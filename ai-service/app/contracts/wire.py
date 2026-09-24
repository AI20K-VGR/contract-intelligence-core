"""Backend ↔ AI2 processing wire contracts.

These DTOs are intentionally separate from the internal JobResult and
IndexContribution models.  The wire contract is the stable integration
boundary; internal pipeline models may evolve independently.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.errors import ContractValidationError


Id = str


class ServiceEnvelope(BaseModel):
    """Backend authorization envelope carried by the canonical job request."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ai2.service-envelope.v1"]
    issuer: Id = Field(min_length=1, max_length=160)
    audience: Id = Field(min_length=1, max_length=160)
    tenant_id: Id = Field(min_length=1, max_length=160)
    actor_id: Id = Field(min_length=1, max_length=160)
    dossier_id: Id = Field(min_length=1, max_length=160)
    scopes: list[Id] = Field(min_length=1, max_length=32)
    key_id: Id = Field(min_length=1, max_length=160)
    issued_at: int = Field(ge=0)
    expires_at: int = Field(ge=0)
    nonce: Id = Field(min_length=16, max_length=160)
    payload_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    signature: str = Field(pattern=r"^[a-fA-F0-9]{64}$")

    @model_validator(mode="after")
    def validate_window(self) -> "ServiceEnvelope":
        if self.expires_at <= self.issued_at:
            raise ValueError("service envelope expires_at must be after issued_at")
        return self


class SnapshotIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: Id = Field(min_length=1, max_length=160)
    snapshot_version: Literal["ai1.snapshot.v1"]
    source_digest: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    snapshot_digest: str = Field(pattern=r"^[a-fA-F0-9]{64}$")


class DossierMemberWire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_id: Id = Field(min_length=1, max_length=160)
    document_id: Id = Field(min_length=1, max_length=160)
    snapshot_id: Id = Field(min_length=1, max_length=160)
    role: Literal["body", "annex"]
    source_digest: str = Field(pattern=r"^[a-fA-F0-9]{64}$")


class RoleRelationWire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation_id: Id = Field(min_length=1, max_length=160)
    relation_type: Literal["MEMBER_OF", "ANNEX_OF"]
    member_id: Id = Field(min_length=1, max_length=160)
    related_member_id: Id | None = None
    dossier_id: Id = Field(min_length=1, max_length=160)

    @model_validator(mode="after")
    def validate_relation_target(self) -> "RoleRelationWire":
        if self.relation_type == "ANNEX_OF" and not self.related_member_id:
            raise ValueError("ANNEX_OF requires related_member_id")
        if self.relation_type == "MEMBER_OF" and self.related_member_id is not None:
            raise ValueError("MEMBER_OF must not have related_member_id")
        return self


class ProcessingBudgetLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_processing_seconds: int = Field(ge=1)
    max_llm_calls: int = Field(ge=0)
    max_embedding_tokens: int = Field(ge=0)


class ProcessingPolicyFlags(BaseModel):
    model_config = ConfigDict(extra="forbid")

    egress_allowed: bool
    use_vector: bool
    budget_limits: ProcessingBudgetLimits


class BeAi2ProcessingRequest(BaseModel):
    """Canonical Backend → AI2 dossier processing request."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["be.ai2.processing.request.v1"]
    service_envelope: ServiceEnvelope
    request_id: Id = Field(min_length=1, max_length=160)
    idempotency_key: Id = Field(min_length=1, max_length=160)
    attempt: int = Field(ge=1)
    task_id: Id = Field(min_length=1, max_length=160)
    dossier_id: Id = Field(min_length=1, max_length=160)
    snapshots: list[dict[str, Any]] = Field(min_length=1, max_length=6)
    snapshot_identities: list[SnapshotIdentity] = Field(min_length=1, max_length=6)
    dossier_members: list[DossierMemberWire] = Field(min_length=1, max_length=6)
    role_relation_map: list[RoleRelationWire] = Field(default_factory=list, max_length=32)
    policy_flags: ProcessingPolicyFlags

    @model_validator(mode="after")
    def validate_membership(self) -> "BeAi2ProcessingRequest":
        snapshots_by_id = {str(item.get("snapshot_id")): item for item in self.snapshots}
        if len(snapshots_by_id) != len(self.snapshots) or any(key == "None" for key in snapshots_by_id):
            raise ValueError("snapshots must have unique snapshot_id values")

        member_by_id = {item.member_id: item for item in self.dossier_members}
        if len(member_by_id) != len(self.dossier_members):
            raise ValueError("dossier_members must have unique member_id values")
        if len({item.document_id for item in self.dossier_members}) != len(self.dossier_members):
            raise ValueError("dossier_members must have unique document_id values")

        if sum(item.role == "body" for item in self.dossier_members) != 1:
            raise ValueError("dossier_members must contain exactly one body")
        member_snapshot_ids = {item.snapshot_id for item in self.dossier_members}
        identity_snapshot_ids = {item.snapshot_id for item in self.snapshot_identities}
        if len(identity_snapshot_ids) != len(self.snapshot_identities):
            raise ValueError("[SEMANTIC] snapshot_identities must have unique snapshot_id values")
        if member_snapshot_ids != set(snapshots_by_id):
            raise ValueError("dossier_members and snapshots must contain the same snapshot IDs")
        if identity_snapshot_ids != set(snapshots_by_id):
            raise ValueError("snapshot_identities and snapshots must contain the same snapshot IDs")

        identities_by_id = {item.snapshot_id: item for item in self.snapshot_identities}
        for snapshot_id, snapshot in snapshots_by_id.items():
            identity = identities_by_id[snapshot_id]
            if snapshot.get("source_digest") != identity.source_digest:
                raise ValueError(
                    f"[SEMANTIC] snapshot_identities source_digest does not match snapshot {snapshot_id}"
                )
            actual_digest = _snapshot_payload_digest(snapshot)
            if identity.snapshot_digest != actual_digest:
                raise ValueError(f"[SEMANTIC] snapshot_digest does not match snapshot {snapshot_id}")

        for snapshot in self.snapshots:
            if snapshot.get("dossier_id") != self.dossier_id:
                raise ValueError("snapshot dossier_id must match request dossier_id")
        member_ids = set(member_by_id)
        relation_ids: set[str] = set()
        for relation in self.role_relation_map:
            if relation.relation_id in relation_ids:
                raise ValueError("[SEMANTIC] role_relation_map must have unique relation_id values")
            relation_ids.add(relation.relation_id)
            if relation.dossier_id != self.dossier_id or relation.member_id not in member_ids:
                raise ValueError("role_relation_map references an unknown dossier member")
            if relation.related_member_id and relation.related_member_id not in member_ids:
                raise ValueError("role_relation_map references an unknown related member")
            member = member_by_id[relation.member_id]
            related = member_by_id.get(relation.related_member_id or "")
            if relation.relation_type == "ANNEX_OF" and (
                member.role != "annex" or related is None or related.role != "body"
            ):
                raise ValueError("role_relation_map ANNEX_OF must link annex to body in the same dossier")
        return self


def _snapshot_payload_digest(snapshot: Mapping[str, Any]) -> str:
    """Hash the exact canonical snapshot object carried by the backend request."""

    encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _citation_key(citation: Any) -> str:
    """Return a stable wire citation ID without inventing geometry."""

    existing = getattr(citation, "citation_id", None)
    if existing:
        return str(existing)
    import hashlib

    raw = "|".join(
        str(getattr(citation, field, "") or "")
        for field in ("node_id", "page_revision_id", "source_file_id", "page", "text_span")
    )
    return "cit:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _citation_wire(citation: Any, citation_id: str) -> dict[str, Any]:
    value = citation.model_dump(mode="json") if hasattr(citation, "model_dump") else dict(citation)
    # Keep the public wire citation closed under the v1 schema. Internal table
    # metadata (for example table_id/cell_id) belongs in AI2 storage, not this
    # Backend-facing envelope.
    allowed = {
        "citation_id",
        "node_id",
        "page_revision_id",
        "bbox",
        "bbox_fragments",
        "text_span",
        "source_file_id",
        "page",
        "page_range",
        "line_ids",
        "char_start",
        "char_end",
        "breadcrumb",
        "structure_path",
        "geometry_available",
        "source_hash",
        "quote_sha256",
        "coordinate_system",
        "geometry_source",
        "precision",
        "validation_status",
        "table_id",
        "cell_id",
    }
    value = {key: item for key, item in value.items() if key in allowed}
    value["citation_id"] = citation_id
    return value


def job_result_to_wire(job: Any, request: BeAi2ProcessingRequest) -> dict[str, Any]:
    """Map internal JobResult to the stable AI2 → Backend result envelope."""

    citations: dict[str, dict[str, Any]] = {}

    def register(citation: Any) -> str:
        citation_id = _citation_key(citation)
        citations.setdefault(citation_id, _citation_wire(citation, citation_id))
        return citation_id

    facts: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    context_findings: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    evidence_issues: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    contract_context: dict[str, Any] | None = None

    contribution = getattr(job, "contribution", None)
    if contribution is not None:
        for fact in contribution.facts:
            value = fact.model_dump(mode="json", exclude={"citation"})
            value["citation_ids"] = [register(fact.citation)]
            facts.append(value)
        for candidate in contribution.candidates:
            evidence_left = [register(item) for item in candidate.evidence_left]
            evidence_right = [register(item) for item in candidate.evidence_right]
            findings.append(
                {
                    "finding_id": candidate.candidate_id,
                    "left_id": candidate.left_id,
                    "right_id": candidate.right_id,
                    "finding_type": candidate.finding_type.value,
                    "model_disposition": candidate.model_disposition.value,
                    "review_state": candidate.review_state.value,
                    "evidence_left_citation_ids": evidence_left,
                    "evidence_right_citation_ids": evidence_right,
                    "reason": candidate.reason,
                    "disposition": candidate.disposition.value if candidate.disposition else None,
                    "scope": candidate.scope.value if candidate.scope else None,
                    "item_key": candidate.item_key,
                }
            )
        for event in contribution.events:
            value = event.model_dump(mode="json", exclude={"citation"})
            value["citation_ids"] = [register(event.citation)]
            events.append(value)
        chunks = [item.model_dump(mode="json") for item in contribution.chunks]
        for issue in contribution.evidence_issues:
            issue_value = issue.model_dump(mode="json", exclude={"citation"})
            issue_value["citation_ids"] = [register(issue.citation)] if issue.citation else []
            evidence_issues.append(issue_value)
        if contribution.contract_context is not None:
            context_value = contribution.contract_context.model_dump(mode="json")
            for part, original_part in zip(context_value.get("parts", []), contribution.contract_context.parts):
                citation = part.get("citation")
                if citation:
                    part["citation_ids"] = [register(original_part.citation)]
                    part.pop("citation", None)
            for finding in context_value.get("findings", []):
                finding["citation_ids"] = []
                original = next((item for item in contribution.contract_context.findings if item.finding_id == finding.get("finding_id")), None)
                if original:
                    finding["citation_ids"] = [register(item) for item in original.citations]
                    context_findings.append(
                        {
                            "finding_id": original.finding_id,
                            "finding_type": original.kind,
                            "relation_type": original.relation_type.value if original.relation_type else None,
                            "subject_key": original.subject_key,
                            "source_node_ids": original.source_node_ids,
                            "review_state": original.review_state.value,
                            "reason": original.reason,
                            "citation_ids": finding["citation_ids"],
                            "metadata": original.metadata,
                        }
                    )
                finding.pop("citations", None)
            contract_context = context_value

    handoff_issues = list(getattr(job, "handoff_issues", []) or [])
    retryable_codes = {
        "PROCESSING_TIMEOUT",
        "LLM_TIMEOUT",
        "LLM_RETRY_EXHAUSTED",
        "AI2_WORKER_FAILED",
    }
    errors = [
        {
            "code": issue.code,
            "message": issue.message,
            "retryable": issue.review_state.value == "BLOCKED" or issue.code in retryable_codes,
        }
        for issue in handoff_issues
    ]
    if getattr(job, "error", None):
        errors.append({"code": "AI2_JOB_FAILED", "message": job.error, "retryable": False})

    status = job.status.value
    review_state = job.review_state.value if job.review_state else None
    result = None
    if status == "SUCCEEDED" and contribution is not None:
        result = {
            "facts": facts,
            "findings": findings,
            "context_findings": context_findings,
            "events": events,
            "citations": list(citations.values()),
            "index_contribution": {
                "state": "propose",
                "chunks": chunks,
                "evidence_issues": evidence_issues,
                "coverage": contribution.coverage,
                "extraction_version": contribution.extraction_version,
                "proposed_index_version": contribution.proposed_index_version,
                "contract_context": contract_context,
            },
        }

    payload = {
        "schema_version": "ai2.be.processing.result.v1",
        "request_id": request.request_id,
        "idempotency_key": request.idempotency_key,
        "attempt": request.attempt,
        "job_id": job.job_id,
        "status": status,
        "review_state": review_state,
        "input_snapshots": [item.model_dump(mode="json") for item in request.snapshot_identities],
        "result": result,
        "errors": errors,
    }
    validate_processing_result(payload, request=request)
    return payload


def validate_processing_result(
    payload: Mapping[str, Any],
    *,
    request: BeAi2ProcessingRequest | Mapping[str, Any] | None = None,
) -> None:
    """Validate a result envelope and its cross-object evidence references.

    JSON Schema protects the closed wire shape.  This validator adds the
    relationships that schema cannot express: request lineage, unique input
    identities, unique citation identity, and every citation reference being
    resolvable.  It raises the boundary error used by adapters so callers get
    a stable code instead of a raw ``KeyError``/``ValidationError``.
    """

    from app.pipeline.ai1_snapshot_adapter import SnapshotContractError

    def fail(message: str, code: str) -> None:
        raise SnapshotContractError(message, code=code)

    if not isinstance(payload, Mapping):
        fail("AI2 result must be an object", "RESULT_CONTRACT_INVALID")
    try:
        from app.contracts.schema_validation import validate_contract

        validate_contract(payload, "ai2.be.processing.result.v1.schema.json", error_code="RESULT_SCHEMA_INVALID")
    except ContractValidationError as exc:
        fail(str(exc), exc.code)

    if request is not None:
        try:
            expected = request if isinstance(request, BeAi2ProcessingRequest) else BeAi2ProcessingRequest.model_validate(request)
        except Exception as exc:
            fail(f"invalid expected processing request: {exc}", "PROCESSING_REQUEST_CONTRACT_INVALID")
        for field in ("request_id", "idempotency_key", "attempt"):
            if payload[field] != getattr(expected, field):
                fail(f"result {field} does not match request", "RESULT_MEMBERSHIP_INVALID")
        expected_snapshots = [item.model_dump(mode="json") for item in expected.snapshot_identities]
        if payload["input_snapshots"] != expected_snapshots:
            fail("result input_snapshots do not match request identities", "RESULT_MEMBERSHIP_INVALID")

    identities = payload["input_snapshots"]
    identity_ids = [item["snapshot_id"] for item in identities]
    if len(identity_ids) != len(set(identity_ids)):
        fail("result input_snapshots contain duplicate snapshot identity", "RESULT_SEMANTIC_INVALID")

    result = payload.get("result")
    if payload["status"] == "SUCCEEDED" and result is None:
        fail("SUCCEEDED result must contain result payload", "RESULT_SEMANTIC_INVALID")
    if result is None:
        return

    citations = result["citations"]
    citation_ids = [item["citation_id"] for item in citations]
    if len(citation_ids) != len(set(citation_ids)):
        fail("result citations contain duplicate citation_id", "RESULT_SEMANTIC_INVALID")
    citation_set = set(citation_ids)

    def check_refs(values: Any, label: str) -> None:
        if not isinstance(values, list) or any(value not in citation_set for value in values):
            fail(f"{label} references an unknown citation", "RESULT_SEMANTIC_INVALID")

    for fact in result["facts"]:
        check_refs(fact["citation_ids"], f"fact {fact['fact_id']}")
    for finding in result["findings"]:
        check_refs(finding["evidence_left_citation_ids"], f"finding {finding['finding_id']} left evidence")
        check_refs(finding["evidence_right_citation_ids"], f"finding {finding['finding_id']} right evidence")
    for finding in result.get("context_findings", []):
        check_refs(finding["citation_ids"], f"context finding {finding['finding_id']}")
    for issue in result["index_contribution"].get("evidence_issues", []):
        if isinstance(issue, Mapping):
            check_refs(issue.get("citation_ids", []), "evidence issue")


validate_result_wire = validate_processing_result
