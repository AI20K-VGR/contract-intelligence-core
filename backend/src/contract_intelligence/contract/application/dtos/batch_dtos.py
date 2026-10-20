"""DTOs for Batch API — Phase 4 OpenAPI alignment."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_STATUS_TO_API: dict[str, str] = {
    "running": "processing",
    "processing": "processing",
    "paused": "processing",
    "completed": "completed",
    "partial_failed": "partial_failed",
    "failed": "failed",
    "cancelled": "cancelled",
}


class BatchCreatedDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: str
    dossier_count: int = 0
    dossier_ids: list[str] = Field(default_factory=list)
    job_ids: list[str] = Field(default_factory=list)


class BatchListItemDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: str
    status: str
    total_dossiers: int = 0
    completed_dossiers: int = 0
    failed_dossiers: int = 0
    name: str | None = None
    created_at: datetime | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> BatchListItemDTO:
        created = row.get("created_at")
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                created = None
        raw_status = str(row.get("status") or "running")
        return cls(
            batch_id=str(row.get("batch_id") or row.get("id") or ""),
            status=_STATUS_TO_API.get(raw_status, raw_status),
            total_dossiers=int(row.get("total_dossiers") or 0),
            completed_dossiers=int(row.get("succeeded") or row.get("completed_dossiers") or 0),
            failed_dossiers=int(row.get("failed") or row.get("failed_dossiers") or 0),
            name=row.get("name"),
            created_at=created if isinstance(created, datetime) else None,
        )


class BatchDetailDTO(BatchListItemDTO):
    dossiers: list[dict[str, Any]] = Field(default_factory=list)


__all__ = ["BatchCreatedDTO", "BatchDetailDTO", "BatchListItemDTO"]
