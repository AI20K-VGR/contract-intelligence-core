from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.contracts.wire import validate_processing_result
from app.pipeline.ai1_snapshot_adapter import (
    SnapshotContractError,
    adapt_ai1_input,
    adapt_be_ai2_processing_request,
    adapt_snapshot_v1,
)
from app.security.service_envelope import build_service_envelope
from app.tools.jobs import JobPayloadConflict, SQLiteJobStore


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "docs" / "contracts" / "examples"
ARTIFACT = ROOT / "plans" / "260923-1023-ai2-long-running-architecture" / "artifacts" / "p0-contract-baseline.json"


def _snapshot(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def _processing_request() -> dict:
    body = _snapshot("ai1.snapshot.v1.body.example.json")
    annex = _snapshot("ai1.snapshot.v1.annex.example.json")
    payload = {
        "schema_version": "be.ai2.processing.request.v1",
        "request_id": "req-p0-001",
        "idempotency_key": "p0-dossier:attempt-1",
        "attempt": 1,
        "task_id": "process-dossier",
        "dossier_id": body["dossier_id"],
        "snapshots": [body, annex],
        "snapshot_identities": [
            {
                "snapshot_id": item["snapshot_id"],
                "snapshot_version": "ai1.snapshot.v1",
                "source_digest": item["source_digest"],
                "snapshot_digest": hashlib.sha256(
                    json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest(),
            }
            for item in (body, annex)
        ],
        "dossier_members": [
            {
                "member_id": "member-body-p0",
                "document_id": body["document_id"],
                "snapshot_id": body["snapshot_id"],
                "role": "body",
                "source_digest": body["source_digest"],
            },
            {
                "member_id": "member-annex-p0",
                "document_id": annex["document_id"],
                "snapshot_id": annex["snapshot_id"],
                "role": "annex",
                "source_digest": annex["source_digest"],
            },
        ],
        "role_relation_map": [
            {
                "relation_id": "relation-annex-p0",
                "relation_type": "ANNEX_OF",
                "member_id": "member-annex-p0",
                "related_member_id": "member-body-p0",
                "dossier_id": body["dossier_id"],
            }
        ],
        "policy_flags": {
            "egress_allowed": False,
            "use_vector": False,
            "budget_limits": {
                "max_processing_seconds": 300,
                "max_llm_calls": 0,
                "max_embedding_tokens": 0,
            },
        },
    }
    payload["service_envelope"] = build_service_envelope(
        payload,
        secret="test-secret",
        tenant_id="tenant_p0",
        dossier_id=payload["dossier_id"],
        actor_id="test-backend-p0",
    )
    return payload


def test_p0_artifact_freezes_decisions_and_executable_case_refs():
    baseline = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    assert baseline["schema"] == "ai2.p0.contract-baseline/v1"
    assert baseline["phase"] == "P0"
    assert baseline["producer_change"] == "none"
    assert baseline["public_schema_change"] == "none"
    assert baseline["decision_record"]["status"] == "approved"
    assert len(baseline["decision_record"]["areas"]) == 8
    assert {case["id"] for case in baseline["contract_cases"]} == {
        "current-ai1-snapshot",
        "legacy-ocr-json",
        "missing-evidence",
        "multiple-logical-documents",
        "unsupported-version",
        "duplicate-submit",
    }


def test_current_ai1_snapshot_and_legacy_ocr_json_stay_separate_compatibility_lanes():
    canonical = adapt_ai1_input(_snapshot("ai1.snapshot.v1.body.example.json"))
    assert canonical.meta["source"] == "ai1.snapshot.v1"
    assert canonical.record.source_files[0].file_id == "doc-body-example-001"
    assert canonical.record.pages[0].source_hash == "a" * 64

    legacy = adapt_ai1_input(
        {
            "document_id": "legacy-p0",
            "filename": "contract.ocr.json",
            "page_count": 1,
            "full_text": "Dieu 1\nNoi dung",
            "pages": [
                {
                    "page_number": 1,
                    "status": "SUCCESS",
                    "input_type": "TEXT_LAYER",
                    "text": "Dieu 1\nNoi dung",
                    "geometry_available": False,
                }
            ],
        }
    )
    assert legacy.meta["source"] == "legacy_ocr_json"
    assert legacy.record.source_files[0].file_id == "legacy-p0"
    assert any(issue.code == "LEGACY_TEXT_ONLY" for issue in legacy.record.handoff_issues)


def test_unknown_fields_are_rejected_on_canonical_snapshot_boundary():
    payload = _snapshot("ai1.snapshot.v1.body.example.json")
    payload["unexpected_p0_field"] = True

    with pytest.raises(SnapshotContractError) as exc:
        adapt_snapshot_v1(payload)

    assert exc.value.code == "SNAPSHOT_SCHEMA_INVALID"


def test_missing_document_reference_is_rejected_before_multi_document_adaptation():
    payload = _processing_request()
    payload["dossier_members"][0]["document_id"] = "missing-document"

    with pytest.raises(SnapshotContractError) as exc:
        adapt_be_ai2_processing_request(payload)

    assert exc.value.code == "REQUEST_MEMBERSHIP_INVALID"


def test_multiple_logical_documents_preserve_members_and_explicit_relation():
    _, adapted = adapt_be_ai2_processing_request(_processing_request())

    assert {item.file_id for item in adapted.record.source_files} == {
        "doc-body-example-001",
        "doc-annex-example-001",
    }
    assert adapted.meta["role_relation_map"][0]["relation_type"] == "ANNEX_OF"


def test_unsupported_snapshot_version_fails_closed():
    payload = _snapshot("ai1.snapshot.v1.body.example.json")
    payload["schema_version"] = "ai1.snapshot.v9"

    with pytest.raises(SnapshotContractError) as exc:
        adapt_ai1_input(payload)

    assert exc.value.code == "UNSUPPORTED_SNAPSHOT_VERSION"


def test_duplicate_submit_returns_same_job_and_conflicting_payload_is_rejected(tmp_path):
    store = SQLiteJobStore(tmp_path / "p0-jobs.sqlite")
    request = {"request_id": "req-p0-001"}
    wire = {"schema_version": "ai2.be.processing.result.v1"}
    first, created = store.create_or_get(
        tenant_id="tenant_p0",
        dossier_id="dossier-p0",
        request_id="req-p0-001",
        idempotency_key="idem-p0",
        attempt=1,
        request=request,
        wire=wire,
        request_fingerprint="a" * 64,
    )
    duplicate, duplicate_created = store.create_or_get(
        tenant_id="tenant_p0",
        dossier_id="dossier-p0",
        request_id="retry-p0",
        idempotency_key="idem-p0",
        attempt=1,
        request={"request_id": "retry-p0"},
        wire=wire,
        request_fingerprint="a" * 64,
    )

    assert created is True
    assert duplicate_created is False
    assert duplicate["job_id"] == first["job_id"]

    with pytest.raises(JobPayloadConflict):
        store.create_or_get(
            tenant_id="tenant_p0",
            dossier_id="dossier-p0",
            request_id="different-p0",
            idempotency_key="idem-p0",
            attempt=1,
            request={"request_id": "different-p0"},
            wire=wire,
            request_fingerprint="b" * 64,
        )


def test_missing_citation_is_not_a_succeeded_processing_result():
    payload = {
        "schema_version": "ai2.be.processing.result.v1",
        "request_id": "req-p0-001",
        "idempotency_key": "idem-p0",
        "attempt": 1,
        "job_id": "job-p0-001",
        "status": "SUCCEEDED",
        "review_state": "PASS",
        "input_snapshots": [
            {
                "snapshot_id": "snap-p0-001",
                "snapshot_version": "ai1.snapshot.v1",
                "source_digest": "a" * 64,
                "snapshot_digest": "b" * 64,
            }
        ],
        "result": {
            "facts": [
                {
                    "fact_id": "fact-p0",
                    "raw_value": "100",
                    "normalized_value": None,
                    "subject": None,
                    "role": None,
                    "unit": None,
                    "currency": None,
                    "vat_basis": None,
                    "condition": None,
                    "scope": None,
                    "validity": None,
                    "item_key": None,
                    "tax_basis": None,
                    "period_start": None,
                    "source_role": None,
                    "provenance": "AI1",
                    "review_state": "PASS",
                    "citation_ids": ["missing-citation"],
                }
            ],
            "findings": [],
            "citations": [],
            "index_contribution": {
                "state": "propose",
                "chunks": [],
                "evidence_issues": [],
                "coverage": {},
                "extraction_version": 1,
                "proposed_index_version": "idx-p0",
                "contract_context": None,
            },
        },
        "errors": [],
    }

    with pytest.raises(SnapshotContractError) as exc:
        validate_processing_result(payload)

    assert exc.value.code == "RESULT_SEMANTIC_INVALID"
