from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app.llm.client import NineRouterClient
from app.pipeline.ai1_snapshot_adapter import adapt_ai1_input
from app.pipeline.ai2_batch import run_ai2_from_ai1_files


DOWNLOADS = Path(r"C:\Users\dungs\Downloads")
DOC_001 = DOWNLOADS / "ocr-run-20260922-093747-doc-001.json"
DOC_002 = DOWNLOADS / "ocr-run-20260922-095540-doc-002.json"


@pytest.mark.integration
@pytest.mark.skipif(not DOC_001.exists() or not DOC_002.exists(), reason="user-provided OCR-lab JSON files are not available")
def test_user_ocr_lab_snapshots_are_adapted_without_losing_structure():
    schema = json.loads((Path(__file__).parents[2] / "docs" / "contracts" / "ai1.snapshot.v1.ocr-lab.schema.json").read_text(encoding="utf-8"))
    for path, expected_pages, expected_tables in ((DOC_001, 8, 1), (DOC_002, 4, 3)):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert list(Draft202012Validator(schema).iter_errors(payload)) == []
        adapted = adapt_ai1_input(payload, scope_id=f"{payload['dossier_id']}:{payload['document_id']}")
        assert len(adapted.record.pages) == expected_pages
        assert len(adapted.record.tables) == expected_tables
        assert adapted.record.source_files[0].filename == payload["filename"]
        assert adapted.record.source_files[0].raw_digest == payload["source_digest"]
        assert any(issue.code == "STRUCTURE_DUPLICATE_NODE_ID" for issue in adapted.record.handoff_issues)
        if path == DOC_001:
            assert any(issue.code == "TABLE_INCOMPLETE_OR_EMPTY" for issue in adapted.record.handoff_issues)


@pytest.mark.integration
@pytest.mark.skipif(not DOC_001.exists() or not DOC_002.exists(), reason="user-provided OCR-lab JSON files are not available")
def test_user_ocr_lab_snapshots_run_in_independent_scopes():
    result = run_ai2_from_ai1_files([DOC_001, DOC_002])
    assert result.dossier_id == "dossier-001"
    assert result.model_dump()["cross_document_findings"] == []
    assert [item.document_id for item in result.documents] == ["doc-001", "doc-002"]
    assert all(item.job is not None for item in result.documents)
    assert all(item.job.status.value == "SUCCEEDED" for item in result.documents)
    assert all(item.job.review_state.value == "NEEDS_REVIEW" for item in result.documents)
    assert result.documents[0].meta["effective_dossier_id"] != result.documents[1].meta["effective_dossier_id"]


@pytest.mark.integration
@pytest.mark.skipif(not DOC_002.exists(), reason="user-provided OCR-lab JSON file is not available")
def test_claimed_table_geometry_cannot_be_promoted_to_pass():
    result = run_ai2_from_ai1_files([DOC_002])
    job = result.documents[0].job
    assert job is not None and job.contribution is not None
    assert any(issue.missing == "CITATION_VERIFICATION" for issue in job.contribution.evidence_issues)
    assert any(f.review_state.value == "NEEDS_REVIEW" for f in job.contribution.facts)


@pytest.mark.live
@pytest.mark.llm
@pytest.mark.integration
@pytest.mark.skipif(not DOC_001.exists() or not DOC_002.exists(), reason="user-provided OCR-lab JSON files are not available")
@pytest.mark.skipif(not NineRouterClient().configured(), reason="AI2 live LLM credentials are not configured")
def test_user_ocr_lab_snapshots_replay_with_real_llm():
    result = run_ai2_from_ai1_files([DOC_001, DOC_002], use_llm=True)
    assert not result.batch_issues
    assert len(result.documents) == 2
    assert all(item.error is None for item in result.documents)
    assert all(item.job is not None and item.job.status.value == "SUCCEEDED" for item in result.documents)
