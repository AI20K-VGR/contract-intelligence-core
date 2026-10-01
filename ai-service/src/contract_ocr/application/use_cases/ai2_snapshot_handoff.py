"""Serialize the OCR lab's internal snapshot into AI2's canonical v1 contract.

The OCR pipeline keeps its richer internal model (filename, document role,
structural nodes and table-continuity decisions).  Those fields are useful to
AI1, but they are intentionally not part of the AI2 handoff contract.  This
module is the single handoff boundary: it emits only the canonical schema used
by ``ai-service/app/pipeline/ai1_snapshot_adapter.py``.

This is a contract adapter, not a second schema.  In particular, geometry
reported as CLAIMED is never upgraded to measured/derived geometry, and words
that cannot be grounded safely are emitted without a bbox.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from contract_ocr.domain.snapshot import DocumentSnapshot, SnapshotPage


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _source_digest(value: str) -> str:
    """Convert the OCR lab's ``sha256:<hex>`` form to AI2's canonical form."""

    raw = value.removeprefix("sha256:")
    if len(raw) != 64:
        raise ValueError("source_digest must be a 64-character SHA-256 hex digest")
    int(raw, 16)
    return raw.lower()


def _bbox(value: Any) -> list[float] | None:
    if value is None:
        return None
    return [float(item) for item in value]


def _geometry(provenance: str | None, *, page_input_type: str, keep_claimed: bool = False) -> dict[str, Any]:
    if provenance is None:
        return {"bbox": None, "bbox_source": "absent", "geometry_status": "absent"}
    value = provenance.upper()
    if value == "MEASURED":
        source = "native" if page_input_type == "TEXT_LAYER" else "detector"
        return {"bbox_source": source, "geometry_status": "measured"}
    if value == "DERIVED":
        return {"bbox_source": "derived", "geometry_status": "derived"}
    # The AI1 lab model calls model-reported coordinates CLAIMED.  The canonical
    # AI2 contract has no CLAIMED enum, so retain only an explicit line-level
    # claim; word/table claims are dropped by their callers.
    if keep_claimed:
        return {"bbox_source": "line_only", "geometry_status": "line_only"}
    return {"bbox_source": "absent", "geometry_status": "absent"}


def _page_status(pages: list[SnapshotPage]) -> str:
    statuses = {page.status for page in pages}
    if statuses == {"FAILED"}:
        return "FAILED"
    if statuses.intersection({"FAILED", "PARTIAL"}):
        return "PARTIAL"
    return "SUCCESS"


def _quality(page: SnapshotPage) -> dict[str, Any]:
    if page.status == "FAILED":
        coverage = "FAILED"
    elif page.status == "PARTIAL":
        coverage = "NEEDS_REVIEW"
    elif not page.text.strip() and "blank_page" in page.warnings:
        coverage = "BLANK_VERIFIED"
    else:
        coverage = "COMPLETE"

    confidences = [word.confidence for word in page.words if word.confidence is not None]
    return {
        "coverage_status": coverage,
        "ocr_confidence": sum(confidences) / len(confidences) if confidences else None,
        "signals": list(page.warnings),
    }


def _warning(code: str, message: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"code": code}
    if message:
        result["message"] = message
    return result


def _page_payload(page: SnapshotPage, *, snapshot_id: str, engine_name: str, engine_version: str) -> dict[str, Any]:
    words_by_line: dict[str, list[Any]] = {}
    for word in page.words:
        words_by_line.setdefault(word.line_id, []).append(word)

    lines: list[dict[str, Any]] = []
    for line in page.lines:
        line_geometry = _geometry(
            line.geometry_provenance,
            page_input_type=page.input_type,
            keep_claimed=True,
        )
        line_payload: dict[str, Any] = {
            "line_id": line.line_id,
            "raw_text": line.text,
            "bbox": _bbox(line.bbox_normalized),
            "bbox_source": line_geometry["bbox_source"],
            "geometry_status": line_geometry["geometry_status"],
            "engine_confidence": None,
            "words": [],
        }
        for word in words_by_line.get(line.line_id, []):
            word_geometry = _geometry(
                word.geometry_provenance,
                page_input_type=page.input_type,
                keep_claimed=False,
            )
            line_payload["words"].append(
                {
                    "word_id": word.word_id,
                    "text": word.text,
                    "char_start": word.line_char_start,
                    "char_end": word.line_char_end,
                    "bbox": _bbox(word.bbox_normalized)
                    if word_geometry["geometry_status"] != "absent"
                    else None,
                    "bbox_source": word_geometry["bbox_source"],
                    "geometry_status": word_geometry["geometry_status"],
                    "engine_confidence": word.confidence,
                }
            )
        lines.append(line_payload)

    tables: list[dict[str, Any]] = []
    has_unstructured_table = False
    for table in page.tables:
        table_geometry = _geometry(
            table.geometry_provenance,
            page_input_type=page.input_type,
            keep_claimed=False,
        )
        cells: list[dict[str, Any]] = []
        for column_index, text in enumerate(table.header):
            cells.append(
                {
                    "cell_id": f"{table.table_id}:header:c{column_index + 1:03d}",
                    "row_index": 0,
                    "column_index": column_index,
                    "row_kind": "HEADER",
                    "text": text,
                    "line_ids": [],
                    "bbox_fragments": [],
                }
            )
        data_row_offset = 1 if table.header else 0
        for row_index, row in enumerate(table.rows):
            for column_index, cell in enumerate(row.cells):
                cell_geometry = _geometry(
                    cell.geometry_provenance,
                    page_input_type=page.input_type,
                    keep_claimed=False,
                )
                cells.append(
                    {
                        "cell_id": cell.cell_id,
                        "row_index": row_index + data_row_offset,
                        "column_index": column_index,
                        "row_kind": "DATA",
                        "text": cell.text,
                        "line_ids": [],
                        "bbox_fragments": (
                            [_bbox(cell.bbox_normalized)]
                            if cell_geometry["geometry_status"] != "absent"
                            and cell.bbox_normalized is not None
                            else []
                        ),
                    }
                )
        if not cells:
            # AI2's semantic contract requires every emitted table to have a
            # resolvable cell inventory. Keep the fact that detection ran, but
            # do not emit an empty table as if its structure were usable.
            has_unstructured_table = True
            continue
        tables.append(
            {
                "table_id": table.table_id,
                "table_coverage": {
                    "status": "DETECTED",
                    "method": engine_name,
                    "version": engine_version,
                },
                "bbox": _bbox(table.bbox_normalized)
                if table_geometry["geometry_status"] != "absent"
                else None,
                "geometry_status": table_geometry["geometry_status"],
                "cells": cells,
            }
        )

    warnings = [_warning(code) for code in page.warnings]
    error = None
    if has_unstructured_table:
        warnings.append(_warning("table_structure_unavailable"))
    if page.error:
        error = _warning("OCR_FAILED", page.error)

    result = {
        "page_no": page.page_number,
        "page_revision_id": f"{snapshot_id}:p{page.page_number}",
        "input_type": page.input_type,
        "status": page.status,
        "raw_text_digest": _digest(page.text),
        "transform": {
            "rotation_degrees": page.rotation_degrees,
            "profile_version": "contract-ocr-lab-handoff-v1",
        },
        "quality": _quality(page),
        "table_coverage": {
            "status": (
                "UNAVAILABLE"
                if has_unstructured_table and not tables
                else {
                "NOT_CHECKED": "UNKNOWN",
                "NOT_PRESENT": "NOT_PRESENT",
                "DETECTED": "DETECTED",
                }.get(page.table_status, "UNKNOWN")
            ),
            "method": engine_name,
            "version": engine_version,
        },
        "lines": lines,
        "tables": tables,
        "warnings": warnings,
    }
    if error is not None:
        result["error"] = error
    return result


def to_ai2_snapshot_v1(
    snapshot: DocumentSnapshot,
    *,
    created_at: str | None = None,
    execution_manifest_id: str | None = None,
) -> dict[str, Any]:
    """Return an AI2-canonical ``ai1.snapshot.v1`` payload.

    The OCR lab does not currently emit execution digests, so this boundary
    derives deterministic handoff metadata and labels the profile explicitly.
    Production AI1 should replace these defaults with real run/config/policy/
    source-version digests once those values are available at the OCR runner.
    """

    internal_json = json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    source_version_digest = _digest("contract-ocr-lab:" + internal_json)
    config_digest = _digest("contract-ocr-lab:config:v1")
    policy_digest = _digest("contract-ocr-lab:policy:v1")
    code_image_digest = _digest("contract-ocr-lab:handoff-writer:v1")
    created = created_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "schema_version": "ai1.snapshot.v1",
        "snapshot_id": snapshot.snapshot_id,
        "dossier_id": snapshot.dossier_id,
        "document_id": snapshot.document_id,
        "run_id": snapshot.snapshot_id,
        "source_digest": _source_digest(snapshot.source_digest),
        "created_at": created,
        "execution": {
            "execution_manifest_id": execution_manifest_id or f"exec:{snapshot.snapshot_id}",
            "config_digest": config_digest,
            "policy_digest": policy_digest,
            "source_version_digest": source_version_digest,
            "replay": False,
        },
        "producer": {
            "engine_name": snapshot.engine.name,
            "engine_version": snapshot.engine.version,
            "model_version": snapshot.engine.version,
            "preprocess_version": "contract-ocr-lab-handoff-v1",
            "code_image_digest": code_image_digest,
        },
        "language": {
            "declared_scope": "vi-en",
            "detected_profile": "vi-en",
            "detector": {"name": "contract-ocr-lab-default", "version": "1"},
        },
        "status": _page_status(snapshot.pages),
        "pages": [
            _page_payload(
                page,
                snapshot_id=snapshot.snapshot_id,
                engine_name=snapshot.engine.name,
                engine_version=snapshot.engine.version,
            )
            for page in snapshot.pages
        ],
    }


__all__ = ["to_ai2_snapshot_v1"]
