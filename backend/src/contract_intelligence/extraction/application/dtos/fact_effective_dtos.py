"""DTOs for FactEffective — Phase 2 optimistic concurrency (current_version)."""

from __future__ import annotations

import contextlib
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _loads_maybe(raw: object) -> Any:
    """Parse JSON string if possible; otherwise return raw value."""
    if not isinstance(raw, str):
        return raw
    with contextlib.suppress(json.JSONDecodeError):
        return json.loads(raw)
    return raw


class CitationDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    run_id: str | None = None
    quote: str = ""
    quote_sha256: str = ""
    segments: list[Any] = Field(default_factory=list)
    doc_char_span: list[int] = Field(default_factory=list)
    coord_system: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any] | None) -> CitationDTO | None:
        if not row:
            return None
        segments = _loads_maybe(row.get("segments"))
        doc_span = row.get("doc_char_span")
        if not doc_span:
            doc_span = [row.get("doc_char_start", 0), row.get("doc_char_end", 0)]
        return cls(
            id=row["id"],
            document_id=row.get("document_id", ""),
            run_id=row.get("run_id"),
            quote=row.get("quote") or "",
            quote_sha256=row.get("quote_sha256") or "",
            segments=segments if isinstance(segments, list) else [],
            doc_char_span=[int(doc_span[0]), int(doc_span[1])]
            if isinstance(doc_span, list) and len(doc_span) >= 2
            else [],
            coord_system=row.get("coord_system"),
        )


class FactDTO(BaseModel):
    """Machine-extracted fact (openapi.yaml: Fact)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    run_id: str | None = None
    key: str
    fact_type: str
    raw_text: str = ""
    normalized_value: Any = None
    context_clause_id: str | None = None
    context_text: str | None = None
    confidence: float = 0.0
    extractor: str = ""
    validation_status: str = "skipped"
    citation: CitationDTO | None = None
    trace_id: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> FactDTO:
        normalized = _loads_maybe(row.get("normalized_value"))
        citation_row = row.get("citation")
        if citation_row is None and row.get("citation_id"):
            citation_row = {"id": row["citation_id"], "document_id": row.get("document_id", "")}
        return cls(
            id=row["id"],
            document_id=row.get("document_id", ""),
            run_id=row.get("run_id"),
            key=row.get("key", ""),
            fact_type=row.get("fact_type", ""),
            raw_text=row.get("raw_text") or "",
            normalized_value=normalized,
            context_clause_id=row.get("context_clause_id"),
            context_text=row.get("context_text"),
            confidence=float(row.get("confidence") or 0.0),
            extractor=row.get("extractor") or "",
            validation_status=row.get("validation_status") or "skipped",
            citation=CitationDTO.from_row(citation_row if isinstance(citation_row, dict) else None),
            trace_id=row.get("trace_id"),
        )


_ACTION_TO_REVIEW_STATE: dict[str | None, str] = {
    None: "unreviewed",
    "unreviewed": "unreviewed",
    "confirm": "confirmed",
    "confirmed": "confirmed",
    "correct": "corrected",
    "corrected": "corrected",
    "reject": "rejected",
    "rejected": "rejected",
    "needs_more_evidence": "awaiting_evidence",
    "awaiting_evidence": "awaiting_evidence",
}


class FactEffectiveDTO(BaseModel):
    """Fact + effective value + current_version for optimistic concurrency.

    Maps to openapi.yaml FactEffective. Client MUST echo ``current_version``
    as ``base_version`` when submitting a review action (Phase 3).
    """

    model_config = ConfigDict(extra="forbid")

    fact: FactDTO
    machine_value: Any = None
    effective_value: Any = None
    review_state: str = "unreviewed"
    reviewer_id: str | None = None
    reviewed_at: datetime | None = None
    review_item_id: str | None = None
    current_version: int = 0

    @classmethod
    def from_row(cls, row: dict[str, Any], *, effective: bool = True) -> FactEffectiveDTO:
        fact = FactDTO.from_row(row)
        machine_value = _loads_maybe(row.get("machine_value", fact.normalized_value))

        if not effective:
            return cls(
                fact=fact,
                machine_value=machine_value,
                effective_value=machine_value,
                review_state="unreviewed",
                current_version=0,
            )

        raw_state = row.get("review_state")
        review_state = _ACTION_TO_REVIEW_STATE.get(
            raw_state if isinstance(raw_state, str) or raw_state is None else None,
            "unreviewed",
        )
        effective_value = _loads_maybe(row.get("effective_value", machine_value))

        reviewed_at = row.get("reviewed_at")
        if isinstance(reviewed_at, str):
            try:
                reviewed_at = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
            except ValueError:
                reviewed_at = None

        return cls(
            fact=fact,
            machine_value=machine_value,
            effective_value=effective_value,
            review_state=review_state,
            reviewer_id=row.get("reviewer_id"),
            reviewed_at=reviewed_at if isinstance(reviewed_at, datetime) else None,
            review_item_id=row.get("review_item_id"),
            current_version=int(row.get("current_version") or 0),
        )


__all__ = ["CitationDTO", "FactDTO", "FactEffectiveDTO"]
