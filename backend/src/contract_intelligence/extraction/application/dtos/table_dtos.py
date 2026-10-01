"""DTOs for Tables — Phase 2 alignment with openapi.yaml DocTable / TableCell."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TableCellDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_idx: int
    col_idx: int
    row_span: int = 1
    col_span: int = 1
    text: str = ""
    bbox: list[float] = Field(default_factory=list)
    is_header: bool = False
    confidence: float = 0.0


class DocTableDTO(BaseModel):
    """Structured table (openapi.yaml: DocTable)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    page_no: int
    bbox: list[float] = Field(default_factory=list)
    rows_count: int = 0
    cols_count: int = 0
    has_borders: bool = True
    is_multi_page: bool = False
    continued_from: str | None = None
    cells: list[TableCellDTO] = Field(default_factory=list)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> DocTableDTO:
        return cls(
            id=row["id"],
            document_id=row.get("document_id", ""),
            page_no=int(row.get("page_no") or 0),
            bbox=_parse_bbox(row.get("bbox")),
            rows_count=int(row.get("rows_count") or 0),
            cols_count=int(row.get("cols_count") or 0),
            has_borders=_as_bool(row.get("has_borders"), default=True),
            is_multi_page=_as_bool(row.get("is_multi_page"), default=False),
            continued_from=row.get("continued_from"),
            cells=_parse_cells(row.get("cells")),
        )


def _as_bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    if value is None:
        return default
    return bool(value)


def _parse_bbox(raw: object) -> list[float]:
    if isinstance(raw, list):
        return [float(x) for x in raw]
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [float(x) for x in parsed]
    return []


def _parse_cells(raw: object) -> list[TableCellDTO]:
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

    cells: list[TableCellDTO] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        cells.append(
            TableCellDTO(
                row_idx=int(item.get("row_idx") or 0),
                col_idx=int(item.get("col_idx") or 0),
                row_span=int(item.get("row_span") or 1),
                col_span=int(item.get("col_span") or 1),
                text=str(item.get("text") or ""),
                bbox=_parse_bbox(item.get("bbox")),
                is_header=_as_bool(item.get("is_header"), default=False),
                confidence=float(item.get("confidence") or 0.0),
            )
        )
    return cells


__all__ = ["DocTableDTO", "TableCellDTO"]
