from contract_intelligence.shared.ai.ai1_adapter import adapt_ai1_snapshot_result


def test_adapts_ai1_snapshot_v1_at_service_boundary() -> None:
    result = {
        "snapshot": {
            "schema_version": "ai1.snapshot.v1",
            "snapshot_id": "snap-1",
            "source_digest": "sha256:" + "a" * 64,
            "dossier_id": "dos-1",
            "document_id": "doc-1",
            "filename": "contract.pdf",
            "document_role": "contract",
            "input_type": "TEXT_LAYER",
            "engine": {"name": "pymupdf", "version": "1"},
            "page_count": 1,
            "processing_ms": 12.0,
            "nodes": [
                {
                    "node_id": "art-1",
                    "type": "ARTICLE",
                    "label_raw": "Điều 1",
                    "label_normalized": "Điều 1",
                    "parent_id": None,
                    "page_start": 1,
                    "page_end": 1,
                    "text": "Payment terms plus OCR text without geometry",
                    "line_ids": ["line-1"],
                    "regions": [
                        {
                            "page_number": 1,
                            "bbox_normalized": [0.1, 0.1, 0.4, 0.2],
                            "geometry_provenance": "MEASURED",
                            "anchor": "START",
                        }
                    ],
                    "bbox_normalized": [0.1, 0.1, 0.4, 0.2],
                    "geometry_provenance": "MEASURED",
                },
                {
                    "node_id": "cl-1",
                    "type": "CLAUSE",
                    "label_raw": "1.1",
                    "label_normalized": "Khoản 1",
                    "parent_id": "art-1",
                    "page_start": 1,
                    "page_end": 1,
                    "text": "Nested clause text",
                    "line_ids": ["line-1"],
                    "bbox_normalized": [0.1, 0.2, 0.4, 0.3],
                    "geometry_provenance": "MEASURED",
                },
            ],
            "table_continuity": [],
            "pages": [
                {
                    "page_number": 1,
                    "status": "SUCCESS",
                    "input_type": "TEXT_LAYER",
                    "source_page_width": 595.0,
                    "source_page_height": 842.0,
                    "rotation_degrees": 0,
                    "page_image_ref": {
                        "uri": "storage://pages/1.png",
                        "width_px": 100,
                        "height_px": 100,
                    },
                    "text": "Payment terms",
                    "lines": [
                        {
                            "line_id": "line-1",
                            "text": "Payment terms",
                            "page_char_start": 0,
                            "page_char_end": 13,
                            "bbox_normalized": [0.1, 0.1, 0.4, 0.2],
                            "geometry_provenance": "MEASURED",
                            "word_ids": ["word-1"],
                        }
                    ],
                    "words": [
                        {
                            "word_id": "word-1",
                            "line_id": "line-1",
                            "text": "Payment",
                            "line_char_start": 0,
                            "line_char_end": 7,
                            "bbox_normalized": [0.1, 0.1, 0.3, 0.2],
                            "geometry_provenance": "MEASURED",
                            "confidence": 0.9,
                        }
                    ],
                    "blocks": [],
                    "table_status": "NOT_PRESENT",
                    "tables": [],
                    "warnings": [],
                    "error": None,
                }
            ],
        }
    }

    payload = adapt_ai1_snapshot_result(result)

    assert payload.document_id == "doc-1"
    assert payload.total_pages == 1
    assert payload.pages[0].kind.value == "native"
    assert payload.lines[0].words[0].text == "Payment"
    assert payload.full_text_nfc == "Payment terms"
    assert payload.clauses[0].source_id == "art-1"
    assert payload.clauses[0].parent_source_id is None
    assert payload.clauses[0].text == "Payment terms plus OCR text without geometry"
    assert payload.clauses[0].regions[0].page_no == 1
    assert payload.clauses[1].source_id == "cl-1"
    assert payload.clauses[1].parent_source_id == "art-1"


def test_adapter_preserves_table_header_as_real_header_cells() -> None:
    result = {
        "snapshot": {
            "schema_version": "ai1.snapshot.v1",
            "document_id": "doc-1",
            "page_count": 1,
            "nodes": [],
            "table_continuity": [],
            "pages": [
                {
                    "page_number": 1,
                    "source_page_width": 100,
                    "source_page_height": 100,
                    "input_type": "SCANNED_OCR",
                    "text": "STT Tên hàng 1 Bút",
                    "lines": [],
                    "words": [],
                    "tables": [
                        {
                            "bbox_normalized": [0.1, 0.2, 0.9, 0.8],
                            "geometry_provenance": "MEASURED",
                            "header": ["STT", "Tên hàng"],
                            "rows": [
                                {
                                    "cells": [
                                        {
                                            "text": "1",
                                            "bbox_normalized": [0.1, 0.5, 0.3, 0.8],
                                        },
                                        {
                                            "text": "Bút",
                                            "bbox_normalized": [0.3, 0.5, 0.9, 0.8],
                                        },
                                    ]
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    }

    payload = adapt_ai1_snapshot_result(result)

    table = payload.tables[0]
    assert table.rows_count == 2
    assert table.cols_count == 2
    assert [(cell.row_idx, cell.text, cell.is_header) for cell in table.cells] == [
        (0, "STT", True),
        (0, "Tên hàng", True),
        (1, "1", False),
        (1, "Bút", False),
    ]
