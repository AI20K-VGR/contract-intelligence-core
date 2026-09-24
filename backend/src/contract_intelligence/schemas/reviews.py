"""Pydantic schemas for HITL review actions."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReviewAction(StrEnum):
    """Allowed reviewer actions — DOC-05b public contract vocabulary."""

    CONFIRM = "confirm"
    CORRECT = "correct"
    REJECT = "reject"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"


class ReviewActionRequest(BaseModel):
    """POST /review-items/{id}/actions request body."""

    model_config = ConfigDict(extra="forbid")

    action: ReviewAction
    base_version: int = Field(..., ge=0, description="Client-observed version; mismatch → 409.")
    reason: str | None = Field(default=None, max_length=2000)
    corrected_value: dict[str, Any] | None = Field(default=None)
    corrected_bbox: list[dict[str, Any]] | None = Field(default=None)
    comment: str | None = Field(default=None, max_length=2000)


__all__ = [
    "ReviewAction",
    "ReviewActionRequest",
]
