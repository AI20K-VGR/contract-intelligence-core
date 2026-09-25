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


def test_adapts_table_continuation_graph_for_backend_persistence() -> None:
    def page(number: int, table: dict) -> dict:
        return {
            "page_number": number,
            "status": "SUCCESS",
            "input_type": "TEXT_LAYER",
            "source_page_width": 595.0,
            "source_page_height": 842.0,
            "rotation_degrees": 0,
            "page_image_ref": {
                "uri": f"storage://pages/{number}.png",
                "width_px": 100,
                "height_px": 100,
            },
            "text": "",
            "lines": [],
            "words": [],
            "blocks": [],
            "table_status": "SUCCESS",
            "tables": [table],
            "warnings": [],
            "error": None,
        }

    result = adapt_ai1_snapshot_result(
        {
            "snapshot": {
                "schema_version": "ai1.snapshot.v1",
                "dossier_id": "dos-1",
                "document_id": "doc-1",
                "page_count": 2,
                "pages": [
                    page(
                        1,
                        {
                            "id": "table-1",
                            "bbox_normalized": [0.1, 0.1, 0.9, 0.5],
                            "rows": [],
                            "continued_by_table_id": "table-2",
                        },
                    ),
                    page(
                        2,
                        {
                            "id": "table-2",
                            "bbox_normalized": [0.1, 0.1, 0.9, 0.5],
                            "rows": [],
                            "continues_table_id": "table-1",
                        },
                    ),
                ],
                "nodes": [],
            }
        }
    )

    assert [table.source_id for table in result.tables] == ["table-1", "table-2"]
    assert result.tables[0].is_multi_page is True
    assert result.tables[0].continued_from_source_id is None
    assert result.tables[1].is_multi_page is True
    assert result.tables[1].continued_from_source_id == "table-1"


def test_adapts_snapshot_table_continuity_links_into_table_rows() -> None:
    def page(number: int, table_id: str) -> dict:
        return {
            "page_number": number,
            "status": "SUCCESS",
            "input_type": "TEXT_LAYER",
            "source_page_width": 595.0,
            "source_page_height": 842.0,
            "rotation_degrees": 0,
            "page_image_ref": {
                "uri": f"storage://pages/{number}.png",
                "width_px": 100,
                "height_px": 100,
            },
            "text": "content",
            "lines": [],
            "words": [],
            "blocks": [],
            "table_status": "SUCCESS",
            "tables": [
                {
                    "id": table_id,
                    "bbox_normalized": [0.1, 0.1, 0.9, 0.9],
                    "rows": [],
                }
            ],
            "warnings": [],
            "error": None,
        }

    result = adapt_ai1_snapshot_result(
        {
            "snapshot": {
                "schema_version": "ai1.snapshot.v1",
                "dossier_id": "dos-1",
                "document_id": "doc-1",
                "page_count": 2,
                "pages": [page(1, "table-1"), page(2, "table-2")],
                "nodes": [],
                "table_continuity": [
                    {
                        "from_table_id": "table-1",
                        "from_page": 1,
                        "to_table_id": "table-2",
                        "to_page": 2,
                        "decision": "MERGE",
                        "confidence": 1.0,
                        "reason_codes": ["ANCHOR_CONTINUOUS"],
                    }
                ],
            }
        }
    )

    assert result.tables[0].is_multi_page is True
    assert result.tables[1].is_multi_page is True
    assert result.tables[1].continued_from_source_id == "table-1"
