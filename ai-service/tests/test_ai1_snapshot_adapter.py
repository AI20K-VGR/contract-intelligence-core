from __future__ import annotations

import pytest

from app.contracts.models import TableCoverage
from app.pipeline.ai1_snapshot_adapter import SnapshotContractError, adapt_ai1_input, adapt_snapshot
from app.pipeline.idp import run_idp
from app.reasoning.query import classify_ask
from app.tools.gateway import ToolGateway
from app.tools.store import InMemorySnapshotStore


def _snapshot(*, pages: list[dict], status: str = "SUCCESS") -> dict:
    return {
        "schema_version": "ai1.snapshot.v1",
        "snapshot_id": "snap-1",
        "dossier_id": "dossier-1",
        "document_id": "doc-1",
        "run_id": "run-1",
        "source_digest": "a" * 64,
        "execution": {},
        "producer": {},
        "status": status,
        "pages": pages,
    }


def _page(**overrides) -> dict:
    page = {
        "page_no": 1,
        "input_type": "SCANNED_OCR",
        "status": "SUCCESS",
        "raw_text_digest": "b" * 64,
        "render": {},
        "transform": {"rotation_degrees": 0, "profile_version": "test"},
        "lines": [],
        "tables": [],
        "warnings": [],
    }
    page.update(overrides)
    return page


def test_partial_text_without_geometry_is_review_only_and_never_gets_bbox():
    result = adapt_snapshot(
        _snapshot(
            pages=[
                _page(
                    status="PARTIAL",
                    text="... chi con text tho",
                    warnings=[{"code": "missing_line_geometry"}],
                )
            ],
            status="PARTIAL",
        )
    )
    assert result.record.pages[0].quality == "LOW"
    assert result.record.pages[0].text == "... chi con text tho"
    assert result.record.nodes[0].bbox == []
    assert any(issue.code == "PAGE_PARTIAL" for issue in result.record.handoff_issues)


def test_compact_ocr_promotes_explicit_contract_value_with_line_citation():
    line = "Giá trị hợp đồng: 1.234.567 VND"
    result = adapt_snapshot(
        _snapshot(
            pages=[
                _page(
                    text=line,
                    lines=[
                        {
                            "line_id": "contract-value-line",
                            "raw_text": line,
                            "bbox": [0.1, 0.1, 0.9, 0.2],
                        }
                    ],
                )
            ]
        )
    )

    node = next(node for node in result.record.nodes if node.structured_key == "contract_value")
    assert node.type == "FIELD"
    assert node.structured_value == "1234567"
    assert node.source_line_ids == ["contract-value-line"]

    store = InMemorySnapshotStore()
    store.put(result.record)
    hits = ToolGateway(store).search_structured(result.envelope, "contract_value")
    assert len(hits) == 1
    assert hits[0]["value"] == "1234567"
    assert hits[0]["citation"]["text_span"] == line


def test_compact_ocr_promotes_contract_price_label_with_line_citation():
    line = "Giá hợp đồng (chưa VAT) bằng số: 1.000.000.000 VND"
    result = adapt_snapshot(
        _snapshot(
            pages=[
                _page(
                    text=line,
                    lines=[
                        {
                            "line_id": "contract-price-line",
                            "raw_text": line,
                            "bbox": [0.1, 0.1, 0.9, 0.2],
                        }
                    ],
                )
            ]
        )
    )

    node = next(node for node in result.record.nodes if node.structured_key == "contract_value")
    assert node.structured_value == "1000000000"
    assert node.source_line_ids == ["contract-price-line"]


def test_failed_ocr_is_blocked_and_not_business_evidence():
    result = adapt_snapshot(
        _snapshot(
            pages=[
                _page(
                    status="FAILED",
                    error={"code": "OCR_ENGINE_UNAVAILABLE"},
                    text="stale text must not be trusted",
                )
            ],
            status="FAILED",
        )
    )
    job = run_idp(result.record, result.envelope)
    assert job.status.value == "FAILED"
    assert job.review_state.value == "BLOCKED"
    assert any(i.code == "OCR_ENGINE_UNAVAILABLE" for i in job.handoff_issues)


def test_sparse_cells_use_column_index_and_preserve_wrapped_cell_geometry():
    result = adapt_snapshot(
        _snapshot(
            pages=[
                _page(
                    tables=[
                        {
                            "table_id": "t1",
                            "cells": [
                                {
                                    "cell_id": "c1",
                                    "row_index": 0,
                                    "column_index": 0,
                                    "text": "02",
                                    "bbox": [0.1, 0.1, 0.2, 0.2],
                                    "line_ids": ["l1"],
                                },
                                {
                                    "cell_id": "c2",
                                    "row_index": 0,
                                    "column_index": 2,
                                    "text": "Dong goi\nkem phu kien",
                                    "bboxes": [
                                        [0.3, 0.1, 0.6, 0.13],
                                        [0.3, 0.13, 0.6, 0.16],
                                    ],
                                    "line_ids": ["l2", "l3"],
                                },
                            ],
                        }
                    ]
                )
            ]
        )
    )
    table = result.record.tables[0]
    assert table.rows == [["02", None, "Dong goi\nkem phu kien"]]
    assert table.cells[1].column_index == 2
    assert len(table.cells[1].bbox_fragments) == 2
    assert table.cell_citations["0:2"].bbox_fragments[1] == [0.3, 0.13, 0.6, 0.16]


def test_table_structure_warning_does_not_make_ai2_reconstruct_a_table():
    result = adapt_snapshot(
        _snapshot(pages=[_page(warnings=[{"code": "table_structure_unavailable"}])])
    )
    assert result.record.tables == []
    assert any(i.code == "TABLE_STRUCTURE_UNAVAILABLE" for i in result.record.handoff_issues)


def test_detected_table_without_cells_becomes_review_issue_not_reconstructed():
    result = adapt_snapshot(_snapshot(pages=[_page(tables=[{"table_id": "t-empty", "cells": []}])]))
    assert result.record.tables == []
    assert result.record.pages[0].quality == "LOW"
    assert any(i.code == "TABLE_CELLS_UNAVAILABLE" for i in result.record.handoff_issues)


def test_detected_table_without_cell_geometry_is_degraded():
    result = adapt_snapshot(
        _snapshot(
            pages=[
                _page(
                    tables=[
                        {
                            "table_id": "t-text-only",
                            "cells": [{"row_index": 0, "column_index": 0, "text": "A"}],
                        }
                    ]
                )
            ]
        )
    )
    assert result.record.tables[0].rows == [["A"]]
    assert result.record.pages[0].quality == "LOW"
    assert any(i.code == "TABLE_GEOMETRY_UNAVAILABLE" for i in result.record.handoff_issues)


def test_tables_on_separate_pages_with_reset_stt_stay_separate():
    pages = [
        _page(tables=[{"table_id": "t1", "cells": [{"row_index": 0, "column_index": 0, "text": "1"}]}]),
        _page(
            page_no=2,
            tables=[{"table_id": "t2", "cells": [{"row_index": 0, "column_index": 0, "text": "1"}]}],
        ),
    ]
    result = adapt_snapshot(_snapshot(pages=pages))
    assert [table.table_id for table in result.record.tables] == ["t1", "t2"]


def test_total_row_without_sequence_is_kept_by_row_index():
    result = adapt_snapshot(
        _snapshot(
            pages=[
                _page(
                    tables=[
                        {
                            "table_id": "t-total",
                            "cells": [
                                {"row_index": 0, "column_index": 0, "text": "1"},
                                {"row_index": 1, "column_index": 1, "text": "Tong cong"},
                            ],
                        }
                    ]
                )
            ]
        )
    )
    assert result.record.tables[0].rows[1] == [None, "Tong cong"]


def test_missing_diacritics_are_used_for_matching_but_raw_label_is_kept():
    result = adapt_snapshot(
        _snapshot(
            pages=[
                _page(
                    lines=[
                        {
                            "line_id": "l1",
                            "raw_text": "DIEU 1. NOI DUNG VA PHAM VI CONG VIEC",
                            "bbox_source": "native",
                            "geometry_status": "measured",
                            "bbox": [0.1, 0.1, 0.8, 0.2],
                            "words": [],
                        }
                    ]
                )
            ]
        )
    )
    assert result.record.nodes[0].type == "CLAUSE"
    assert result.record.nodes[0].raw_label.startswith("DIEU 1")
    assert classify_ask("DIEU 1 noi ve gi?")["type"] == "lookup_clause"


def test_explicit_no_tables_is_not_an_evidence_issue():
    result = adapt_snapshot(
        _snapshot(
            pages=[
                _page(
                    text="Dieu 1. Noi dung",
                    table_coverage={"status": "NOT_PRESENT", "method": "layout-v1"},
                ),
                _page(
                    page_no=2,
                    text="Dieu 2. Thanh toan",
                    table_coverage="NOT_PRESENT",
                ),
            ]
        )
    )
    assert all(page.table_coverage == TableCoverage.NOT_PRESENT for page in result.record.pages)
    assert result.meta["table_coverage"] == "NOT_PRESENT"
    assert not any(issue.code.startswith("TABLE_") for issue in result.record.handoff_issues)


def test_empty_tables_without_detection_result_is_unknown():
    result = adapt_snapshot(_snapshot(pages=[_page(text="Dieu 1. Noi dung")]))
    assert result.record.pages[0].table_coverage == TableCoverage.UNKNOWN
    assert any(issue.code == "TABLE_DETECTION_UNKNOWN" for issue in result.record.handoff_issues)


def test_legacy_text_only_is_degraded_without_geometry_or_tables():
    result = adapt_ai1_input(
        {
            "document_id": "legacy-doc",
            "filename": "contract.pdf",
            "page_count": 2,
            "full_text": "Dieu 1\nNoi dung",
            "pages": [
                {
                    "page_number": 1,
                    "status": "SUCCESS",
                    "input_type": "TEXT_LAYER",
                    "text": "Dieu 1\nNoi dung",
                    "geometry_available": True,
                },
                {
                    "page_number": 2,
                    "status": "SUCCESS",
                    "input_type": "TEXT_LAYER",
                    "text": "Dieu 2\nThanh toan",
                    "geometry_available": True,
                },
            ],
        }
    )
    assert result.meta["source"] == "legacy_ocr_json"
    assert result.meta["capabilities"]["line_geometry"] is False
    assert result.record.tables == []
    assert all(page.quality == "LOW" for page in result.record.pages)
    assert all(page.table_coverage == TableCoverage.UNKNOWN for page in result.record.pages)
    assert all(node.bbox == [] for node in result.record.nodes)
    assert any(issue.code == "LEGACY_TEXT_ONLY" for issue in result.record.handoff_issues)


def test_catalog_is_rejected_before_reasoning():
    with pytest.raises(SnapshotContractError) as exc:
        adapt_ai1_input({"schema_version": "ai2.ocr_edge_cases.v1", "cases": []})
    assert exc.value.code == "UNSUPPORTED_ARTIFACT_KIND"


def test_non_canonical_snapshot_version_is_rejected():
    payload = _snapshot(pages=[_page()])
    payload["schema_version"] = "ai1.snapshot.invalid"

    with pytest.raises(SnapshotContractError) as exc:
        adapt_ai1_input(payload)

    assert exc.value.code == "UNSUPPORTED_SNAPSHOT_VERSION"


def _v1_snapshot(page: dict) -> dict:
    return {
        "schema_version": "ai1.snapshot.v1",
        "snapshot_id": "snap-v1",
        "dossier_id": "dossier-v1",
        "document_id": "doc-v1",
        "run_id": "run-v1",
        "source_digest": "a" * 64,
        "created_at": "2026-09-21T00:00:00Z",
        "execution": {
            "execution_manifest_id": "manifest-v1",
            "config_digest": "b" * 64,
            "policy_digest": "c" * 64,
            "source_version_digest": "d" * 64,
        },
        "producer": {
            "engine_name": "test",
            "engine_version": "1",
            "code_image_digest": "e" * 64,
        },
        "language": {
            "declared_scope": "vi",
            "detected_profile": "vi",
            "detector": {"name": "test", "version": "1"},
        },
        "status": "SUCCESS",
        "pages": [page],
    }


def test_v1_semantic_validation_accepts_explicit_no_table_page():
    result = adapt_ai1_input(
        _v1_snapshot(
            {
                "page_no": 1,
                "page_revision_id": "page-v1-1",
                "input_type": "TEXT_LAYER",
                "status": "SUCCESS",
                "raw_text_digest": "f" * 64,
                "transform": {"rotation_degrees": 0, "profile_version": "test"},
                "quality": {"coverage_status": "COMPLETE"},
                "table_coverage": {"status": "NOT_PRESENT", "method": "layout-v1"},
                "lines": [],
                "tables": [],
                "warnings": [],
            }
        )
    )
    assert result.record.pages[0].table_coverage == TableCoverage.NOT_PRESENT
    assert result.meta["source"] == "ai1.snapshot.v1"


def test_v1_semantic_validation_rejects_word_span_outside_line():
    page = {
        "page_no": 1,
        "page_revision_id": "page-v1-1",
        "input_type": "TEXT_LAYER",
        "status": "SUCCESS",
        "raw_text_digest": "f" * 64,
        "transform": {"rotation_degrees": 0, "profile_version": "test"},
        "quality": {"coverage_status": "COMPLETE"},
        "table_coverage": {"status": "NOT_PRESENT", "method": "layout-v1"},
        "lines": [
            {
                "line_id": "line-1",
                "raw_text": "abc",
                "bbox_source": "absent",
                "geometry_status": "absent",
                "words": [
                    {
                        "word_id": "word-1",
                        "text": "abc",
                        "char_start": 0,
                        "char_end": 4,
                        "bbox_source": "absent",
                        "geometry_status": "absent",
                    }
                ],
            }
        ],
        "tables": [],
        "warnings": [],
    }
    with pytest.raises(SnapshotContractError) as exc:
        adapt_ai1_input(_v1_snapshot(page))
    assert exc.value.code == "SNAPSHOT_SEMANTIC_INVALID"
