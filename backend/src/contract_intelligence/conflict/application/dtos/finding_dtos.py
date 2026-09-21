"""DTOs for Finding / Conflict list — Phase 2 alignment with openapi.yaml Finding."""

from __future__ import annotations

import contextlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FindingSideDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    side: str
    document_id: str
    document_role: str | None = None
    fact_id: str | None = None
    clause_node_id: str | None = None
    citation: dict[str, Any] | None = None
    value_snapshot: Any = None


class FindingReviewDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    status: str
    current_version: int = 0


class FindingDTO(BaseModel):
    """Finding payload (openapi.yaml: Finding)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    dossier_id: str
    run_id: str | None = None
    finding_type: str
    scope: str
    key_or_topic: str
    disposition: str
    severity: str
    confidence: float = 0.0
    rationale: str | None = None
    method: str = ""
    sides: list[FindingSideDTO] = Field(default_factory=list)
    disclaimer: str = "Kết quả so sánh kỹ thuật, không phải kết luận pháp lý."
    review: FindingReviewDTO | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> FindingDTO:
        sides_raw = row.get("sides") or []
        sides: list[FindingSideDTO] = []
        for side in sides_raw:
            if not isinstance(side, dict):
                continue
            snapshot = side.get("value_snapshot")
            if isinstance(snapshot, str):
                with contextlib.suppress(json.JSONDecodeError):
                    snapshot = json.loads(snapshot)
            sides.append(
                FindingSideDTO(
                    side=str(side.get("side") or ""),
                    document_id=str(side.get("document_id") or ""),
                    document_role=side.get("document_role"),
                    fact_id=side.get("fact_id"),
                    clause_node_id=side.get("clause_node_id"),
                    citation=side.get("citation")
                    if isinstance(side.get("citation"), dict)
                    else None,
                    value_snapshot=snapshot,
                )
            )

        review = None
        review_raw = row.get("review")
        if isinstance(review_raw, dict) and review_raw.get("item_id"):
            review = FindingReviewDTO(
                item_id=str(review_raw["item_id"]),
                status=str(review_raw.get("status") or "open"),
                current_version=int(review_raw.get("current_version") or 0),
            )

        return cls(
            id=row["id"],
            dossier_id=row.get("dossier_id", ""),
            run_id=row.get("run_id"),
            finding_type=row.get("finding_type", ""),
            scope=row.get("scope", ""),
            key_or_topic=row.get("key_or_topic", ""),
            disposition=row.get("disposition", ""),
            severity=row.get("severity", ""),
            confidence=float(row.get("confidence") or 0.0),
            rationale=row.get("rationale"),
            method=row.get("method") or "",
            sides=sides,
            disclaimer=row.get("disclaimer")
            or "Kết quả so sánh kỹ thuật, không phải kết luận pháp lý.",
            review=review,
        )


__all__ = ["FindingDTO", "FindingReviewDTO", "FindingSideDTO"]
