"""Stub SQLAlchemy impl cho ReviewItemRepository."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.review.domain.entities.review_item import (
    ReviewItem,
    ReviewPriority,
)


class SqlReviewItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, review_item_id: str) -> ReviewItem | None:
        raise NotImplementedError

    async def list_open(
        self,
        dossier_id: str,
        *,
        priority: ReviewPriority | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ReviewItem]:
        raise NotImplementedError

    async def try_increment_version(self, *, review_item_id: str, base_version: int) -> bool:
        """Sprint 2 — implement bằng:

        .. code-block:: sql

            UPDATE review_item
               SET version = version + 1, updated_at = now()
             WHERE id = :id AND version = :base_version

        Trả về ``rowcount > 0``.
        """
        raise NotImplementedError

    async def add(self, review_item: ReviewItem) -> None:
        raise NotImplementedError

    async def save(self, review_item: ReviewItem) -> None:
        raise NotImplementedError
