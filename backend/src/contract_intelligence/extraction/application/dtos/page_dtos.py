"""DTOs for Page endpoints — Phase 2 alignment with openapi.yaml Page schema."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict


class PageDTO(BaseModel):
    """Page metadata (openapi.yaml: Page)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    page_no: int
    kind: str = "native"
    width_pt: float
    height_pt: float
    rotation: int = 0
    render_dpi: int = 300
    preview_uri: str | None = None
    render_uri: str | None = None
    quality: dict[str, Any] | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> PageDTO:
        quality = row.get("quality")
        if quality is None and row.get("features"):
            quality = _parse_json_obj(row["features"])
        return cls(
            id=row["id"],
            document_id=row.get("document_id", ""),
            page_no=int(row["page_no"]),
            kind=row.get("kind") or "native",
            width_pt=float(row["width_pt"]),
            height_pt=float(row["height_pt"]),
            rotation=int(row.get("rotation") or 0),
            render_dpi=int(row.get("render_dpi") or 300),
            preview_uri=row.get("preview_uri") or row.get("preview_blob_uri"),
            render_uri=row.get("render_uri") or row.get("render_blob_uri"),
            quality=quality if isinstance(quality, dict) else None,
        )


def _parse_json_obj(raw: object) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


__all__ = ["PageDTO"]
