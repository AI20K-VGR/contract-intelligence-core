"""ReviewAction — append-only lịch sử thao tác reviewer.

Tương ứng bảng ``review_action`` (xem ``DOC-04c`` §9.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from contract_intelligence.shared.base import BaseEntity, new_ulid


class ReviewActionType(StrEnum):
    CONFIRM = "confirm"
    CORRECT = "correct"
    REJECT = "reject"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"


@dataclass(eq=False)
class ReviewAction(BaseEntity[str]):
    id: str = field(default_factory=lambda: new_ulid("ra_"))
    review_item_id: str = ""
    target_type: str = ""
    target_id: str = ""
    action: ReviewActionType = ReviewActionType.CONFIRM
    # P0-05 — echo lại version client đang xem (server atomic UPDATE version+=1)
    base_version: int = 0
    corrected_value: dict[str, object] | None = None
    corrected_bbox: list[dict[str, object]] | None = None
    comment: str | None = None
    reviewer_id: str = ""
