"""Review BC — application service."""

from __future__ import annotations

from typing import Any

from contract_intelligence.review.domain.entities.review_action import ReviewActionType
from contract_intelligence.review.domain.entities.review_item import (
    ReviewItemStatus,
    ReviewPriority,
)
from contract_intelligence.review.infrastructure.persistence.repository_impl import (
    ReviewRepositoryImpl,
)
from contract_intelligence.shared.exceptions import NotFoundError


class ReviewService:
    def __init__(
        self,
        *,
        repo: ReviewRepositoryImpl,
        tenant_id: str,
    ) -> None:
        self._repo = repo
        self._tenant_id = tenant_id

    async def list_review_items(
        self,
        dossier_id: str,
        *,
        priority: ReviewPriority | None = None,
        status_filter: ReviewItemStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        return await self._repo.list_by_dossier(
            dossier_id, priority=priority, status_filter=status_filter, limit=limit, offset=offset
        )

    async def get_review_item(self, item_id: str) -> dict[str, Any]:
        item = await self._repo.get_item(item_id)
        if item is None:
            raise NotFoundError(entity_type="ReviewItem", entity_id=item_id)
        return item

    async def list_revisions(self, item_id: str) -> list[dict[str, Any]]:
        # Verify item exists
        await self.get_review_item(item_id)
        return await self._repo.list_revisions(item_id)

    async def submit_action(
        self,
        *,
        item_id: str,
        action_type: ReviewActionType,
        base_version: int,
        reviewer_id: str,
        corrected_value: dict[str, Any] | None = None,
        corrected_bbox: list[dict[str, Any]] | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        return await self._repo.submit_action(
            item_id=item_id,
            action_type=action_type,
            base_version=base_version,
            reviewer_id=reviewer_id,
            corrected_value=corrected_value,
            corrected_bbox=corrected_bbox,
            comment=comment,
        )


__all__ = ["ReviewService"]
