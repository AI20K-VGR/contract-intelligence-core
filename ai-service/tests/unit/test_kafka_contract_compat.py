import hashlib
import json
from pathlib import Path

import pytest

from app.contracts import schema_validation
from app.pipeline.ai1_snapshot_adapter import adapt_be_ai2_processing_request


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _ocr_lab_snapshot() -> dict:
    text = "Dieu 1. Gia tri hop dong la 20.000.000 VND."
    return {
        "schema_version": "ai1.snapshot.v1",
        "snapshot_id": "snap-compat-001",
        "dossier_id": "dossier-compat-001",
        "document_id": "doc-compat-001",
        "run_id": "run-compat-001",
        "source_digest": "sha256:" + "a" * 64,
        "created_at": "2026-09-24T11:00:00Z",
        "execution": {
            "execution_manifest_id": "exec-compat-001",
            "config_digest": "b" * 64,
            "policy_digest": "c" * 64,
            "source_version_digest": "d" * 64,
            "replay": False,
        },
        "producer": {
            "engine_name": "ai1-ocr",
            "engine_version": "1",
            "model_version": "fixture",
            "preprocess_version": "fixture",
            "code_image_digest": "e" * 64,
        },
        "language": {
            "declared_scope": "vi",
            "detected_profile": "vi",
            "detector": {"name": "fixture", "version": "1"},
        },
        "status": "SUCCESS",
        "filename": "compat.pdf",
        "document_role": "contract",
        "input_type": "TEXT_LAYER",
        "engine": {"name": "pymupdf", "version": "1"},
        "page_count": 1,
        "processing_ms": 1,
        "pages": [
            {
                "page_number": 1,
                "status": "SUCCESS",
                "input_type": "TEXT_LAYER",
                "source_page_width": 595,
                "source_page_height": 842,
                "text": text,
                "lines": [
                    {
                        "line_id": "line-1",
                        "text": text,
                        "page_char_start": 0,
                        "page_char_end": len(text),
                        "bbox_normalized": [0.1, 0.1, 0.9, 0.2],
                        "geometry_provenance": "MEASURED",
                        "word_ids": [],
                    }
                ],
                "words": [],
                "blocks": [],
                "table_status": "NOT_PRESENT",
                "tables": [],
                "warnings": [],
            }
        ],
        "nodes": [],
        "table_continuity": [],
    }


def _request(snapshot: dict) -> dict:
    source_digest = snapshot["source_digest"]
    return {
        "schema_version": "be.ai2.processing.request.v1",
        "service_envelope": {
            "schema_version": "ai2.service-envelope.v1",
            "issuer": "backend-service",
            "audience": "vsf-ai2",
            "tenant_id": "tenant-a",
            "actor_id": "backend",
            "dossier_id": snapshot["dossier_id"],
            "scopes": ["ai2.process"],
            "key_id": "default",
            "issued_at": 1,
            "expires_at": 2,
            "nonce": "n" * 16,
            "payload_sha256": "f" * 64,
            "signature": "0" * 64,
        },
        "request_id": "req-compat-001",
        "idempotency_key": "idem-compat-001",
        "attempt": 1,
        "task_id": "task-compat-001",
        "dossier_id": snapshot["dossier_id"],
        "snapshots": [snapshot],
        "snapshot_identities": [
            {
                "snapshot_id": snapshot["snapshot_id"],
                "snapshot_version": "ai1.snapshot.v1",
                "source_digest": source_digest,
                "snapshot_digest": _digest(snapshot),
            }
        ],
        "dossier_members": [
            {
                "member_id": "mem-doc-compat-001",
                "document_id": snapshot["document_id"],
                "snapshot_id": snapshot["snapshot_id"],
                "role": "body",
                "source_digest": source_digest,
            }
        ],
        "role_relation_map": [
            {
                "relation_id": "rel-body-compat-001",
                "relation_type": "MEMBER_OF",
                "member_id": "mem-doc-compat-001",
                "related_member_id": None,
                "dossier_id": snapshot["dossier_id"],
            }
        ],
        "policy_flags": {
            "egress_allowed": False,
            "use_vector": False,
            "budget_limits": {
                "max_processing_seconds": 120,
                "max_llm_calls": 0,
                "max_embedding_tokens": 0,
            },
        },
    }


def test_kafka_boundary_accepts_current_ocr_lab_snapshot_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        schema_validation,
        "CONTRACT_ROOT",
        Path(__file__).resolve().parents[3].parent.parent / "docs" / "contracts",
    )

    snapshot = _ocr_lab_snapshot()
    request, adapted = adapt_be_ai2_processing_request(
        _request(snapshot), tenant_id="tenant-a", actor_id="backend"
    )

    assert request.snapshots[0]["source_digest"] == "a" * 64
    assert adapted.meta["adapter"] == "ocr-lab"
    assert adapted.record.pages[0].text == snapshot["pages"][0]["text"]
