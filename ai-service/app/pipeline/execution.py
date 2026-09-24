"""Typed execution boundary for the existing AI2 pipeline.

The boundary owns execution metadata, scope checks and adapter error mapping.
It deliberately does not own canonical run state, audit or evidence storage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.models import HandoffIssue, JobResult, JobStatus, ReviewState
from app.pipeline.runtime import ProcessingTimeout, ProcessingRuntime
from app.tools.store import DossierRecord, InMemorySnapshotStore
from app.contracts.models import ToolEnvelope


class ExecutionContext(BaseModel):
    """Immutable identity and retry context carried through one execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1, max_length=160)
    tenant_id: str = Field(min_length=1, max_length=160)
    dossier_id: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=160)
    correlation_id: str = Field(min_length=1, max_length=160)
    idempotency_key: str = Field(min_length=1, max_length=200)
    attempt: int = Field(default=1, ge=1)
    generation_id: str = Field(min_length=1, max_length=200)
    worker_token: str | None = Field(default=None, max_length=200)
    cancel_requested: bool = False

    @classmethod
    def from_request(
        cls,
        record: DossierRecord,
        envelope: ToolEnvelope,
        *,
        job_id: str | None = None,
        correlation_id: str | None = None,
        idempotency_key: str | None = None,
        attempt: int = 1,
        worker_token: str | None = None,
        cancel_requested: bool = False,
    ) -> "ExecutionContext":
        run_id = job_id or f"run_{uuid4().hex[:12]}"
        return cls(
            run_id=run_id,
            tenant_id=record.tenant_id,
            dossier_id=record.dossier_id,
            actor_id=envelope.auth.actor_id,
            correlation_id=correlation_id or run_id,
            idempotency_key=idempotency_key or run_id,
            attempt=attempt,
            generation_id=f"generation:{run_id}",
            worker_token=worker_token,
            cancel_requested=cancel_requested,
        )


@dataclass(frozen=True, slots=True)
class ExecutionError:
    code: str
    message: str
    retryable: bool = False
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionArtifact:
    """Typed adapter artifact; evidence refs are mandatory for tool output."""

    artifact_id: str
    kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    citation_refs: tuple[str, ...] = ()
    side_effect: bool = False
    approved: bool = False


@dataclass(slots=True)
class ExecutionResponse:
    result: JobResult | None = None
    artifacts: tuple[ExecutionArtifact, ...] = ()
    error: ExecutionError | None = None
    adapter_name: str = "unknown"
    adapter_version: str = "0"

    def to_job_result(self, job_id: str) -> JobResult:
        if self.result is not None:
            return self.result
        error = self.error or ExecutionError("EXECUTION_FAILED", "execution returned no result")
        review_state = ReviewState.BLOCKED if error.code in {
            "TENANT_SCOPE_MISMATCH",
            "DOSSIER_SCOPE_MISMATCH",
            "RUN_CANCELLED",
            "LEASE_FENCED",
            "ADK_VERSION_MISMATCH",
            "SIDE_EFFECT_DENIED",
        } else ReviewState.NEEDS_REVIEW
        return JobResult(
            job_id=job_id,
            status=JobStatus.FAILED,
            review_state=review_state,
            handoff_issues=[HandoffIssue(
                code=error.code,
                message=error.message,
                review_state=review_state,
                retryable=error.retryable,
            )],
            error=error.message,
        )


class CallbackDisposition(str, Enum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    OUT_OF_ORDER = "OUT_OF_ORDER"


@dataclass
class ExecutionRequest:
    context: ExecutionContext
    record: DossierRecord
    envelope: ToolEnvelope
    llm: Any = None
    store: InMemorySnapshotStore | None = None
    index: Any = None
    runtime: ProcessingRuntime | None = None
    lease_guard: Callable[[], bool] | None = None
    _callback_ids: set[str] = field(default_factory=set, init=False, repr=False)
    _last_callback_sequence: int = field(default=0, init=False, repr=False)

    def accept_callback(self, *, callback_id: str, sequence: int) -> CallbackDisposition:
        if callback_id in self._callback_ids:
            return CallbackDisposition.DUPLICATE
        if sequence != self._last_callback_sequence + 1:
            return CallbackDisposition.OUT_OF_ORDER
        self._callback_ids.add(callback_id)
        self._last_callback_sequence = sequence
        return CallbackDisposition.ACCEPTED


class ExecutionAdapter(Protocol):
    adapter_name: str
    adapter_version: str

    def execute(self, request: ExecutionRequest) -> ExecutionResponse:
        """Execute without taking ownership of canonical state or audit."""


PipelineRunner = Callable[..., JobResult]


def _scope_error(request: ExecutionRequest) -> ExecutionError | None:
    checks = (
        (request.context.tenant_id, request.record.tenant_id, "TENANT_SCOPE_MISMATCH"),
        (request.context.tenant_id, request.envelope.auth.tenant_id, "TENANT_SCOPE_MISMATCH"),
        (request.context.dossier_id, request.record.dossier_id, "DOSSIER_SCOPE_MISMATCH"),
        (request.context.dossier_id, request.envelope.auth.dossier_id, "DOSSIER_SCOPE_MISMATCH"),
    )
    for actual, expected, code in checks:
        if actual != expected:
            return ExecutionError(code, f"execution scope mismatch: {actual!r} != {expected!r}")
    return None


class CurrentPipelineAdapter:
    """Adapter around the unchanged synchronous AI2 implementation."""

    adapter_name = "ai2-current-pipeline"
    adapter_version = "1"

    def __init__(self, runner: PipelineRunner) -> None:
        self._runner = runner

    def execute(self, request: ExecutionRequest) -> ExecutionResponse:
        scope_error = _scope_error(request)
        if scope_error is not None:
            return ExecutionResponse(error=scope_error, adapter_name=self.adapter_name, adapter_version=self.adapter_version)
        if request.context.cancel_requested:
            return ExecutionResponse(
                error=ExecutionError("RUN_CANCELLED", "run was cancelled before execution"),
                adapter_name=self.adapter_name,
                adapter_version=self.adapter_version,
            )
        if request.lease_guard is not None and not request.lease_guard():
            return ExecutionResponse(
                error=ExecutionError("LEASE_FENCED", "worker lease is no longer current"),
                adapter_name=self.adapter_name,
                adapter_version=self.adapter_version,
            )
        try:
            result = self._runner(
                request.record,
                request.envelope,
                llm=request.llm,
                store=request.store,
                index=request.index,
                job_id=request.context.run_id,
                runtime=request.runtime,
                execution_context=request.context,
            )
        except ProcessingTimeout as exc:
            return ExecutionResponse(
                error=ExecutionError("EXECUTION_TIMEOUT", str(exc), retryable=True),
                adapter_name=self.adapter_name,
                adapter_version=self.adapter_version,
            )
        except TimeoutError as exc:
            return ExecutionResponse(
                error=ExecutionError("EXECUTION_TIMEOUT", str(exc), retryable=True),
                adapter_name=self.adapter_name,
                adapter_version=self.adapter_version,
            )
        except Exception as exc:  # boundary maps unexpected adapter failures
            return ExecutionResponse(
                error=ExecutionError("EXECUTION_FAILED", f"{type(exc).__name__}: {exc}"),
                adapter_name=self.adapter_name,
                adapter_version=self.adapter_version,
            )
        if request.lease_guard is not None and not request.lease_guard():
            return ExecutionResponse(
                error=ExecutionError("LEASE_FENCED", "worker lease was fenced during execution"),
                adapter_name=self.adapter_name,
                adapter_version=self.adapter_version,
            )
        return ExecutionResponse(
            result=result,
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
        )


def validate_tool_result(result: ExecutionArtifact) -> ExecutionError | None:
    if not result.citation_refs:
        return ExecutionError("TOOL_CITATION_REQUIRED", "external tool result has no citation reference")
    if result.side_effect and not result.approved:
        return ExecutionError("SIDE_EFFECT_DENIED", "external tool side effect requires explicit approval")
    return None


__all__ = [
    "CallbackDisposition",
    "CurrentPipelineAdapter",
    "ExecutionAdapter",
    "ExecutionArtifact",
    "ExecutionContext",
    "ExecutionError",
    "ExecutionRequest",
    "ExecutionResponse",
    "validate_tool_result",
]
