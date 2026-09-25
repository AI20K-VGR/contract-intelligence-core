from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.pipeline.ai1_snapshot_adapter import SnapshotContractError, adapt_ai2_request


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_EXAMPLES = ROOT / "docs" / "contracts" / "examples"


def _request() -> dict:
    body = json.loads((CONTRACT_EXAMPLES / "ai1.snapshot.v1.body.example.json").read_text(encoding="utf-8"))
    annex = json.loads((CONTRACT_EXAMPLES / "ai1.snapshot.v1.annex.example.json").read_text(encoding="utf-8"))
    return {
        "schema_version": "ai2.idp.request.v1",
        "task_id": "task-contract-example-001",
        "attempt_id": "attempt-contract-example-001",
        "manifest": {
            "schema_version": "ai1.dossier-manifest.v1",
            "manifest_id": "manifest-example-001",
            "dossier_id": "dossier-example-001",
            "documents": [
                {
                    "document_id": body["document_id"],
                    "snapshot_id": body["snapshot_id"],
                    "role": "body",
                    "source_digest": body["source_digest"],
                },
                {
                    "document_id": annex["document_id"],
                    "snapshot_id": annex["snapshot_id"],
                    "role": "annex",
                    "source_digest": annex["source_digest"],
                },
            ],
        },
        "snapshots": [body, annex],
    }


def test_canonical_request_accepts_official_examples_and_manifest_roles():
    result = adapt_ai2_request(_request())

    assert result.meta["source"] == "ai2.idp.request.v1"
    assert result.meta["snapshot_ids"] == [
        "snap-body-example-001",
        "snap-annex-example-001",
    ]
    assert {item.file_id: item.role for item in result.record.source_files} == {
        "doc-body-example-001": "body",
        "doc-annex-example-001": "annex",
    }
    assert result.record.dossier_id == "dossier-example-001"
    assert len(result.record.pages) == 2


def test_canonical_request_rejects_unknown_root_field():
    payload = _request()
    payload["unexpected"] = True

    with pytest.raises(SnapshotContractError) as exc:
        adapt_ai2_request(payload)

    assert exc.value.code == "REQUEST_SCHEMA_INVALID"


def test_canonical_snapshot_rejects_missing_required_provenance():
    payload = _request()
    del payload["snapshots"][0]["created_at"]

    with pytest.raises(SnapshotContractError) as exc:
        adapt_ai2_request(payload)

    assert exc.value.code == "REQUEST_SCHEMA_INVALID"


def test_canonical_request_rejects_manifest_source_mismatch():
    payload = _request()
    payload["manifest"]["documents"][0]["source_digest"] = "f" * 64

    with pytest.raises(SnapshotContractError) as exc:
        adapt_ai2_request(payload)

    assert exc.value.code == "REQUEST_MEMBERSHIP_INVALID"


def test_canonical_request_rejects_non_v1_snapshot():
    payload = _request()
    snapshot = copy.deepcopy(payload["snapshots"][0])
    snapshot["schema_version"] = "ai1.snapshot.invalid"
    payload["snapshots"] = [snapshot]
    payload["manifest"]["documents"] = [payload["manifest"]["documents"][0]]

    with pytest.raises(SnapshotContractError) as exc:
        adapt_ai2_request(payload)

    assert exc.value.code == "REQUEST_SCHEMA_INVALID"


def test_canonical_request_requires_exactly_one_body_document():
    payload = _request()
    for document in payload["manifest"]["documents"]:
        document["role"] = "annex"

    with pytest.raises(SnapshotContractError) as exc:
        adapt_ai2_request(payload)

    assert exc.value.code == "REQUEST_SCHEMA_INVALID"


def test_canonical_semantics_reject_duplicate_page_revision_across_documents():
    payload = _request()
    payload["snapshots"][1]["pages"][0]["page_revision_id"] = payload["snapshots"][0]["pages"][0]["page_revision_id"]

    with pytest.raises(SnapshotContractError) as exc:
        adapt_ai2_request(payload)

    assert exc.value.code == "REQUEST_SEMANTIC_INVALID"


def test_canonical_semantics_rejects_reversed_bbox():
    payload = _request()
    payload["snapshots"][0]["pages"][0]["lines"] = [
        {
            "line_id": "line-1",
            "raw_text": "Noi dung",
            "bbox": [0.8, 0.2, 0.1, 0.3],
            "bbox_source": "native",
            "geometry_status": "measured",
            "words": [],
        }
    ]

    with pytest.raises(SnapshotContractError) as exc:
        adapt_ai2_request(payload)

    assert exc.value.code == "SNAPSHOT_SEMANTIC_INVALID"


def test_canonical_adapter_does_not_accept_ocr_lab_producer_shape():
    payload = _request()
    producer_shape = {
        "schema_version": "ai1.snapshot.v1",
        "snapshot_id": "ocr-lab-snapshot",
        "source_digest": "sha256:" + "a" * 64,
        "dossier_id": payload["manifest"]["dossier_id"],
        "document_id": "doc-ocr-lab",
        "filename": "contract.json",
        "document_role": "contract",
        "input_type": "TEXT_LAYER",
        "engine": {"name": "ocr-lab", "version": "1"},
        "page_count": 1,
        "processing_ms": 1,
        "pages": [],
        "nodes": [],
        "table_continuity": [],
    }
    payload["snapshots"] = [producer_shape]
    payload["manifest"]["documents"] = [
        {
            "document_id": producer_shape["document_id"],
            "snapshot_id": producer_shape["snapshot_id"],
            "role": "body",
            "source_digest": "a" * 64,
        }
    ]

    with pytest.raises(SnapshotContractError) as exc:
        adapt_ai2_request(payload)

    assert exc.value.code == "REQUEST_SCHEMA_INVALID"
