"""Compatibility adapter for the current OCR ``data/meta`` demo payload."""

from __future__ import annotations

from typing import Any, Mapping


def is_ocr_json_demo(payload: Any) -> bool:
    return (
        isinstance(payload, Mapping)
        and isinstance(payload.get("data"), list)
        and isinstance(payload.get("meta"), Mapping)
    )


def _as_int(value: Any, default: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if result >= 1 else default


def _bbox(region: Any) -> list[float] | None:
    if not isinstance(region, Mapping):
        return None
    value = region.get("bbox")
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError):
        return None


def normalize_ocr_json(payload: Mapping[str, Any], *, source_digest: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Convert data/meta nodes into degraded page-text evidence for the demo."""

    raw_nodes = payload.get("data")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise ValueError("ocr.json must contain a non-empty data[] array")
    document_ids = {
        str(node.get("document_id"))
        for node in raw_nodes
        if isinstance(node, Mapping) and node.get("document_id")
    }
    if len(document_ids) != 1:
        raise ValueError("demo adapter requires exactly one document_id in data[]")
    document_id = next(iter(document_ids))
    nodes = [node for node in raw_nodes if isinstance(node, Mapping) and str(node.get("text") or "").strip()]
    nodes.sort(key=lambda node: (_as_int(node.get("page_start"), 1), str(node.get("stable_path") or ""), str(node.get("id") or "")))
    page_lines: dict[int, list[dict[str, Any]]] = {}
    for index, node in enumerate(nodes, start=1):
        regions = node.get("regions") if isinstance(node.get("regions"), list) else []
        region = next((item for item in regions if isinstance(item, Mapping)), None)
        page_no = _as_int(region.get("page_no") if region else None, _as_int(node.get("page_start"), 1))
        bbox = _bbox(region)
        line: dict[str, Any] = {
            "line_id": str(node.get("id") or f"ocr-node:{index}"),
            "raw_text": str(node.get("text") or ""),
            "bbox_source": "measured" if bbox else "absent",
            "geometry_status": "measured" if bbox else "absent",
            "words": [],
        }
        if bbox:
            line["bbox"] = bbox
        page_lines.setdefault(page_no, []).append(line)
    pages = []
    for page_no in sorted(page_lines):
        lines = page_lines[page_no]
        pages.append({
            "page_number": page_no,
            "status": "PARTIAL",
            "text": "\n".join(str(line["raw_text"]) for line in lines),
            "lines": lines,
            "geometry_available": any("bbox" in line for line in lines),
        })
    normalized = {
        "document_id": document_id,
        "filename": "ocr.json",
        "dossier_id": f"demo-dossier:{document_id}",
        "run_id": f"demo-run:{source_digest[:16]}",
        "page_count": len(pages),
        "full_text": "\n\n".join(page["text"] for page in pages),
        "pages": pages,
    }
    summary = {
        "adapter": "ocr-json-data-meta-v0-demo",
        "source_sha256": source_digest,
        "source_document_id": document_id,
        "source_node_count": len(raw_nodes),
        "mapped_node_count": len(nodes),
        "mapped_page_count": len(pages),
        "limitations": [
            "document_role is not present; treated as body for demo",
            "current legacy adapter does not retain parent/children relation in AI2 nodes",
            "citations use synthetic legacy line ids, not original source node ids",
            "words, tables, and page dimensions are unavailable",
            "all pages are marked PARTIAL and final output requires review",
        ],
    }
    return normalized, summary
