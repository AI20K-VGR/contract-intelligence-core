"""Bounded context: review — HITL review queue, action log, approval.

Aggregate roots:

- ``ReviewItem`` — 1 item trong hàng đợi review
- ``ReviewAction`` — 1 thao tác của reviewer (append-only 🔒)
- ``DossierApproval`` — snapshot ký duyệt cuối (append-only 🔒)

Context này hiện thực **optimistic concurrency** (P0-05) trên ``ReviewItem.version``.
"""

from contract_intelligence.review.domain.entities.dossier_approval import DossierApproval
from contract_intelligence.review.domain.entities.review_action import (
    ReviewAction,
    ReviewActionType,
)
from contract_intelligence.review.domain.entities.review_item import (
    ReviewItem,
    ReviewItemStatus,
    ReviewPriority,
    ReviewTargetType,
)

__all__ = [
    "DossierApproval",
    "ReviewAction",
    "ReviewActionType",
    "ReviewItem",
    "ReviewItemStatus",
    "ReviewPriority",
    "ReviewTargetType",
]
