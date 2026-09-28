from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.pipeline.ai1_snapshot_adapter import adapt_ai1_input
from app.pipeline.ai2_batch import run_ai2_from_ai1_files
from app.pipeline.contract_context import build_contract_context
from app.pipeline.idp import run_idp
from app.pipeline.index import IndexStore
from app.pipeline.grounding import repair_active_nodes
from app.reasoning.query import QueryRouter
from app.tools.gateway import ToolGateway
from app.tools.store import InMemorySnapshotStore


DOWNLOADS = Path(r"C:\Users\dungs\Downloads")
DOC_001 = DOWNLOADS / "ocr-run-20260922-093747-doc-001.json"
DOC_002 = DOWNLOADS / "ocr-run-20260922-095540-doc-002.json"


@pytest.mark.integration
@pytest.mark.skipif(not DOC_002.exists(), reason="user-provided OCR-lab JSON file is not available")
def test_context_detects_appendix_pages_inside_one_contract():
    payload = json.loads(DOC_002.read_text(encoding="utf-8"))
    adapted = adapt_ai1_input(payload, scope_id="context-test:doc-002")
    context = build_contract_context(adapted.record)

    assert [(part.part_id, part.page_range) for part in context.parts] == [
        ("body", [1]),
        ("annex:01", [2, 3, 4]),
    ]
    link = [finding for finding in context.findings if finding.kind == "PART_LINK"]
    assert len(link) == 1
    assert link[0].review_state.value == "PASS"
    assert link[0].relation_type.value == "REFERENCES"


@pytest.mark.integration
@pytest.mark.skipif(not DOC_001.exists() or not DOC_002.exists(), reason="user-provided OCR-lab JSON files are not available")
def test_independent_contract_files_never_create_cross_document_context():
    result = run_ai2_from_ai1_files([DOC_001, DOC_002])
    assert result.relation_policy == "INDEPENDENT"
    assert result.model_dump()["cross_document_findings"] == []
    contexts = [item.job.contribution.contract_context for item in result.documents if item.job and item.job.contribution]
    assert len(contexts) == 2
    assert all(context.scope == "SINGLE_DOCUMENT" for context in contexts)
    assert contexts[0].source_file_ids != contexts[1].source_file_ids


@pytest.mark.integration
@pytest.mark.skipif(not DOC_002.exists(), reason="user-provided OCR-lab JSON file is not available")
def test_annex_query_reads_embedded_tables_not_only_outline_labels():
    payload = json.loads(DOC_002.read_text(encoding="utf-8"))
    adapted = adapt_ai1_input(payload, scope_id="context-query:doc-002")
    store = InMemorySnapshotStore()
    run_idp(adapted.record, adapted.envelope, store=store, index=IndexStore())
    result = QueryRouter(store, ToolGateway(store)).query(adapted.envelope, "Phụ lục 01 thay đổi giá thế nào?")

    assert result["review_state"] == "NEEDS_REVIEW"
    assert "Phụ lục 01" in (result.get("answer") or "")
    assert any("table-node:doc-002" in str(citation.get("node_id")) for citation in result.get("citations", []))


@pytest.mark.integration
@pytest.mark.skipif(not DOC_002.exists(), reason="user-provided OCR-lab JSON file is not available")
def test_workspace_repair_keeps_reconstructed_table_nodes():
    payload = json.loads(DOC_002.read_text(encoding="utf-8"))
    adapted = adapt_ai1_input(payload, scope_id="context-repair:doc-002")
    active, _issues = repair_active_nodes(adapted.record)
    active_ids = {node.node_id for node in active}
    assert {table.node_id for table in adapted.record.tables}.issubset(active_ids)


@pytest.mark.integration
@pytest.mark.skipif(not DOC_001.exists() or not DOC_002.exists(), reason="user-provided OCR-lab JSON files are not available")
def test_events_findings_and_party_questions_are_source_grounded():
    result = run_ai2_from_ai1_files([DOC_001, DOC_002])
    by_id = {item.document_id: item.job for item in result.documents}

    for document_id in ("doc-001", "doc-002"):
        job = by_id[document_id]
        assert job is not None and job.contribution is not None
        events = job.contribution.events
        assert events
        assert {event.event_type for event in events}.intersection({"PAYMENT", "DELIVERY", "ACCEPTANCE", "WARRANTY"})
        assert all(event.citation.node_id and event.citation.text_span for event in events)
        assert not any(issue.missing == "CITATION_VERIFICATION" and "event:" in issue.reason for issue in job.contribution.evidence_issues)

    context = by_id["doc-002"].contribution.contract_context
    assert context is not None
    assert any(finding.kind == "PART_LINK" for finding in context.findings)
    assert by_id["doc-002"].contribution.coverage["n_context_findings"] >= 1


@pytest.mark.integration
@pytest.mark.skipif(not DOC_001.exists() or not DOC_002.exists(), reason="user-provided OCR-lab JSON files are not available")
def test_party_and_annex_inventory_questions_distinguish_the_two_contracts():
    for path, expected_annex in (
        (DOC_001, "Không phát hiện tiêu đề"),
        (DOC_002, "Phát hiện 1 phụ lục"),
    ):
        payload = json.loads(path.read_text(encoding="utf-8"))
        adapted = adapt_ai1_input(payload, scope_id=f"ask-regression:{payload['document_id']}")
        store = InMemorySnapshotStore()
        run_idp(adapted.record, adapted.envelope, store=store, index=IndexStore())
        router = QueryRouter(store, ToolGateway(store))

        party = router.query(adapted.envelope, "Có bao nhiêu bên trong hợp đồng?")
        if path == DOC_001:
            assert party["review_state"] == "NEEDS_REVIEW"
            assert "2 vai trò" in party["answer"]
            assert "chưa có tên pháp nhân hoặc mst" in party["answer"].lower()
        else:
            assert party["review_state"] == "ANSWERED"
            assert "2 bên/pháp nhân được nhận diện" in party["answer"]
        assert party["citations"]
        assert party.get("grounded") is True
        assert all(citation.get("validation_status") == "VALID" for citation in party["citations"])

        party_card = router.query(adapted.envelope, "\u0042\u00ean \u0041 l\u00e0 ai?")
        if path == DOC_002:
            assert "MINH PHÁT" in party_card["answer"]
            assert party_card["review_state"] == "ANSWERED"
        else:
            assert "(không tách được tên)" in party_card["answer"]
            assert party_card["review_state"] == "NEEDS_REVIEW"

        annexes = router.query(adapted.envelope, "Có phụ lục nào không?")
        assert expected_annex in annexes["answer"]


@pytest.mark.integration
@pytest.mark.skipif(not DOC_002.exists(), reason="user-provided OCR-lab JSON file is not available")
def test_relation_retrieval_keeps_requested_clause_target():
    payload = json.loads(DOC_002.read_text(encoding="utf-8"))
    adapted = adapt_ai1_input(payload, scope_id="relation-target:doc-002")
    store = InMemorySnapshotStore()
    run_idp(adapted.record, adapted.envelope, store=store, index=IndexStore())
    router = QueryRouter(store, ToolGateway(store))

    result = router.query(adapted.envelope, "Điều 2 liên quan thế nào đến phụ lục 01?")
    citation_ids = {citation.get("node_id") for citation in result.get("citations") or []}

    assert "2" in citation_ids
    assert result["review_state"] == "NEEDS_REVIEW"
