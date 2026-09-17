"""Finding — 1 phát hiện xung đột hoặc khớp.

Tương ứng bảng ``finding`` (xem ``DOC-04c`` §8.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from contract_intelligence.shared.base import BaseEntity, new_ulid


class FindingType(str, Enum):
    STRUCTURED = "structured"  # rule-based compare
    SEMANTIC = "semantic"  # LLM compare


class Scope(str, Enum):
    WITHIN_DOCUMENT = "within_document"
    CONTRACT_ANNEX = "contract_annex"
    ANNEX_ANNEX = "annex_annex"


class Disposition(str, Enum):
    """Kết luận so sánh — 5 giá trị theo schema."""

    COMPARABLE_MATCH = "comparable_match"
    COMPARABLE_DIFFERENCE = "comparable_difference"
    CANDIDATE_AMENDMENT = "candidate_amendment"
    NOT_COMPARABLE = "not_comparable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(eq=False)
class Finding(BaseEntity[str]):
    id: str = field(default_factory=lambda: new_ulid("fnd_"))
    dossier_id: str = ""
    run_id: str = ""
    finding_type: FindingType = FindingType.STRUCTURED
    scope: Scope = Scope.CONTRACT_ANNEX
    key_or_topic: str = ""
    disposition: Disposition = Disposition.COMPARABLE_MATCH
    severity: Severity = Severity.LOW
    confidence: float = 0.0
    rationale: str | None = None
    method: str = ""  # "rule:money_compare@1" | "llm:..."
    trace_id: str | None = None
    observation_id: str | None = None
