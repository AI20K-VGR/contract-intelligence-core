"""Deterministic migration boundary used by the P8 parity tests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Callable

from app.migration.canary import OutputComparison, compare_outputs


class DuplicateSubmissionConflict(ValueError):
    """Raised when an idempotency key is reused for a different request."""


class Route(str, Enum):
    LEGACY = "legacy"
    CANARY = "canary"
    CANONICAL = "canonical"
    DUAL_READ = "dual-read"


@dataclass
class FeatureFlags:
    canonical_enabled: bool = False
    dual_read: bool = False
    canary_tenants: frozenset[str] = field(default_factory=frozenset)
    rollback_to_legacy: bool = False


@dataclass(frozen=True)
class MigrationRequest:
    tenant_id: str
    legacy_session_id: str
    idempotency_key: str
    raw_ai1: dict[str, Any]


@dataclass(frozen=True)
class DocumentInspection:
    document_count: int
    mode: str
    document_ids: tuple[str, ...]


@dataclass(frozen=True)
class AuditRecord:
    action: str


@dataclass(frozen=True)
class SubmissionOutcome:
    run_id: str
    generation_id: str
    route: Route
    result: Any
    parity: OutputComparison | None = None
    duplicate: bool = False


@dataclass(frozen=True)
class PublishOutcome:
    published: bool
    reason: str | None = None


Reader = Callable[[dict[str, Any]], Any]


def _request_digest(request: MigrationRequest) -> str:
    encoded = json.dumps(
        request.raw_ai1,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


class MigrationBoundary:
    def __init__(self, flags: FeatureFlags | None = None) -> None:
        self.flags = flags or FeatureFlags()
        self.records: list[AuditRecord] = []
        self._submissions: dict[tuple[str, str], tuple[str, SubmissionOutcome]] = {}
        self._sessions: dict[tuple[str, str], str] = {}
        self._published: dict[str, Any] = {}

    def route_for(self, tenant_id: str) -> Route:
        if self.flags.rollback_to_legacy or not self.flags.canonical_enabled:
            return Route.LEGACY
        if self.flags.dual_read and (
            not self.flags.canary_tenants or tenant_id in self.flags.canary_tenants
        ):
            return Route.DUAL_READ
        if not self.flags.canary_tenants or tenant_id in self.flags.canary_tenants:
            return Route.CANONICAL
        return Route.LEGACY

    def inspect_documents(self, request: MigrationRequest) -> DocumentInspection:
        documents = request.raw_ai1.get("documents")
        if not isinstance(documents, list):
            documents = [{"id": request.raw_ai1.get("snapshot_id", "document-1")}]

        document_ids = tuple(
            str(document.get("id"))
            for document in documents
            if isinstance(document, dict) and "id" in document
        )
        return DocumentInspection(
            document_count=len(documents),
            mode="one-document" if len(documents) == 1 else "multi-document",
            document_ids=document_ids,
        )

    def submit(
        self,
        request: MigrationRequest,
        *,
        legacy_reader: Reader | None = None,
        canonical_reader: Reader | None = None,
    ) -> SubmissionOutcome:
        submission_key = (request.tenant_id, request.idempotency_key)
        digest = _request_digest(request)
        existing = self._submissions.get(submission_key)
        if existing is not None:
            old_digest, outcome = existing
            if old_digest != digest:
                raise DuplicateSubmissionConflict(
                    f"idempotency key conflict: {request.idempotency_key}"
                )
            return SubmissionOutcome(
                run_id=outcome.run_id,
                generation_id=outcome.generation_id,
                route=outcome.route,
                result=outcome.result,
                parity=outcome.parity,
                duplicate=True,
            )

        session_key = (request.tenant_id, request.legacy_session_id)
        run_id = self._sessions.setdefault(
            session_key,
            f"run-{request.tenant_id}-{request.legacy_session_id}",
        )
        generation_id = "generation-1"
        route = self.route_for(request.tenant_id)
        payload = deepcopy(request.raw_ai1)
        legacy_result = legacy_reader(payload) if legacy_reader else payload
        parity: OutputComparison | None = None

        if route is Route.DUAL_READ:
            canonical_result = (
                canonical_reader(deepcopy(request.raw_ai1))
                if canonical_reader
                else deepcopy(legacy_result)
            )
            result = legacy_result
            parity = compare_outputs(legacy_result, canonical_result)
        elif route in {Route.CANARY, Route.CANONICAL} and canonical_reader:
            result = canonical_reader(deepcopy(request.raw_ai1))
        else:
            result = legacy_result

        outcome = SubmissionOutcome(
            run_id=run_id,
            generation_id=generation_id,
            route=route,
            result=result,
            parity=parity,
        )
        self._submissions[submission_key] = (digest, outcome)
        self.records.append(AuditRecord(action="SUBMITTED"))
        if parity is not None:
            self.records.append(AuditRecord(action="PARITY_CHECKED"))
        return outcome

    def rollback(self, *, reason: str) -> None:
        del reason
        self.flags.rollback_to_legacy = True
        self.records.append(AuditRecord(action="ROLLBACK_ACTIVATED"))

    def publish(
        self,
        run_id: str,
        *,
        generation_id: str,
        result: Any,
        verified: bool,
    ) -> PublishOutcome:
        if self.flags.rollback_to_legacy:
            self.records.append(AuditRecord(action="PUBLISH_REJECTED"))
            return PublishOutcome(False, "ROLLBACK_ACTIVE")

        if not any(
            outcome.run_id == run_id
            for _, outcome in self._submissions.values()
        ):
            self.records.append(AuditRecord(action="PUBLISH_REJECTED"))
            return PublishOutcome(False, "UNKNOWN_RUN")

        expected_generation = next(
            outcome.generation_id
            for _, outcome in self._submissions.values()
            if outcome.run_id == run_id
        )
        if generation_id != expected_generation:
            self.records.append(AuditRecord(action="PUBLISH_REJECTED"))
            return PublishOutcome(False, "STALE_GENERATION")
        if not verified:
            self.records.append(AuditRecord(action="PUBLISH_REJECTED"))
            return PublishOutcome(False, "UNVERIFIED_GENERATION")

        self._published[run_id] = result
        self.records.append(AuditRecord(action="PUBLISHED"))
        return PublishOutcome(True)

    def published_result(self, run_id: str) -> Any | None:
        return self._published.get(run_id)

    def run_for_session(self, legacy_session_id: str) -> str | None:
        matches = [
            run_id
            for (tenant_id, session_id), run_id in self._sessions.items()
            if session_id == legacy_session_id
        ]
        return matches[0] if matches else None
