"""DTOs for Re-OCR — Phase 4 OpenAPI alignment."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ReOcrProfile = Literal["high_res_binarize", "table_optimized", "handwritten_vietnamese"]


class ReOcrRequestPayloadDTO(BaseModel):
    """openapi.yaml: ReOcrRequestPayload."""

    model_config = ConfigDict(extra="forbid")

    profile: ReOcrProfile
    page_numbers: list[int] = Field(default_factory=list)
    reason: str | None = None


class ReOcrRequestRecordDTO(BaseModel):
    """openapi.yaml: ReOcrRequestRecord."""

    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    profile: str
    page_numbers: list[int] = Field(default_factory=list)
    status: str
    requested_by: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
    job_id: str | None = None
    reason: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ReOcrRequestRecordDTO:
        created = row.get("created_at")
        finished = row.get("finished_at") or row.get("completed_at")
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                created = None
        if isinstance(finished, str):
            try:
                finished = datetime.fromisoformat(finished.replace("Z", "+00:00"))
            except ValueError:
                finished = None

        raw_status = str(row.get("status") or "pending")
        status_map = {
            "queued": "pending",
            "pending": "pending",
            "running": "processing",
            "processing": "processing",
            "succeeded": "completed",
            "completed": "completed",
            "failed": "failed",
            "cancelled": "failed",
        }
        return cls(
            id=str(row.get("id") or ""),
            document_id=str(row.get("document_id") or ""),
            profile=str(row.get("profile") or "high_res_binarize"),
            page_numbers=list(row.get("page_numbers") or row.get("page_ids") or []),
            status=status_map.get(raw_status, raw_status),
            requested_by=row.get("requested_by"),
            created_at=created if isinstance(created, datetime) else None,
            completed_at=finished if isinstance(finished, datetime) else None,
            job_id=row.get("job_id"),
            reason=row.get("reason"),
        )


__all__ = ["ReOcrProfile", "ReOcrRequestPayloadDTO", "ReOcrRequestRecordDTO"]
