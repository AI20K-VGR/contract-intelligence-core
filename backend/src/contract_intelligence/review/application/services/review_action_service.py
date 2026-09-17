"""Use case: ghi nhận ReviewAction với optimistic concurrency (P0-05).

Flow:

1. Nhận request kèm ``base_version``.
2. Gọi ``try_increment_version`` trên repository — nếu False → 409.
3. Trong cùng transaction, INSERT ``ReviewAction`` (append-only 🔒).
4. Trả về ``review_item.version`` mới cho client.
"""

from __future__ import annotations

import datetime as _dt

from contract_intelligence.review.domain.entities.review_action import (
    ReviewAction,
    ReviewActionType,
)
from contract_intelligence.review.domain.repositories.review_item_repository import (
    ReviewItemRepository,
)
from contract_intelligence.shared.base import new_ulid
from contract_intelligence.shared.exceptions import NotFoundError, ReviewVersionConflict


class ReviewActionService:
    def __init__(
        self,
        *,
        review_item_repo: ReviewItemRepository,
        # action_repo: ReviewActionRepository,  # append-only — Sprint 2
        reviewer_id: str,
    ) -> None:
        self._review_item_repo = review_item_repo
        self._reviewer_id = reviewer_id

    async def submit(
        self,
        *,
        review_item_id: str,
        action_type: ReviewActionType,
        base_version: int,
        corrected_value: dict[str, object] | None = None,
        corrected_bbox: list[dict[str, object]] | None = None,
        comment: str | None = None,
    ) -> ReviewAction:
        # 1. P0-05 optimistic concurrency
        ok = await self._review_item_repo.try_increment_version(
            review_item_id=review_item_id,
            base_version=base_version,
        )
        if not ok:
            # Lấy current version để trả về chi tiết
            current = await self._review_item_repo.get(review_item_id)
            if current is None:
                raise NotFoundError("ReviewItem", review_item_id)
            raise ReviewVersionConflict(
                review_item_id=review_item_id,
                expected_version=base_version,
                current_version=current.version,
            )

        # 2. Build action (append-only)
        # target_type/target_id: lấy từ item hiện tại
        item = await self._review_item_repo.get(review_item_id)
        if item is None:
            raise NotFoundError("ReviewItem", review_item_id)

        # 3. Persist (Sprint 2 — append ReviewActionRepository.add)
        return ReviewAction(
            id=new_ulid("ra_"),
            review_item_id=review_item_id,
            target_type=item.target_type.value,
            target_id=item.target_id,
            action=action_type,
            base_version=base_version,
            corrected_value=corrected_value,
            corrected_bbox=corrected_bbox,
            comment=comment,
            reviewer_id=self._reviewer_id,
            created_at=_dt.datetime.now(tz=_dt.UTC),
        )
