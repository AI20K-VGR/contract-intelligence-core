from __future__ import annotations

import json
from pathlib import Path

from app.ai2 import PACKAGE_VERSION, process_files
from app.ai2.v1 import API_VERSION, INPUT_PROFILE, process_payloads, process_payloads_full


DOWNLOADS = Path(r"C:\Users\dungs\Downloads")
DOC_001 = DOWNLOADS / "ocr-run-20260922-093747-doc-001.json"
DOC_002 = DOWNLOADS / "ocr-run-20260922-095540-doc-002.json"


def test_versioned_package_exports_stable_api():
    assert PACKAGE_VERSION == "1.0.0"
    assert API_VERSION == "ai2.package.v1"
    assert INPUT_PROFILE == "ai1.snapshot.v1/ocr-lab"


def test_versioned_package_processes_user_files_when_present():
    if not DOC_001.exists() or not DOC_002.exists():
        return
    result = process_files([DOC_001, DOC_002])
    assert result.model_dump()["cross_document_findings"] == []
    assert [item.document_id for item in result.documents] == ["doc-001", "doc-002"]


def test_versioned_package_adapts_in_memory_payload():
    payload = json.loads(DOC_001.read_text(encoding="utf-8")) if DOC_001.exists() else {
        "schema_version": "ai1.snapshot.v1",
        "snapshot_id": "snap-1",
        "source_digest": "sha256:" + "a" * 64,
        "dossier_id": "dossier-1",
        "document_id": "doc-1",
        "filename": "doc.pdf",
        "document_role": "contract",
        "input_type": "TEXT_LAYER",
        "engine": {"name": "test", "version": "1"},
        "page_count": 1,
        "processing_ms": 1,
        "pages": [{"page_number": 1, "status": "SUCCESS", "input_type": "TEXT_LAYER", "source_page_width": 1, "source_page_height": 1, "text": "x", "lines": [], "words": [], "blocks": [], "table_status": "NOT_PRESENT", "tables": [], "warnings": [], "error": None}],
        "nodes": [],
        "table_continuity": [],
    }
    result = process_payloads([payload])
    assert len(result) == 1
    assert result[0].record.dossier_id.endswith(":doc-001") or result[0].record.dossier_id.endswith(":doc-1")


def test_versioned_package_runs_full_in_memory_payload():
    payload = json.loads(DOC_002.read_text(encoding="utf-8")) if DOC_002.exists() else None
    if payload is None:
        return
    result = process_payloads_full([payload])
    assert result.documents[0].job is not None
    assert result.documents[0].job.contribution is not None
    context = result.documents[0].job.contribution.contract_context
    assert context is not None
    assert any(part.part_id == "annex:01" for part in context.parts)
