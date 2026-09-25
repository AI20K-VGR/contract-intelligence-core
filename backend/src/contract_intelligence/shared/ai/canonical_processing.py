"""Build and adapt the canonical Backend ↔ AI2 processing wire contract.

The Kafka worker owns the durable dossier lifecycle. This module only maps the
AI1-owned ``ai1.snapshot.v1`` documents plus the confirmed manifest into the
closed ``be.ai2.processing.request.v1`` envelope.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from contract_intelligence.contract.infrastructure.persistence.orm import (
    DocumentORM,
    ManifestItemORM,
    ManifestRelationORM,
)


def _digest(value: dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _wire_source_digest(value: Any) -> str:
    """Map AI1's labelled digest to AI2's unlabelled SHA-256 wire field."""

    digest = str(value)
    if digest.lower().startswith("sha256:"):
        return digest[7:]
    return digest


def _geometry_fields(value: Any) -> tuple[str, str]:
    provenance = str(value or "").lower()
    if provenance in {"measured", "native"}:
        return "native", "measured"
    if provenance in {"detector", "detected"}:
        return "detector", "measured"
    if provenance in {"derived", "inferred"}:
        return "derived", "derived"
    if provenance in {"line_only", "line-only"}:
        return "line_only", "line_only"
    return "absent", "absent"


def _bbox(value: Any) -> list[float] | None:
    if isinstance(value, list) and len(value) == 4:
        return [float(item) for item in value]
    return None


def _canonicalize_compact_snapshot(
    snapshot: dict[str, Any], *, dossier_id: str, run_id: str
) -> dict[str, Any]:
    """Adapt the current AI1 compact snapshot into the closed v1 contract."""

    snapshot_id = str(snapshot["snapshot_id"])
    document_id = str(snapshot["document_id"])
    engine_raw = snapshot.get("engine")
    engine: dict[str, Any] = engine_raw if isinstance(engine_raw, dict) else {}
    engine_name = str(engine.get("name") or "ai1")
    engine_version = str(engine.get("version") or "unknown")
    pages: list[dict[str, Any]] = []

    for raw_page in snapshot.get("pages", []):
        page_no = int(raw_page.get("page_number") or 1)
        page_text = str(raw_page.get("text") or "")
        page_input = str(raw_page.get("input_type") or "MIXED").upper()
        if page_input not in {"TEXT_LAYER", "SCANNED_OCR", "MIXED"}:
            page_input = "MIXED"
        page_status = str(raw_page.get("status") or "SUCCESS").upper()
        if page_status not in {"SUCCESS", "PARTIAL", "FAILED"}:
            page_status = "PARTIAL"
        words_by_line: dict[str, list[dict[str, Any]]] = {}
        for raw_word in raw_page.get("words", []):
            words_by_line.setdefault(str(raw_word.get("line_id") or ""), []).append(raw_word)

        lines: list[dict[str, Any]] = []
        for raw_line in raw_page.get("lines", []):
            line_id = str(
                raw_line.get("line_id") or f"{snapshot_id}:line:{page_no}:{len(lines) + 1}"
            )
            line_bbox = _bbox(raw_line.get("bbox_normalized"))
            bbox_source, geometry_status = _geometry_fields(raw_line.get("geometry_provenance"))
            canonical_words: list[dict[str, Any]] = []
            for index, raw_word in enumerate(words_by_line.get(line_id, []), start=1):
                line_length = len(str(raw_line.get("text") or ""))
                if line_length == 0:
                    continue
                word_id = str(raw_word.get("word_id") or f"{line_id}:word:{index}")
                word_bbox = _bbox(raw_word.get("bbox_normalized"))
                word_source, word_geometry = _geometry_fields(raw_word.get("geometry_provenance"))
                word_start = max(
                    0,
                    min(line_length - 1, int(raw_word.get("line_char_start") or 0)),
                )
                word_end = max(
                    word_start + 1,
                    min(line_length, int(raw_word.get("line_char_end") or word_start + 1)),
                )
                canonical_words.append(
                    {
                        "word_id": word_id,
                        "text": str(raw_word.get("text") or " "),
                        "char_start": word_start,
                        "char_end": max(word_start + 1, word_end),
                        "bbox": word_bbox,
                        "bbox_source": word_source,
                        "geometry_status": word_geometry,
                        "engine_confidence": raw_word.get("confidence"),
                    }
                )
            lines.append(
                {
                    "line_id": line_id,
                    "raw_text": str(raw_line.get("text") or ""),
                    "bbox": line_bbox,
                    "bbox_source": bbox_source,
                    "geometry_status": geometry_status,
                    "engine_confidence": 1.0,
                    "words": canonical_words,
                }
            )

        tables: list[dict[str, Any]] = []
        for raw_table in raw_page.get("tables", []):
            table_id = f"{snapshot_id}:table:{page_no}:{len(tables) + 1}"
            table_bbox = _bbox(raw_table.get("bbox_normalized"))
            table_source, table_geometry = _geometry_fields(raw_table.get("geometry_provenance"))
            cells: list[dict[str, Any]] = []
            for row_index, raw_row in enumerate(raw_table.get("rows", [])):
                for column_index, raw_cell in enumerate(raw_row.get("cells", [])):
                    cell_bbox = _bbox(raw_cell.get("bbox_normalized"))
                    line_ids = [str(item) for item in raw_cell.get("line_ids", []) if item]
                    cells.append(
                        {
                            "cell_id": f"{table_id}:cell:{row_index}:{column_index}",
                            "row_index": row_index,
                            "column_index": column_index,
                            "rowspan": 1,
                            "colspan": 1,
                            "row_kind": (
                                "HEADER" if row_index == 0 and raw_table.get("header") else "DATA"
                            ),
                            "text": str(raw_cell.get("text") or ""),
                            "line_ids": list(dict.fromkeys(line_ids)),
                            "bbox_fragments": [cell_bbox] if cell_bbox else [],
                        }
                    )
            if not cells:
                continue
            tables.append(
                {
                    "table_id": table_id,
                    "table_coverage": {"status": "DETECTED", "method": "ai1"},
                    "bbox": table_bbox,
                    "geometry_status": table_geometry,
                    "cells": cells,
                }
            )

        warnings = []
        for warning in raw_page.get("warnings", []):
            if isinstance(warning, dict):
                warnings.append(
                    {
                        "code": str(warning.get("code") or "AI1_WARNING"),
                        "message": str(warning.get("message") or ""),
                    }
                )
            else:
                warnings.append({"code": "AI1_WARNING", "message": str(warning)})
        table_status = "DETECTED" if tables else "NOT_PRESENT"
        pages.append(
            {
                "page_no": page_no,
                "page_revision_id": f"{snapshot_id}:page:{page_no}",
                "input_type": page_input,
                "status": page_status,
                "raw_text_digest": hashlib.sha256(page_text.encode("utf-8")).hexdigest(),
                "transform": {
                    "rotation_degrees": int(raw_page.get("rotation_degrees") or 0),
                    "profile_version": "ai1.compact.v1",
                },
                "quality": {
                    "coverage_status": "COMPLETE" if page_status == "SUCCESS" else "NEEDS_REVIEW",
                    "ocr_confidence": 1.0,
                    "signals": [],
                },
                "table_coverage": {"status": table_status, "method": "ai1"},
                "lines": lines,
                "tables": tables,
                "warnings": warnings,
            }
        )

    source_digest = _wire_source_digest(snapshot.get("source_digest"))
    status = (
        "SUCCESS" if pages and all(page["status"] == "SUCCESS" for page in pages) else "PARTIAL"
    )
    return {
        "schema_version": "ai1.snapshot.v1",
        "snapshot_id": snapshot_id,
        "dossier_id": dossier_id,
        "document_id": document_id,
        "run_id": run_id,
        "source_digest": source_digest,
        "created_at": datetime.now(tz=UTC).isoformat(),
        "execution": {
            "execution_manifest_id": f"exec:{run_id}",
            "config_digest": _digest({"engine": engine_name, "version": engine_version}),
            "policy_digest": _digest({"policy": "backend-ai2-v1"}),
            "source_version_digest": _digest({"source": "ai1.compact.v1"}),
            "replay": False,
        },
        "producer": {
            "engine_name": engine_name,
            "engine_version": engine_version,
            "code_image_digest": _digest(engine),
        },
        "language": {
            "declared_scope": "vi",
            "detected_profile": "vi",
            "detector": {"name": "ai1", "version": "compact.v1"},
        },
        "status": status,
        "pages": pages,
    }


def build_processing_request(
    *,
    dossier_id: str,
    run_id: str,
    snapshots: dict[str, dict[str, Any]],
    documents: list[DocumentORM],
    members: list[ManifestItemORM],
    relations: list[ManifestRelationORM],
) -> dict[str, Any] | None:
    """Return a canonical request only when the confirmed manifest is complete."""

    included = [item for item in members if item.included and item.document_id]
    by_document = {document.id: document for document in documents}
    selected: list[tuple[ManifestItemORM, dict[str, Any]]] = []
    for member in sorted(included, key=lambda item: item.order_index):
        snapshot = snapshots.get(str(member.document_id))
        document = by_document.get(str(member.document_id))
        if snapshot is None or document is None:
            return None
        if snapshot.get("schema_version") != "ai1.snapshot.v1":
            return None
        selected.append((member, snapshot))

    bodies = [item for item, _ in selected if str(item.doc_type).lower() == "contract"]
    if len(bodies) != 1:
        return None

    wire_selected = [
        (
            member,
            (
                _canonicalize_compact_snapshot(snapshot, dossier_id=dossier_id, run_id=run_id)
                if "execution" not in snapshot
                else {
                    **snapshot,
                    "source_digest": _wire_source_digest(snapshot.get("source_digest")),
                }
            ),
        )
        for member, snapshot in selected
    ]

    snapshot_identities = [
        {
            "snapshot_id": str(snapshot["snapshot_id"]),
            "snapshot_version": "ai1.snapshot.v1",
            "source_digest": str(snapshot["source_digest"]),
            "snapshot_digest": _digest(snapshot),
        }
        for _, snapshot in wire_selected
    ]
    dossier_members = [
        {
            "member_id": str(member.id),
            "document_id": str(member.document_id),
            "snapshot_id": str(snapshot["snapshot_id"]),
            "role": "body" if str(member.doc_type).lower() == "contract" else "annex",
            "source_digest": str(snapshot["source_digest"]),
        }
        for member, snapshot in wire_selected
    ]
    selected_member_ids = {str(member.id) for member, _ in selected}
    role_relation_map: list[dict[str, Any]] = []
    for relation in relations:
        if relation.source_document_id not in {str(member.document_id) for member, _ in selected}:
            continue
        if relation.target_document_id not in {str(member.document_id) for member, _ in selected}:
            continue
        if relation.relation_type != "annex_of":
            continue
        source_member = next(
            (
                member
                for member, _ in selected
                if str(member.document_id) == relation.source_document_id
            ),
            None,
        )
        target_member = next(
            (
                member
                for member, _ in selected
                if str(member.document_id) == relation.target_document_id
            ),
            None,
        )
        if source_member is None or target_member is None:
            continue
        role_relation_map.append(
            {
                "relation_id": str(relation.id),
                "relation_type": "ANNEX_OF",
                "member_id": str(source_member.id),
                "related_member_id": str(target_member.id),
                "dossier_id": dossier_id,
            }
        )

    # The canonical contract requires no synthetic relation when the dossier
    # contains only a body. Keep this set for a defensive membership check.
    if not selected_member_ids:
        return None

    request_id = f"{run_id}:ai2"
    return {
        "schema_version": "be.ai2.processing.request.v1",
        "request_id": request_id,
        "idempotency_key": request_id,
        "attempt": 1,
        "task_id": run_id,
        "dossier_id": dossier_id,
        "snapshots": [snapshot for _, snapshot in wire_selected],
        "snapshot_identities": snapshot_identities,
        "dossier_members": dossier_members,
        "role_relation_map": role_relation_map,
        "policy_flags": {
            "egress_allowed": False,
            "use_vector": True,
            "budget_limits": {
                "max_processing_seconds": 300,
                "max_llm_calls": 20,
                "max_embedding_tokens": 50_000,
            },
        },
        "_created_at": datetime.now(tz=UTC).isoformat(),
    }


def strip_internal_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove backend-only metadata before schema validation/signing."""

    result = dict(payload)
    result.pop("_created_at", None)
    return result


__all__ = ["build_processing_request", "strip_internal_fields"]
