"""Output DTO cho fact — read-only."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from contract_intelligence.extraction.domain.entities.fact import Fact, FactType


class FactResponse(BaseModel):
    """Snapshot 1 fact — kèm citation_id."""

    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    key: str
    fact_type: FactType
    raw_text: str
    normalized_value: dict | None
    confidence: float
    extractor: str
    citation_id: str

    @classmethod
    def from_domain(cls, fact: Fact) -> FactResponse:
        return cls(
            id=fact.id,
            document_id=fact.document_id,
            key=fact.key,
            fact_type=fact.fact_type,
            raw_text=fact.raw_text,
            normalized_value=fact.normalized_value,
            confidence=fact.confidence,
            extractor=fact.extractor,
            citation_id=fact.citation_id,
        )
