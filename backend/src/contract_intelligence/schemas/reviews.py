"""Pydantic schemas for HITL review actions."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ReviewAction(StrEnum):
    """Allowed reviewer actions on a review item."""

    CONFIRM = "CONFIRM"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REJECT = "REJECT"


class ReviewActionRequest(BaseModel):
    """POST /review-items/{id}/actions request body."""

    model_config = ConfigDict(extra="forbid")

    action: ReviewAction
    base_version: int = Field(..., ge=0, description="Client-observed version; mismatch → 409.")
    reason: str | None = Field(default=None, max_length=2000)


__all__ = [
    "ReviewAction",
    "ReviewActionRequest",
]
