from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app
from app.pipeline.ai1_snapshot_adapter import adapt_ai1_input


def _result(*, clauses: list[dict] | None = None, tables: list[dict] | None = None, facts: list[dict] | None = None) -> dict:
    document_id = "doc-result"
    line_id = f"{document_id}:1:0"
    citation_id = "cite-line-1"
    page = {
        "document_id": document_id,
        "sha256": "a" * 64,
        "role": "contract",
        "storage_key": "contract.pdf",
        "page_count": 1,
        "page_number": 1,
        "width": 1000,
        "height": 1400,
        "rotation": 0,
        "image_key": "page-1.png",
        "lines": [{"id": line_id, "text": "HOP DONG SO 01 BEN A CONG TY ABC", "bbox": [0.1, 0.1, 0.8, 0.2], "words": []}],
        "tables": tables or [],
        "engine": "test",
        "status": "completed",
        "issue": None,
    }
    machine = {
        "schema_version": "0.1",
        "run_id": "run-result",
        "dossier_id": "source-dossier",
        "is_partial": False,
        "review_required": True,
        "coverage": {"expected_pages": 1, "completed_pages": 1, "failed_pages": 0, "coverage_complete": True, "processing_complete": True},
        "documents": [{"document_id": document_id, "sha256": "a" * 64, "role": "contract", "storage_key": "contract.pdf", "page_count": 1}],
        "pages": [page],
        "clauses": clauses or [],
        "tables": tables or [],
        "facts": facts or [],
        "findings": [],
        "issues": [],
        "limitations": [],
        "citations": [{"id": citation_id, "run_id": "run-result", "document_id": document_id, "source_hash": "a" * 64, "page_number": 1, "line_id": line_id, "quote": page["lines"][0]["text"], "bbox": [0.1, 0.1, 0.8, 0.2], "coordinate_system": "normalized_top_left_rendered_page", "geometry_source": "test", "precision": "line"}],
    }
    return {"machine": machine, "effective": machine, "effective_result_hash": "b" * 64, "review": {}, "review_version": 1, "status": "pending_review", "result_hash": "b" * 64}


def test_result_v01_maps_clause_fact_citation_and_pending_review():
    payload = _result(
        clauses=[{"id": "clause-1", "type": "article", "label": "Dieu 1. Noi dung", "parent_id": None, "document_id": "doc-result", "citation_ids": ["cite-line-1"]}],
        facts=[{"id": "fact-a", "type": "party_a", "raw": "Cong ty ABC", "normalized": {"name": "Cong ty ABC"}, "document_id": "doc-result", "source_role": "contract", "context": {"source_line": "BEN A: Cong ty ABC"}, "citation_ids": ["cite-line-1"], "confidence": {"signals": {"source_resolved": True}}}],
    )
    result = adapt_ai1_input(payload)
    assert result.meta["source"] == "ai1.result.v0.1"
    assert result.record.dossier_id.startswith("ai1-result:")
    assert len(result.record.pages) == 1
    assert any(node.type == "CLAUSE" for node in result.record.nodes)
    assert result.record.facts[0].role == "party_a"
    assert result.record.facts[0].citation.validation_status == "VALID"
    assert result.record.input_facts is not None
    assert [fact.fact_id for fact in result.record.input_facts] == ["fact-a"]
    assert result.record.citation_index["cite-line-1"].quote_sha256


def test_legacy_result_remains_explicit_compatibility_adapter():
    result = adapt_ai1_input(_result())

    assert result.meta["adapter"] == "legacy-result-v0.1"
    assert result.meta["source"] == "ai1.result.v0.1"
    assert any(issue.code == "AI1_PENDING_REVIEW" for issue in result.record.handoff_issues)


def test_result_derived_facts_are_not_marked_as_ai1_input_facts():
    payload = _result()
    line = payload["machine"]["pages"][0]["lines"][0]
    line["text"] = "BEN A: CONG TY ABC. Ma so thue: 0101234567"
    payload["machine"]["citations"][0]["quote"] = line["text"]

    result = adapt_ai1_input(payload)

    assert result.record.input_facts == []
    assert result.record.facts
    assert all(fact.provenance.startswith("AI2_") for fact in result.record.facts)


def test_result_citation_uses_referenced_duplicate_line():
    payload = _result()
    page = payload["machine"]["pages"][0]
    first = page["lines"][0]
    second = {**first, "id": "doc-result:1:1"}
    page["lines"] = [first, second]
    payload["machine"]["citations"][0]["line_id"] = second["id"]
    payload["machine"]["citations"][0]["quote"] = second["text"]

    result = adapt_ai1_input(payload)

    citation = result.record.citation_index["cite-line-1"]
    assert citation.line_ids == [second["id"]]
    assert citation.validation_status == "VALID"


def test_result_derives_contract_number_value_and_payment_schedule():
    payload = _result()
    page = payload["machine"]["pages"][0]
    lines = [
        {"id": "doc-result:1:0", "text": "SO: 12/2026/HD-DV/MH-TT", "bbox": [0.1, 0.1, 0.8, 0.2], "words": []},
        {"id": "doc-result:1:1", "text": "Tong gia tri tam tinh: 125.000.000 dong", "bbox": [0.1, 0.2, 0.8, 0.3], "words": []},
        {"id": "doc-result:1:2", "text": "Tien do thanh toan: 30% tam ung, 40% sau khi ban giao, 30% sau nghiem thu.", "bbox": [0.1, 0.3, 0.8, 0.4], "words": []},
    ]
    page["lines"] = lines
    payload["machine"]["citations"] = [
        {
            "id": f"cite-{index}",
            "run_id": "run-result",
            "document_id": "doc-result",
            "source_hash": "a" * 64,
            "page_number": 1,
            "line_id": line["id"],
            "quote": line["text"],
            "bbox": line["bbox"],
            "coordinate_system": "normalized_top_left_rendered_page",
            "geometry_source": "test",
            "precision": "line",
        }
        for index, line in enumerate(lines)
    ]

    result = adapt_ai1_input(payload)
    derived = {fact.role: fact for fact in result.record.facts}

    assert derived["contract_number"].raw_value == "12/2026/HD-DV/MH-TT"
    assert derived["contract_value"].raw_value == "125.000.000"
    assert "30% tam ung" in derived["payment_schedule"].raw_value
    assert all(derived[key].citation.validation_status == "VALID" for key in ("contract_number", "contract_value", "payment_schedule"))


def test_result_without_clauses_uses_degraded_blocks_and_keeps_tables_separate():
    table = {"id": "table-1", "document_id": "doc-result", "page_number": 1, "row_count": 1, "col_count": 1, "bbox": [0.1, 0.3, 0.8, 0.5], "rows": [{"row_index": 0, "cells": [{"col_index": 0, "text": "A", "bbox": [0.1, 0.3, 0.8, 0.4], "inferred": False}]}], "continues_table_id": None, "continued_by_table_id": "table-2"}
    result = adapt_ai1_input(_result(tables=[table]))
    assert not any(node.type == "CLAUSE" for node in result.record.nodes)
    assert any(node.type == "UNNUMBERED_BLOCK" for node in result.record.nodes)
    assert len(result.record.tables) == 1
    assert result.record.tables[0].continuation is True
    assert any(issue.code == "TABLE_CONTINUATION_REVIEW" for issue in result.record.handoff_issues)


def test_result_api_runs_deterministic_and_verifies_citation():
    client = TestClient(app)
    response = client.post("/api/workspace/ai1-result", json=_result(
        facts=[{"id": "fact-a", "type": "party_a", "raw": "Cong ty ABC", "normalized": {"name": "Cong ty ABC"}, "document_id": "doc-result", "source_role": "contract", "context": {}, "citation_ids": ["cite-line-1"], "confidence": {"signals": {"source_resolved": True}}}],
    ))
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "ai1_result"
    assert body["review_queue_status"] == "NOT_RUN"
    sid = body["session_id"]
    extracted = client.post(f"/api/workspace/{sid}/extract", json={"use_llm": False})
    assert extracted.status_code == 200
    assert extracted.json()["job"]["status"] == "SUCCEEDED"
    assert extracted.json()["review_queue_status"] == "HAS_REVIEW_ITEMS"
    asked = client.post(f"/api/workspace/{sid}/ask", json={"query": "Thông tin bên A?", "use_llm": False})
    assert asked.status_code == 200
    answer_citations = asked.json()["citations"]
    assert answer_citations and answer_citations[0]["citation_id"] == "cite-line-1"
    assert answer_citations[0]["validation_status"] == "VALID"
    verified = client.post(f"/api/workspace/{sid}/citations/cite-line-1/verify")
    assert verified.status_code == 200
    assert verified.json()["valid"] is True
    publish = client.post(f"/api/workspace/{sid}/publish", json={"confirm": True})
    assert publish.status_code == 409


def test_result_and_snapshot_workspace_lanes_do_not_accept_each_other():
    client = TestClient(app)

    result_to_snapshot = client.post("/api/workspace/ai1-snapshot", json=_result())
    assert result_to_snapshot.status_code == 422
    assert result_to_snapshot.json()["detail"]["code"] == "WRONG_INPUT_LANE"

    snapshot_to_result = client.post(
        "/api/workspace/ai1-result",
        json={"schema_version": "ai1.snapshot.v1", "pages": []},
    )
    assert snapshot_to_result.status_code == 422
    assert snapshot_to_result.json()["detail"]["code"] == "WRONG_INPUT_LANE"
