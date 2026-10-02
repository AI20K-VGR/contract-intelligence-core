"""B5-order: when a result is BLOCKED, Backend reads ``errors[0].code`` as the
blocking reason, so BLOCKED issues lead and everything else keeps its order."""

from __future__ import annotations

import json
from pathlib import Path

from app.contracts.models import (
    HandoffIssue,
    IndexContribution,
    JobResult,
    JobStatus,
    ReviewState,
)
from app.contracts.wire import (
    BeAi2ProcessingRequest,
    job_result_to_wire,
    validate_processing_result,
)
from app.security.service_envelope import build_service_envelope

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "docs" / "contracts" / "examples"
RESULT_SCHEMA = ROOT / "docs" / "contracts" / "ai2.be.processing.result.v1.schema.json"


def _request() -> BeAi2ProcessingRequest:
    import hashlib

    body = json.loads((EXAMPLES / "ai1.snapshot.v1.body.example.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    payload = {
        "schema_version": "be.ai2.processing.request.v1",
        "request_id": "req-b5-001",
        "idempotency_key": "dossier-example-001:b5",
        "attempt": 1,
        "task_id": "process-dossier",
        "dossier_id": body["dossier_id"],
        "snapshots": [body],
        "snapshot_identities": [
            {
                "snapshot_id": body["snapshot_id"],
                "snapshot_version": "ai1.snapshot.v1",
                "source_digest": body["source_digest"],
                "snapshot_digest": digest,
            }
        ],
        "dossier_members": [
            {
                "member_id": "member-body-001",
                "document_id": body["document_id"],
                "snapshot_id": body["snapshot_id"],
                "role": "body",
                "source_digest": body["source_digest"],
            }
        ],
        "policy_flags": {
            "egress_allowed": False,
            "use_vector": False,
            "budget_limits": {"max_processing_seconds": 60, "max_llm_calls": 0, "max_embedding_tokens": 0},
        },
    }
    payload["service_envelope"] = build_service_envelope(
        payload, secret="test-secret", tenant_id="tenant_a", dossier_id=body["dossier_id"]
    )
    return BeAi2ProcessingRequest.model_validate(payload)


def _issue(code: str, state: ReviewState) -> HandoffIssue:
    return HandoffIssue(code=code, message=f"{code} message", review_state=state)


def _job(issues: list[HandoffIssue], *, error: str | None = None) -> JobResult:
    return JobResult(
        job_id="job-b5-001",
        status=JobStatus.SUCCEEDED,
        review_state=ReviewState.BLOCKED,
        handoff_issues=issues,
        contribution=IndexContribution(extraction_version=1, proposed_index_version="idx_b5"),
        error=error,
    )


def test_blocked_issue_leads_errors_and_others_keep_order():
    issues = [
        _issue("REVIEW_A", ReviewState.NEEDS_REVIEW),
        _issue("GAP_B", ReviewState.INSUFFICIENT_EVIDENCE),
        _issue("BLOCK_C", ReviewState.BLOCKED),
        _issue("REVIEW_D", ReviewState.NEEDS_REVIEW),
        _issue("BLOCK_E", ReviewState.BLOCKED),
    ]
    request = _request()

    wire = job_result_to_wire(_job(issues), request)

    assert wire["status"] == "SUCCEEDED"
    assert wire["review_state"] == "BLOCKED"
    assert [item["code"] for item in wire["errors"]] == [
        "BLOCK_C",
        "BLOCK_E",
        "REVIEW_A",
        "GAP_B",
        "REVIEW_D",
    ]
    validate_processing_result(wire, request=request)


def test_job_failure_error_stays_last():
    issues = [
        _issue("REVIEW_A", ReviewState.NEEDS_REVIEW),
        _issue("BLOCK_B", ReviewState.BLOCKED),
    ]
    request = _request()

    wire = job_result_to_wire(_job(issues, error="worker crashed"), request)

    assert [item["code"] for item in wire["errors"]] == ["BLOCK_B", "REVIEW_A", "AI2_JOB_FAILED"]
    validate_processing_result(wire, request=request)


def test_order_is_unchanged_without_blocked_issue():
    issues = [_issue("REVIEW_A", ReviewState.NEEDS_REVIEW), _issue("GAP_B", ReviewState.INSUFFICIENT_EVIDENCE)]

    wire = job_result_to_wire(_job(issues), _request())

    assert [item["code"] for item in wire["errors"]] == ["REVIEW_A", "GAP_B"]


def test_result_schema_documents_errors_order_convention():
    schema = json.loads(RESULT_SCHEMA.read_text(encoding="utf-8"))
    description = schema["properties"]["errors"].get("description", "")

    assert "errors[0]" in description
    assert "BLOCKED" in description
    assert "SUCCEEDED" in description
