"""Fact — 1 thực thể trích xuất.

Tương ứng bảng ``fact`` (xem ``DOC-04c`` §7.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from contract_intelligence.shared.base import BaseEntity, new_ulid


class FactType(str, Enum):
    """Phân loại fact — discriminator cho extractor & UI."""

    MONEY = "money"
    DATE = "date"
    DURATION = "duration"
    PARTY = "party"
    PERCENT = "percent"
    JURISDICTION = "jurisdiction"
    LAW_REFERENCE = "law_reference"
    FREE_TEXT = "free_text"


@dataclass(eq=False)
class Fact(BaseEntity[str]):
    id: str = field(default_factory=lambda: new_ulid("fct_"))
    document_id: str = ""
    run_id: str = ""
    key: str = ""  # vd "price.total", "date.signing"
    fact_type: FactType = FactType.FREE_TEXT
    raw_text: str = ""
    normalized_value: dict[str, object] | None = None
    context_clause_id: str | None = None
    context_text: str | None = None
    confidence: float = 0.0
    extractor: str = ""  # "rule:money@1" | "llm:gpt-5.6-terra@extract.v1"
    validation_status: str = "passed"
    validation_notes: dict[str, object] = field(default_factory=dict)
    citation_id: str = ""
    trace_id: str | None = None
    observation_id: str | None = None
