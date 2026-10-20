from copy import deepcopy

import pytest

from tests.test_ai1_result_v01 import _result
from app.pipeline.ai1_snapshot_adapter import adapt_ai1_input, SnapshotContractError
from app.pipeline.citations import CitationResolver
from app.pipeline.idp import run_idp
from app.pipeline.table_headers import parse_amount
from app.tools.persist import record_to_dict, record_from_dict


def table(table_id="table-a", rows=None, page=1):
    rows = rows or [["STT", "Mo ta", "Thanh tien"], ["1", "Vat tu", "2.500.000"], ["2", "Service", "0"], ["3", "Missing", ""]]
    return {"id": table_id, "document_id": "doc-result", "page_number": page,
            "bbox": [0.1, 0.3, 0.9, 0.8], "row_count": len(rows), "col_count": len(rows[0]),
            "rows": [{"row_index": r, "cells": [{"col_index": c, "text": value,
                       "bbox": [0.1 + c * 0.2, 0.3 + r * 0.1, 0.2 + c * 0.2, 0.35 + r * 0.1]}
                      for c, value in enumerate(row)]} for r, row in enumerate(rows)]}


def test_all_cells_have_global_ids_and_exact_cell_evidence():
    result = adapt_ai1_input(_result(tables=[table(), table("table-b")]))
    rec = result.record
    cell_cites = [c for c in rec.citation_index.values() if c.cell_id]
    assert len(cell_cites) == 24
    assert all(c.citation_id in rec.citation_index for c in cell_cites)
    resolver = CitationResolver(rec.pages, rec.tables)
    citation = rec.tables[0].cell_citations["1:2"]
    assert resolver.verify(citation).valid
    assert citation.line_ids == [] and citation.char_start is None
    assert not resolver.verify(citation.model_copy(update={"text_span": "forged"})).valid
    assert not resolver.verify(citation.model_copy(update={"cell_id": "missing"})).valid
    assert not resolver.verify(citation.model_copy(update={"source_hash": "f" * 64})).valid


def test_amount_column_missing_zero_and_rerun_survive_reload():
    a = adapt_ai1_input(_result(tables=[table()]))
    run_idp(a.record, a.envelope)
    facts = a.record.facts
    assert [f.raw_value for f in facts] == ["2.500.000", "0", "MISSING"]
    assert [f.normalized_value for f in facts] == ["2500000", "0", None]
    assert facts[0].role == "line_amount"  # 'vat tu' is not VAT tax.
    assert facts[0].citation.cell_id.endswith(":r1:c2")
    before = [(f.fact_id, f.raw_value, f.citation.citation_id) for f in facts]
    restored = record_from_dict(record_to_dict(a.record))
    run_idp(restored, a.envelope)
    assert [(f.fact_id, f.raw_value, f.citation.citation_id) for f in restored.facts] == before


def test_effective_content_changes_revision_even_with_same_declared_hash():
    payload = _result(tables=[table()])
    original = deepcopy(payload)
    a = adapt_ai1_input(payload)
    assert payload == original
    changed = deepcopy(payload)
    changed["effective"]["tables"][0]["rows"][1]["cells"][2]["text"] = "9.000.000"
    b = adapt_ai1_input(changed)
    assert a.meta["result_hash"] == b.meta["result_hash"]
    assert a.record.pins.source_snapshot_digest != b.record.pins.source_snapshot_digest
    assert a.record.pages[0].page_revision_id != b.record.pages[0].page_revision_id
    assert not CitationResolver(b.record.pages, b.record.tables).verify(a.record.tables[0].cell_citations["1:2"]).valid


@pytest.mark.parametrize("inventory", ["tables", "citations", "pages"])
def test_duplicate_evidence_rejected(inventory):
    payload = _result(tables=[table()])
    payload["effective"][inventory].append(deepcopy(payload["effective"][inventory][0]))
    with pytest.raises(SnapshotContractError):
        adapt_ai1_input(payload)


def test_headerless_table_does_not_guess_amount_column():
    a = adapt_ai1_input(_result(tables=[table(rows=[["A", "Description", "100"]])]))
    r = run_idp(a.record, a.envelope)
    assert r.contribution.facts == []
    assert any(i.code == "TABLE_HEADER_UNRESOLVED" for i in r.handoff_issues)


def test_ambiguous_decimal_and_nonfinite_are_not_numbers():
    assert parse_amount("240.000") is None
    assert parse_amount("NaN") is None
    assert parse_amount("Infinity") is None
    assert parse_amount("-1.250.000") == "-1250000"


def test_partial_llm_row_output_triggers_fallback():
    from app.pipeline.table import TablePipeline
    assert TablePipeline._needs_fallback({"rows_out": [{"row_index": 0, "raw": "1", "normalized": "1", "missing": False}]}, {"n_rows": 2})


def test_annex_continuation_uses_scope_without_merging_raw_evidence():
    payload = _result(tables=[table()])
    first_page = payload["effective"]["pages"][0]
    first_page["lines"][0]["text"] = "PHU LUC 01 - BANG GIA"
    payload["effective"]["citations"][0]["quote"] = first_page["lines"][0]["text"]
    payload["effective"]["clauses"] = [{"id": "heading", "type": "fragment", "label": first_page["lines"][0]["text"], "document_id": "doc-result", "citation_ids": ["cite-line-1"]}]
    second_page = deepcopy(first_page)
    second_page["page_number"] = 2
    second_page["lines"] = [{"id": "page2", "text": "Continuation", "bbox": [0.1, 0.8, 0.8, 0.9]}]
    payload["effective"]["pages"].append(second_page)
    payload["effective"]["tables"].append(table("table-b", rows=[["4", "Next item", "3.000.000"]], page=2))
    original = deepcopy(payload)
    a = adapt_ai1_input(payload)
    assert payload == original
    assert a.record.tables[1].header_source_table_id == "table-a"
    assert a.record.tables[1].rows == [["4", "Next item", "3.000.000"]]
    assert a.record.tables[1].source_role == "annex"
    assert a.record.tables[0].section_scope == a.record.tables[1].section_scope
    from app.tools.store import InMemorySnapshotStore
    from app.tools.gateway import ToolGateway
    from app.reasoning.query import QueryRouter
    store = InMemorySnapshotStore()
    run_idp(a.record, a.envelope, store=store)
    answer = QueryRouter(store, ToolGateway(store)).query(a.envelope, "Phụ lục 1 gồm gì?")
    assert answer["l0_notes"] != "annex_missing"
    assert any(i.code == "TABLE_CONTINUATION_REVIEW" for i in a.record.handoff_issues)


def test_party_tax_code_does_not_include_street_number():
    from app.reasoning.ask_assemble import assemble_party
    result = assemble_party("A", [{"node_id": "party", "type": "FIELD", "structured_key": "party_a",
        "structured_value": "Cong ty Test. So 15, Duong ABC. Ma so thue: 0101234567."}], [], [])
    assert "MST: 0101234567" in result["answer"]
    assert "150101234567" not in result["answer"]


def test_annex_mention_is_not_document_role():
    from app.reasoning.relations import doc_side
    assert doc_side(["Hợp đồng", "Điều 1"], "Dich vu doi soat phu luc") == "Thân HĐ"


def test_existing_nested_clause_parent_is_preserved():
    payload = _result(clauses=[
        {"id": "article", "type": "article", "label": "Dieu 1", "citation_ids": ["cite-line-1"]},
        {"id": "subclause", "type": "clause", "label": "1.1", "parent_id": "article", "citation_ids": ["cite-line-1"]},
    ])
    a = adapt_ai1_input(payload)
    assert next(n for n in a.record.evidence_nodes() if n.node_id == "subclause").parent_id == "article"


def test_requested_subspan_rebuilds_hash_and_offsets():
    from app.reasoning.l3_ground import L3Ground
    from app.tools.store import InMemorySnapshotStore
    from app.tools.gateway import ToolGateway
    payload = _result(clauses=[{"id": "clause", "type": "article", "label": "HOP DONG SO 01 BEN A CONG TY ABC", "citation_ids": ["cite-line-1"]}])
    a = adapt_ai1_input(payload)
    store = InMemorySnapshotStore()
    store.put(a.record)
    citations = L3Ground(ToolGateway(store))._normalize_citations(a.envelope, [{"node_id": "clause", "text_span": "CONG TY ABC"}], {"clause"})
    assert citations[0]["text_span"] == "CONG TY ABC"
    assert citations[0]["validation_status"] == "VALID"


def test_explicit_review_block_is_preserved_when_status_says_completed():
    payload = _result()
    payload["status"] = "completed"
    payload["machine"]["review_required"] = False
    payload["review"] = {"blocked": True, "unresolved": ["completeness"]}
    a = adapt_ai1_input(payload)
    assert a.meta["review_required"]
    assert any(i.code == "AI1_PENDING_REVIEW" for i in a.record.handoff_issues)


def test_table_cell_fields_survive_public_result_serialization():
    from app.contracts.schema_validation import validate_contract
    from app.contracts.wire import BeAi2ProcessingRequest, job_result_to_wire
    from tests.test_processing_wire_contract import _request
    a = adapt_ai1_input(_result(tables=[table()]))
    result = run_idp(a.record, a.envelope)
    wire = job_result_to_wire(result, BeAi2ProcessingRequest.model_validate(_request()))
    validate_contract(wire, "ai2.be.processing.result.v1.schema.json", error_code="TEST")
    assert any(c["table_id"] == "table-a" and c["cell_id"].endswith(":r1:c2") for c in wire["result"]["citations"])
    assert any(i["missing"] == "TABLE_COMPARISON_CONTEXT" for i in wire["result"]["index_contribution"]["evidence_issues"])
