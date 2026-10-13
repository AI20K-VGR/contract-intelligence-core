"""Tenant-scoped expert approval, atomic CAS, immutable receipts và draft-only fallback."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.shared.ai.tenant_lexicon_contracts import (
    ACTION_SYMBOLS,
    QUALIFIER_SYMBOLS,
    ActivationPolicy,
    ActiveAlias,
    Assignment,
    ErrorMeasurement,
    LexiconCommand,
    PromotionOptIn,
    Proposal,
    ProposalTarget,
    digest_json,
    normalize_source,
    validate_alias,
)
from contract_intelligence.shared.ai.tenant_lexicon_store import (
    AliasEntryORM,
    AliasProposalORM,
    ExpertAssignmentORM,
    LexiconAuditORM,
    LexiconHeadORM,
    LexiconVersionORM,
)
from contract_intelligence.shared.auth.schemas import AuthenticatedUser


class LexiconError(Exception):
    def __init__(self, status: int, code: str) -> None:
        self.status = status
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class VerifiedMeasurement:
    errors: int
    denominator: int
    labels_digest: str


class ApprovedLabelMeasurementReader:
    """Đọc artifact được reviewer giữ trong trusted root; ref là SHA256 bytes đã freeze."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve(strict=True)

    def resolve(
        self,
        tenant_id: str,
        proposal: AliasProposalORM,
        reviewer_id: str,
        approved_by: str | None,
        labels_ref: str,
    ) -> VerifiedMeasurement | None:
        if len(labels_ref) != 64 or any(c not in "0123456789abcdef" for c in labels_ref):
            return None
        path = self.root / f"{labels_ref}.json"
        try:
            if (
                path.is_symlink()
                or path.resolve(strict=True).parent != self.root
                or path.stat().st_size > 1_000_000
            ):
                return None
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != labels_ref:
                return None
            data = json.loads(raw)
        except (OSError, ValueError, UnicodeError):
            return None
        required = {
            "schema_version",
            "status",
            "tenant_id",
            "proposal_id",
            "proposal_version",
            "source",
            "kind",
            "symbol",
            "producer_id",
            "reviewer_id",
            "approval_ref",
            "labels",
        }
        if not isinstance(data, dict) or set(data) != required:
            return None
        if (
            data["schema_version"] != "tenant_alias.labels.v1"
            or data["status"] != "APPROVED"
            or data["tenant_id"] != tenant_id
            or data["proposal_id"] != proposal.proposal_id
            or type(data["proposal_version"]) is not int
            or data["proposal_version"] != proposal.version
            or data["source"] != normalize_source(proposal.source)
            or data["kind"] != proposal.kind
            or data["symbol"] != proposal.symbol
            or data["producer_id"] != proposal.producer_id
            or data["reviewer_id"] != reviewer_id
            or reviewer_id in {proposal.producer_id, approved_by}
            or not isinstance(data["approval_ref"], str)
            or not data["approval_ref"].strip()
            or not isinstance(data["labels"], list)
        ):
            return None
        symbols = ACTION_SYMBOLS if proposal.kind == "action" else QUALIFIER_SYMBOLS
        seen = set()
        errors = 0
        for label in data["labels"]:
            if (
                not isinstance(label, dict)
                or set(label) != {"unit_id", "expected_symbol", "source_ref", "source_digest"}
                or not isinstance(label["unit_id"], str)
                or not label["unit_id"].strip()
                or label["unit_id"] in seen
                or not isinstance(label["expected_symbol"], str)
                or label["expected_symbol"] not in symbols
                or not isinstance(label["source_ref"], str)
                or not label["source_ref"].strip()
                or not isinstance(label["source_digest"], str)
                or len(label["source_digest"]) != 64
                or any(c not in "0123456789abcdef" for c in label["source_digest"])
            ):
                return None
            seen.add(label["unit_id"])
            errors += label["expected_symbol"] != proposal.symbol
        return VerifiedMeasurement(errors, len(seen), labels_ref)


class TenantLexiconService:
    def __init__(
        self,
        session: AsyncSession,
        policy: ActivationPolicy | None = None,
        measurement_reader: ApprovedLabelMeasurementReader | None = None,
    ) -> None:
        self.session = session
        self.policy = policy
        self.measurement_reader = measurement_reader

    @staticmethod
    def _scope(tenant_id: str, user: AuthenticatedUser) -> None:
        if not user.is_active or user.tenant_id != tenant_id:
            raise LexiconError(403, "TENANT_SCOPE_DENIED")

    async def _expert(self, tenant_id: str, user: AuthenticatedUser) -> ExpertAssignmentORM:
        assignment = await self.session.scalar(
            select(ExpertAssignmentORM)
            .where(ExpertAssignmentORM.tenant_id == tenant_id)
            .order_by(ExpertAssignmentORM.version.desc())
            .limit(1)
        )
        if (
            assignment is None
            or assignment.expert_id != user.user_id
            or assignment.expires_at <= datetime.now(UTC)
        ):
            raise LexiconError(403, "NAMED_CONTRACT_EXPERT_REQUIRED")
        return assignment

    async def read_profile(
        self, tenant_id: str, user: AuthenticatedUser, version: int | None = None
    ) -> dict[str, Any]:
        self._scope(tenant_id, user)
        query = select(LexiconVersionORM).where(LexiconVersionORM.tenant_id == tenant_id)
        if version is not None:
            query = query.where(LexiconVersionORM.version == version)
        record = await self.session.scalar(
            query.order_by(LexiconVersionORM.version.desc()).limit(1)
        )
        if record is None:
            if version is not None:
                raise LexiconError(404, "PROFILE_VERSION_NOT_FOUND")
            return self._initial(tenant_id)
        # JSON is validated on writes; copy ensures callers cannot mutate ORM history.
        return copy.deepcopy(record.profile)

    @staticmethod
    def _initial(tenant_id: str) -> dict[str, Any]:
        return {
            "tenant_id": tenant_id,
            "version": 0,
            "aliases": [],
            "active_aliases": [],
            "proposals": [],
            "decisions": {},
            "measurements": {},
            "opt_in": False,
            "activation_state": "DRAFT_ONLY",
            "activation_blockers": ["POLICY_NOT_FROZEN"],
        }

    async def resolve_for_run(self, tenant_id: str) -> dict[str, Any]:
        """Chỉ dùng với tenant đã lấy từ job owner tin cậy; pin một bản sao cho run mới."""
        record = await self.session.scalar(
            select(LexiconVersionORM)
            .where(LexiconVersionORM.tenant_id == tenant_id)
            .order_by(LexiconVersionORM.version.desc())
            .limit(1)
        )
        version = record.version if record else 0
        aliases: list[dict[str, object]] = []
        if (
            record
            and self.policy
            and record.profile.get("policy_digest") == self.policy.policy_digest
        ):
            assignment = await self.session.scalar(
                select(ExpertAssignmentORM)
                .where(ExpertAssignmentORM.tenant_id == tenant_id)
                .order_by(ExpertAssignmentORM.version.desc())
                .limit(1)
            )
            if assignment and assignment.expires_at > datetime.now(UTC):
                aliases = [
                    alias.model_dump()
                    for alias in TypeAdapter(list[ActiveAlias]).validate_python(
                        record.profile["active_aliases"]
                    )
                ]
        snapshot = {"tenant_id": tenant_id, "version": version, "aliases": aliases}
        return {**snapshot, "digest": digest_json(snapshot), "method": "TENANT_ALIAS"}

    async def read_metadata(self, tenant_id: str, user: AuthenticatedUser) -> dict[str, Any]:
        """Quyền hiện tại tách khỏi profile immutable; không suy expert từ RBAC admin."""
        self._scope(tenant_id, user)
        profile = await self.read_profile(tenant_id, user)
        assignment = await self.session.scalar(
            select(ExpertAssignmentORM)
            .where(ExpertAssignmentORM.tenant_id == tenant_id)
            .order_by(ExpertAssignmentORM.version.desc())
            .limit(1)
        )
        expert = bool(
            assignment
            and assignment.expert_id == user.user_id
            and assignment.expires_at > datetime.now(UTC)
        )
        admin = user.role == "ADMINISTRATOR"
        producers = {p["proposal_id"]: p["producer_id"] for p in profile["proposals"]}
        current_aliases = (await self.resolve_for_run(tenant_id))["aliases"]
        assignment_data = (
            {
                "expert_id": assignment.expert_id,
                "expertise_ref": assignment.expertise_ref,
                "expires_at": assignment.expires_at.isoformat(),
                "designated_by": assignment.designated_by,
            }
            if assignment
            else None
        )
        return {
            "assignment": assignment_data,
            "permissions": {
                "can_propose": user.role in {"OPERATOR", "ADMINISTRATOR"},
                "can_assign": admin,
                "can_approve": expert,
                "can_reject": expert,
                "can_revoke": expert,
                "can_opt_in": admin,
                "can_measure": expert
                and any(
                    a.get("approved_by") != user.user_id
                    and producers.get(a["proposal_id"]) != user.user_id
                    for a in profile["aliases"]
                ),
                "can_promote": bool(
                    admin and profile["opt_in"] and self.policy and current_aliases
                ),
            },
        }

    async def execute(
        self, tenant_id: str, user: AuthenticatedUser, command: LexiconCommand
    ) -> dict[str, Any]:
        self._scope(tenant_id, user)
        if self.session.in_transaction():
            raise RuntimeError("lexicon command requires a fresh transaction scope")
        async with self.session.begin():
            await self.session.execute(
                insert(LexiconHeadORM)
                .values(tenant_id=tenant_id, version=0)
                .on_conflict_do_nothing()
            )
            head = await self.session.scalar(
                select(LexiconHeadORM)
                .where(LexiconHeadORM.tenant_id == tenant_id)
                .with_for_update()
            )
            if head is None:
                raise RuntimeError("missing locked lexicon head")
            previous = await self.session.get(
                LexiconAuditORM, (tenant_id, user.user_id, command.idempotency_key)
            )
            if previous is not None:
                if previous.command_digest != command.digest:
                    raise LexiconError(409, "IDEMPOTENCY_DIGEST_CONFLICT")
                return copy.deepcopy(previous.receipt)
            if head.version != command.base_version:
                raise LexiconError(409, "LEXICON_VERSION_CONFLICT")
            profile = await self.read_profile(tenant_id, user)
            version = head.version + 1
            receipt = await self._apply(tenant_id, user, command, profile, version)
            self._activation(profile)
            profile["version"] = version
            profile["alias_digest"] = digest_json(
                {
                    "tenant_id": tenant_id,
                    "version": version,
                    "aliases": sorted(
                        profile["active_aliases"], key=lambda a: (a["kind"], a["source"])
                    ),
                }
            )
            profile["digest"] = digest_json(
                {key: value for key, value in profile.items() if key != "digest"}
            )
            receipt.update(
                version=version,
                digest=profile["digest"],
                activation_state=profile["activation_state"],
                activation_blockers=profile["activation_blockers"],
            )
            self.session.add(
                LexiconVersionORM(
                    tenant_id=tenant_id, version=version, digest=profile["digest"], profile=profile
                )
            )
            await self.session.flush()
            for alias in profile["aliases"]:
                self.session.add(
                    AliasEntryORM(
                        tenant_id=tenant_id,
                        version=version,
                        source=alias["source"],
                        kind=alias["kind"],
                        symbol=alias["symbol"],
                        proposal_id=alias["proposal_id"],
                        method="TENANT_ALIAS",
                    )
                )
            self.session.add(
                LexiconAuditORM(
                    tenant_id=tenant_id,
                    actor_id=user.user_id,
                    idempotency_key=command.idempotency_key,
                    command_digest=command.digest,
                    action=command.action,
                    created_at=datetime.now(UTC),
                    receipt=receipt,
                )
            )
            head.version = version
            return copy.deepcopy(receipt)

    async def _apply(
        self,
        tenant_id: str,
        user: AuthenticatedUser,
        command: LexiconCommand,
        profile: dict[str, Any],
        version: int,
    ) -> dict[str, Any]:
        try:
            return await self._validated_apply(tenant_id, user, command, profile, version)
        except (ValidationError, ValueError, TypeError) as exc:
            raise LexiconError(422, "INVALID_LEXICON_COMMAND") from exc

    async def _validated_apply(
        self,
        tenant_id: str,
        user: AuthenticatedUser,
        command: LexiconCommand,
        profile: dict[str, Any],
        version: int,
    ) -> dict[str, Any]:
        action, payload = command.action, command.payload
        receipt: dict[str, Any] = {
            "action": action,
            "actor_id": user.user_id,
            "tenant_id": tenant_id,
        }
        if action == "ASSIGN":
            if user.role != "ADMINISTRATOR":
                raise LexiconError(403, "TENANT_ADMIN_REQUIRED")
            assignment = Assignment.model_validate_json(json.dumps(payload))
            self.session.add(
                ExpertAssignmentORM(
                    tenant_id=tenant_id,
                    version=version,
                    expert_id=assignment.expert_id,
                    designated_by=user.user_id,
                    expertise_ref=assignment.expertise_ref,
                    expires_at=assignment.expires_at,
                )
            )
            return receipt
        if action == "OPT_IN":
            if user.role != "ADMINISTRATOR":
                raise LexiconError(403, "TENANT_ADMIN_REQUIRED")
            consent = PromotionOptIn.model_validate(payload)
            profile["opt_in"] = consent.enabled
            profile["consent_ref"] = consent.consent_ref
            return receipt
        if action == "PROPOSE":
            if user.role not in {"OPERATOR", "ADMINISTRATOR"}:
                raise LexiconError(403, "OPERATOR_REQUIRED")
            proposal = Proposal.model_validate(payload)
            proposal_id = str(uuid4())
            self.session.add(
                AliasProposalORM(
                    tenant_id=tenant_id,
                    proposal_id=proposal_id,
                    producer_id=user.user_id,
                    version=version,
                    **proposal.model_dump(),
                )
            )
            profile["proposals"].append(
                {"proposal_id": proposal_id, "producer_id": user.user_id, **proposal.model_dump()}
            )
            profile["decisions"][proposal_id] = "PROPOSED"
            receipt["proposal_id"] = proposal_id
            return receipt
        target = (
            ErrorMeasurement.model_validate(payload)
            if action == "MEASURE"
            else ProposalTarget.model_validate(payload)
        )
        proposal_orm = await self.session.get(AliasProposalORM, (tenant_id, target.proposal_id))
        if proposal_orm is None:
            raise LexiconError(404, "PROPOSAL_NOT_FOUND")
        receipt["proposal_id"] = target.proposal_id
        if action == "PROMOTE":
            eligible = {
                a["proposal_id"] for a in (await self.resolve_for_run(tenant_id))["aliases"]
            }
            if (
                user.role != "ADMINISTRATOR"
                or not profile["opt_in"]
                or self.policy is None
                or target.proposal_id not in eligible
            ):
                raise LexiconError(403, "PROMOTION_NOT_AUTHORIZED")
            receipt["abstract_alias"] = {
                "source": proposal_orm.source,
                "symbol": proposal_orm.symbol,
                "kind": proposal_orm.kind,
            }
            return receipt
        await self._expert(tenant_id, user)
        state = profile["decisions"].get(target.proposal_id)
        if action == "MEASURE":
            assert isinstance(target, ErrorMeasurement)
            approver = next(
                (
                    a.get("approved_by")
                    for a in profile["aliases"]
                    if a["proposal_id"] == target.proposal_id
                ),
                None,
            )
            if user.user_id in {proposal_orm.producer_id, approver}:
                raise LexiconError(403, "INDEPENDENT_LABEL_REVIEWER_REQUIRED")
            verified = (
                self.measurement_reader.resolve(
                    tenant_id, proposal_orm, user.user_id, approver, target.labels_ref
                )
                if self.measurement_reader
                else None
            )
            profile["measurements"][target.proposal_id] = {
                **target.model_dump(),
                "reviewer_id": user.user_id,
                "verified": verified is not None,
                "errors": verified.errors if verified else target.errors,
                "denominator": verified.denominator if verified else target.denominator,
                "labels_digest": verified.labels_digest if verified else None,
            }
            return receipt
        if action == "APPROVE":
            if state != "PROPOSED":
                raise LexiconError(409, "PROPOSAL_ALREADY_DECIDED")
            if proposal_orm.producer_id == user.user_id:
                raise LexiconError(403, "PRODUCER_CANNOT_APPROVE")
            source = validate_alias(
                proposal_orm.source,
                proposal_orm.symbol,
                proposal_orm.kind,
                minimum_length=self.policy.minimum_length if self.policy else 4,
            )
            if any(
                a["source"] == source and a["kind"] == proposal_orm.kind for a in profile["aliases"]
            ):
                raise LexiconError(409, "ALIAS_COLLISION")
            profile["aliases"].append(
                {
                    "source": source,
                    "symbol": proposal_orm.symbol,
                    "kind": proposal_orm.kind,
                    "proposal_id": target.proposal_id,
                    "method": "TENANT_ALIAS",
                    "approved_by": user.user_id,
                }
            )
            profile["decisions"][target.proposal_id] = "APPROVED_DRAFT"
        elif action == "REJECT":
            if state != "PROPOSED":
                raise LexiconError(409, "PROPOSAL_ALREADY_DECIDED")
            profile["decisions"][target.proposal_id] = "REJECTED"
        elif action == "REVOKE":
            if state != "APPROVED_DRAFT":
                raise LexiconError(409, "APPROVED_ALIAS_REQUIRED")
            profile["aliases"] = [
                a for a in profile["aliases"] if a["proposal_id"] != target.proposal_id
            ]
            profile["decisions"][target.proposal_id] = "REVOKED"
        return receipt

    def _activation(self, profile: dict[str, Any]) -> None:
        profile["active_aliases"] = []
        blockers = set()
        if self.policy is None:
            blockers.add("POLICY_NOT_FROZEN")
        for alias in profile["aliases"]:
            measurement = profile["measurements"].get(alias["proposal_id"])
            if (
                measurement is None
                or not measurement.get("verified")
                or measurement["denominator"] == 0
                or measurement.get("reviewer_id") == alias.get("approved_by")
            ):
                blockers.add("INDEPENDENT_ERROR_RATE_NOT_MEASURED")
                continue
            if (
                self.policy
                and measurement["errors"] / measurement["denominator"]
                <= self.policy.revoke_error_rate
            ):
                profile["active_aliases"].append(
                    {key: alias[key] for key in ("source", "symbol", "kind", "proposal_id")}
                )
            elif self.policy:
                blockers.add("REVOKE_ERROR_THRESHOLD_EXCEEDED")
        profile["activation_blockers"] = sorted(blockers)
        profile["activation_state"] = "ACTIVE" if profile["active_aliases"] else "DRAFT_ONLY"
        profile["policy_digest"] = self.policy.policy_digest if self.policy else None
