"""DTOs for HITL Review endpoints — Phase 3 OpenAPI alignment."""

from __future__ import annotations

import contextlib
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReviewItemDTO(BaseModel):
    """Review queue item (openapi.yaml: ReviewItem)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    dossier_id: str
    run_id: str
    target_type: str
    target_id: str
    reason: str = ""
    priority: str = "P3"
    status: str = "open"
    version: int = 1
    source_trace_id: str | None = None
    source_observation_id: str | None = None
    target_snapshot: dict[str, Any] | None = None
    created_at: datetime | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ReviewItemDTO:
        created = row.get("created_at")
        if isinstance(created, str):
            with contextlib.suppress(ValueError):
                created = datetime.fromisoformat(created.replace("Z", "+00:00"))
        if not isinstance(created, datetime):
            created = None
        return cls(
            id=row["id"],
            dossier_id=row.get("dossier_id", ""),
            run_id=row.get("run_id", ""),
            target_type=row.get("target_type", ""),
            target_id=row.get("target_id", ""),
            reason=row.get("reason") or "",
            priority=row.get("priority") or "P3",
            status=row.get("status") or "open",
            version=int(row.get("version") or 1),
            source_trace_id=row.get("source_trace_id"),
            source_observation_id=row.get("source_observation_id"),
            target_snapshot=row.get("target_snapshot")
            if isinstance(row.get("target_snapshot"), dict)
            else None,
            created_at=created,
        )


class ReviewActionRequestDTO(BaseModel):
    """POST /review-items/{id}/actions body (openapi.yaml: ReviewActionRequest)."""

    model_config = ConfigDict(extra="forbid")

    action: str = Field(..., description="confirm | correct | reject | needs_more_evidence")
    base_version: int = Field(
        ...,
        ge=0,
        description="Version client saw (0 = machine baseline). Mismatch → 409.",
    )
    corrected_value: dict[str, Any] | None = None
    corrected_bbox: list[Any] | None = None
    comment: str | None = Field(default=None, max_length=2000)


class ReviewActionResponseDTO(BaseModel):
    """Successful action response (openapi.yaml: ReviewActionResponse)."""

    model_config = ConfigDict(extra="forbid")

    review_action_id: str
    item_status: str
    new_version: int
    effective_value: Any = None
    machine_value: Any = None
    job_status: str | None = None
    open_items_remaining: int | None = None
    idempotent_replay: bool = False


class ReviewItemRevisionDTO(BaseModel):
    """Append-only audit entry (openapi.yaml: ReviewItemRevision)."""

    model_config = ConfigDict(extra="forbid")

    revision_number: int
    action: str
    author_user_id: str
    author_role: str | None = None
    comment: str | None = None
    corrected_value: Any = None
    corrected_bbox: Any = None
    previous_version: int | None = None
    created_at: datetime | None = None

    @classmethod
    def from_action_row(cls, row: dict[str, Any], *, revision_number: int) -> ReviewItemRevisionDTO:
        created = row.get("created_at")
        if isinstance(created, str):
            with contextlib.suppress(ValueError):
                created = datetime.fromisoformat(created.replace("Z", "+00:00"))
        if not isinstance(created, datetime):
            created = None

        corrected_value = row.get("corrected_value")
        if isinstance(corrected_value, str):
            with contextlib.suppress(json.JSONDecodeError):
                corrected_value = json.loads(corrected_value)

        corrected_bbox = row.get("corrected_bbox")
        if isinstance(corrected_bbox, str):
            with contextlib.suppress(json.JSONDecodeError):
                corrected_bbox = json.loads(corrected_bbox)

        base_version = int(row.get("base_version") or 0)
        return cls(
            revision_number=revision_number,
            action=str(row.get("action") or ""),
            author_user_id=str(row.get("reviewer_id") or row.get("author_user_id") or ""),
            author_role=row.get("author_role"),
            comment=row.get("comment"),
            corrected_value=corrected_value,
            corrected_bbox=corrected_bbox,
            previous_version=base_version,
            created_at=created,
        )


class ReviewConflictErrorDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = "VERSION_CONFLICT"
    message: str


class ReviewConflictResponseDTO(BaseModel):
    """409 body (openapi.yaml: ReviewConflictResponse)."""

    model_config = ConfigDict(extra="forbid")

    error: ReviewConflictErrorDTO
    current_state: dict[str, Any] | None = None
    your_submitted_action: dict[str, Any] | None = None


__all__ = [
    "ReviewActionRequestDTO",
    "ReviewActionResponseDTO",
    "ReviewConflictErrorDTO",
    "ReviewConflictResponseDTO",
    "ReviewItemDTO",
    "ReviewItemRevisionDTO",
]
