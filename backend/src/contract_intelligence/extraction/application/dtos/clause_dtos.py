"""DTOs for Clause tree — Phase 2 alignment with openapi.yaml ClauseNode."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ClauseRegionDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_no: int
    bbox: list[float] = Field(default_factory=list)
    bbox_source: str | None = None


class ClauseNodeDTO(BaseModel):
    """Nested clause tree node (openapi.yaml: ClauseNode)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    node_type: str
    label: str
    number: str | None = None
    title: str | None = None
    text: str = ""
    lang: str | None = None
    parent_id: str | None = None
    stable_path: str = ""
    page_start: int = 0
    page_end: int = 0
    confidence: float = 0.0
    regions: list[ClauseRegionDTO] = Field(default_factory=list)
    children: list[ClauseNodeDTO] = Field(default_factory=list)

    @classmethod
    def from_row(cls, row: dict[str, Any], *, stable_path: str = "") -> ClauseNodeDTO:
        return cls(
            id=row["id"],
            document_id=row.get("document_id", ""),
            node_type=row.get("node_type", "clause"),
            label=row.get("label", ""),
            number=row.get("number"),
            title=row.get("title") or None,
            text=row.get("text") or "",
            lang=row.get("lang"),
            parent_id=row.get("parent_id"),
            stable_path=stable_path or row.get("stable_path") or "",
            page_start=int(row.get("page_start") or 0),
            page_end=int(row.get("page_end") or 0),
            confidence=float(row.get("confidence") or 0.0),
            regions=_parse_regions(row.get("regions")),
            children=[],
        )


def build_clause_tree(flat_rows: list[dict[str, Any]]) -> list[ClauseNodeDTO]:
    """Build nested ClauseNode tree from flat parent_id rows."""
    nodes: dict[str, ClauseNodeDTO] = {row["id"]: ClauseNodeDTO.from_row(row) for row in flat_rows}
    roots: list[ClauseNodeDTO] = []
    for row in flat_rows:
        node = nodes[row["id"]]
        parent_id = row.get("parent_id")
        if parent_id and parent_id in nodes:
            nodes[parent_id].children.append(node)
        else:
            roots.append(node)

    def _assign_paths(node: ClauseNodeDTO, prefix: str) -> None:
        segment = _path_segment(node)
        node.stable_path = f"{prefix}/{segment}" if prefix else segment
        for child in node.children:
            _assign_paths(child, node.stable_path)

    for root in roots:
        _assign_paths(root, "")
    return roots


def _path_segment(node: ClauseNodeDTO) -> str:
    number = (node.number or "").strip() or "x"
    kind = (node.node_type or "clause").lower()
    short = {
        "article": "art",
        "clause": "cl",
        "point": "pt",
        "annex": "annex",
        "preamble": "preamble",
        "signature_block": "sig",
    }.get(kind, kind)
    return f"{short}-{number}"


def _parse_regions(raw: object) -> list[ClauseRegionDTO]:
    data: list[Any]
    if isinstance(raw, list):
        data = raw
    elif isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
        data = parsed if isinstance(parsed, list) else []
    else:
        return []

    regions: list[ClauseRegionDTO] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        bbox = item.get("bbox") or []
        if isinstance(bbox, str):
            try:
                bbox = json.loads(bbox)
            except json.JSONDecodeError:
                bbox = []
        regions.append(
            ClauseRegionDTO(
                page_no=int(item.get("page_no") or 0),
                bbox=[float(x) for x in bbox] if isinstance(bbox, list) else [],
                bbox_source=item.get("bbox_source"),
            )
        )
    return regions


__all__ = ["ClauseNodeDTO", "ClauseRegionDTO", "build_clause_tree"]
