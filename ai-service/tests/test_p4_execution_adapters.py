from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.contracts.models import JobResult, JobStatus, ReviewState
from fixtures import envelope as fixture_envelope
from fixtures import mock_record
from app.pipeline.adk_adapter import (
    ADKExecutionAdapter,
    ADKExecutionRequest,
    ADKExecutionResponse,
    ADKToolResult,
)
from app.pipeline.execution import (
    CallbackDisposition,
    ExecutionContext,
    ExecutionRequest,
    ExecutionResponse,
    CurrentPipelineAdapter,
    validate_tool_result,
)


def _context(**overrides) -> ExecutionContext:
    values = {
        "run_id": "run-p4",
        "tenant_id": "tenant_a",
        "dossier_id": "dossier_001",
        "actor_id": "user_001",
        "correlation_id": "corr-p4",
        "idempotency_key": "idem-p4",
        "attempt": 1,
        "generation_id": "generation:run-p4",
    }
    values.update(overrides)
    return ExecutionContext(**values)


def _request(**overrides) -> ExecutionRequest:
    values = {
        "context": _context(),
        "record": mock_record(),
        "envelope": fixture_envelope(),
    }
    values.update(overrides)
    return ExecutionRequest(**values)


def _job() -> JobResult:
    return JobResult(job_id="run-p4", status=JobStatus.SUCCEEDED, review_state=ReviewState.PASS)


def test_current_pipeline_adapter_returns_typed_result_and_propagates_scope():
    seen = {}

    def runner(record, envelope, **kwargs):
        seen.update(kwargs)
        return _job()

    response = CurrentPipelineAdapter(runner).execute(_request())

    assert isinstance(response, ExecutionResponse)
    assert response.result == _job()
    assert response.error is None
    assert seen["job_id"] == "run-p4"
    assert seen["execution_context"].tenant_id == "tenant_a"


def test_current_pipeline_adapter_rejects_tenant_scope_mismatch_before_running():
    calls = []
    request = _request(context=_context(tenant_id="tenant-b"))

    response = CurrentPipelineAdapter(lambda *_args, **_kwargs: calls.append(True)).execute(request)

    assert response.result is None
    assert response.error is not None
    assert response.error.code == "TENANT_SCOPE_MISMATCH"
    assert calls == []


def test_current_pipeline_adapter_maps_timeout_and_cancel_without_losing_typed_error():
    def timeout_runner(*_args, **_kwargs):
        raise TimeoutError("provider timeout")

    timed_out = CurrentPipelineAdapter(timeout_runner).execute(_request())
    cancelled = CurrentPipelineAdapter(lambda *_args, **_kwargs: _job()).execute(
        _request(context=_context(cancel_requested=True))
    )

    assert timed_out.error is not None
    assert timed_out.error.code == "EXECUTION_TIMEOUT"
    assert timed_out.error.retryable is True
    assert cancelled.error is not None
    assert cancelled.error.code == "RUN_CANCELLED"


def test_current_pipeline_adapter_fences_worker_before_and_after_execution():
    valid = iter([False])
    response = CurrentPipelineAdapter(lambda *_args, **_kwargs: _job()).execute(
        _request(lease_guard=lambda: next(valid))
    )

    assert response.error is not None
    assert response.error.code == "LEASE_FENCED"

    checks = iter([True, False])
    response = CurrentPipelineAdapter(lambda *_args, **_kwargs: _job()).execute(
        _request(lease_guard=lambda: next(checks))
    )
    assert response.error is not None
    assert response.error.code == "LEASE_FENCED"


def test_callback_tracker_classifies_duplicate_and_out_of_order_callbacks():
    request = _request()
    first = request.accept_callback(callback_id="cb-1", sequence=1)
    duplicate = request.accept_callback(callback_id="cb-1", sequence=1)
    gap = request.accept_callback(callback_id="cb-3", sequence=3)

    assert first == CallbackDisposition.ACCEPTED
    assert duplicate == CallbackDisposition.DUPLICATE
    assert gap == CallbackDisposition.OUT_OF_ORDER


@dataclass
class FakeADKRuntime:
    api_version: str = "adk-python:1"

    def execute(self, request: ADKExecutionRequest) -> ADKExecutionResponse:
        assert request.context.tenant_id == "tenant_a"
        return ADKExecutionResponse(
            status="SUCCEEDED",
            artifact=ADKToolResult(
                artifact_id="artifact-1",
                kind="tool-result",
                payload={"ok": True},
                citation_refs=("cite-1",),
            ),
        )


def test_optional_adk_adapter_is_dependency_free_and_maps_versioned_artifact():
    response = ADKExecutionAdapter(FakeADKRuntime(), expected_version="adk-python:1").execute(_request())

    assert response.error is None
    assert response.artifacts[0].artifact_id == "artifact-1"
    assert response.adapter_name == "adk"


def test_optional_adk_adapter_rejects_version_mismatch_without_calling_runtime():
    runtime = FakeADKRuntime(api_version="adk-python:2")
    response = ADKExecutionAdapter(runtime, expected_version="adk-python:1").execute(_request())

    assert response.result is None
    assert response.error is not None
    assert response.error.code == "ADK_VERSION_MISMATCH"


def test_external_tool_contract_requires_citation_and_explicit_side_effect_approval():
    no_citation = validate_tool_result(
        ADKToolResult(artifact_id="a", kind="tool", payload={}, citation_refs=())
    )
    denied = validate_tool_result(
        ADKToolResult(
            artifact_id="a",
            kind="tool",
            payload={},
            citation_refs=("cite-1",),
            side_effect=True,
            approved=False,
        )
    )
    approved = validate_tool_result(
        ADKToolResult(
            artifact_id="a",
            kind="tool",
            payload={},
            citation_refs=("cite-1",),
            side_effect=True,
            approved=True,
        )
    )

    assert no_citation is not None and no_citation.code == "TOOL_CITATION_REQUIRED"
    assert denied is not None and denied.code == "SIDE_EFFECT_DENIED"
    assert approved is None
