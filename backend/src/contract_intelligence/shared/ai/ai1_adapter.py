"""Translate the AI1 handoff snapshot into the backend OCR payload.

AI1 owns ``ai1.snapshot.v1``.  The backend pipeline still persists the older
``ai1.snapshot.v3`` shape, so the translation is deliberately kept at the
HTTP boundary.  Neither service imports the other service's Python package.
"""

from __future__ import annotations

from typing import Any

from contract_intelligence.shared.ai.schemas import Ai1SnapshotPayload, PageKind

_PAGE_KIND = {
    "TEXT_LAYER": PageKind.NATIVE,
    "SCANNED_OCR": PageKind.SCANNED,
    "MIXED": PageKind.HYBRID,
}


def adapt_ai1_snapshot_result(result: dict[str, Any]) -> Ai1SnapshotPayload:
    """Validate a v3 payload or adapt the AI1-owned v1 handoff snapshot.

    The bridge expects the v1 snapshot under ``result.snapshot``.  Keeping the
    envelope means AI1 can add job metadata without changing the backend's
    persistence contract.
    """
    if result.get("schema_version") == "ai1.snapshot.v3":
        return Ai1SnapshotPayload.model_validate(result)

    snapshot = result.get("snapshot")
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != "ai1.snapshot.v1":
        raise ValueError(
            "OCR result must be ai1.snapshot.v3 or contain an ai1.snapshot.v1 snapshot"
        )

    pages = snapshot.get("pages", [])
    full_text = "\f".join(str(page.get("text", "")) for page in pages)
    lines: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    page_items: list[dict[str, Any]] = []
    line_offsets: dict[str, tuple[int, int, int, list[float]]] = {}
    document_offset = 0

    for page in pages:
        page_no = int(page["page_number"])
        page_text = str(page.get("text", ""))
        image_ref = page.get("page_image_ref") or {}
        page_items.append(
            {
                "page_no": page_no,
                "width_pt": float(page["source_page_width"]),
                "height_pt": float(page["source_page_height"]),
                "rotation": int(page.get("rotation_degrees", 0)),
                "kind": _PAGE_KIND.get(page.get("input_type"), PageKind.HYBRID),
                "render_blob_uri": str(image_ref.get("uri", "")),
                "preview_blob_uri": str(image_ref.get("uri", "")),
                "features": {
                    "ai1_page_status": page.get("status"),
                    "table_status": page.get("table_status"),
                    "warnings": page.get("warnings", []),
                    "error": page.get("error"),
                },
            }
        )

        words_by_line: dict[str, list[dict[str, Any]]] = {}
        for word in page.get("words", []):
            words_by_line.setdefault(str(word["line_id"]), []).append(word)

        for line_no, line in enumerate(page.get("lines", []), start=1):
            line_id = str(line["line_id"])
            bbox = list(line["bbox_normalized"])
            start = document_offset + int(line["page_char_start"])
            end = document_offset + int(line["page_char_end"])
            line_offsets[line_id] = (start, end, page_no, bbox)
            lines.append(
                {
                    "page_no": page_no,
                    "line_no": line_no,
                    "text": str(line["text"]),
                    "bbox": bbox,
                    "confidence": 1.0,
                    "doc_char_start": start,
                    "doc_char_end": end,
                    "words": [
                        {
                            "text": str(word["text"]),
                            "bbox": list(word["bbox_normalized"]),
                            "conf": float(word.get("confidence") or 0.0),
                        }
                        for word in words_by_line.get(line_id, [])
                    ],
                }
            )

        for table in page.get("tables", []):
            cells: list[dict[str, Any]] = []
            for row_index, row in enumerate(table.get("rows", [])):
                for column_index, cell in enumerate(row.get("cells", [])):
                    bbox = cell.get("bbox_normalized")
                    if bbox is None:
                        continue
                    cells.append(
                        {
                            "row_idx": row_index,
                            "col_idx": column_index,
                            "text": str(cell.get("text", "")),
                            "bbox": list(bbox),
                            "is_header": row_index == 0 and bool(table.get("header")),
                            "confidence": 1.0,
                        }
                    )
            rows = table.get("rows", [])
            tables.append(
                {
                    "page_no": page_no,
                    "bbox": list(table["bbox_normalized"]),
                    "rows_count": len(rows),
                    "cols_count": max((len(row.get("cells", [])) for row in rows), default=0),
                    "has_borders": table.get("geometry_provenance") == "MEASURED",
                    "cells": cells,
                }
            )
        document_offset += len(page_text) + 1

    clauses: list[dict[str, Any]] = []
    for node in snapshot.get("nodes", []):
        node_line_ids = [str(line_id) for line_id in node.get("line_ids", [])]
        positioned = [line_offsets[line_id] for line_id in node_line_ids if line_id in line_offsets]
        if positioned:
            start = min(item[0] for item in positioned)
            end = max(item[1] for item in positioned)
        else:
            start = end = 0
        node_bbox = node.get("bbox_normalized")
        clauses.append(
            {
                "node_type": str(node.get("type", "UNMARKED")).lower(),
                "label": str(node.get("label_normalized", "")),
                "number": str(node.get("label_raw") or ""),
                "title": str(node.get("label_normalized", "")),
                "text": "\n".join(
                    next((line["text"] for line in lines if line["doc_char_start"] == item[0]), "")
                    for item in positioned
                ),
                "page_start": int(node.get("page_start", 1)),
                "page_end": int(node.get("page_end", 1)),
                "confidence": 1.0,
                "doc_char_start": start,
                "doc_char_end": end,
                "regions": (
                    [
                        {
                            "page_no": int(node.get("page_start", 1)),
                            "bbox": list(node_bbox),
                            "bbox_source": str(node.get("geometry_provenance") or "derived"),
                        }
                    ]
                    if node_bbox is not None
                    else []
                ),
            }
        )

    return Ai1SnapshotPayload.model_validate(
        {
            "schema_version": "ai1.snapshot.v3",
            "document_id": snapshot["document_id"],
            "total_pages": int(snapshot["page_count"]),
            "pages": page_items,
            "full_text_nfc": full_text,
            "lines": lines,
            "clauses": clauses,
            "tables": tables,
        }
    )


__all__ = ["adapt_ai1_snapshot_result"]
