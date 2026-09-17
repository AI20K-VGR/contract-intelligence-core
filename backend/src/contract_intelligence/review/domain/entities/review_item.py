"""ReviewItem — 1 item trong hàng đợi reviewer.

Tương ứng bảng ``review_item`` (xem ``DOC-04c`` §9.1).
Optimistic concurrency: ``version`` tăng mỗi action (P0-05).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from contract_intelligence.shared.base import BaseEntity, new_ulid


class ReviewTargetType(str, Enum):
    FACT = "fact"
    FINDING = "finding"
    ANNEX_LINK = "annex_link"
    CLAUSE = "clause"
    TABLE_CELL = "table_cell"
    CITATION = "citation"


class ReviewPriority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class ReviewItemStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    AWAITING_EVIDENCE = "awaiting_evidence"


@dataclass(eq=False)
class ReviewItem(BaseEntity[str]):
    id: str = field(default_factory=lambda: new_ulid("ri_"))
    dossier_id: str = ""
    run_id: str = ""
    target_type: ReviewTargetType = ReviewTargetType.FACT
    target_id: str = ""
    reason: str = ""
    priority: ReviewPriority = ReviewPriority.P3
    status: ReviewItemStatus = ReviewItemStatus.OPEN
    # P0-05 optimistic concurrency — tăng mỗi khi ReviewAction được ghi
    version: int = 1
    source_trace_id: str | None = None
    source_observation_id: str | None = None
