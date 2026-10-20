"""ReviewItemRepository Protocol — đặc biệt hỗ trợ optimistic concurrency."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from contract_intelligence.review.domain.entities.review_item import (
    ReviewItem,
    ReviewPriority,
)


@runtime_checkable
class ReviewItemRepository(Protocol):
    async def get(self, review_item_id: str) -> ReviewItem | None: ...

    async def list_open(
        self,
        dossier_id: str,
        *,
        priority: ReviewPriority | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ReviewItem]: ...

    async def try_increment_version(self, *, review_item_id: str, base_version: int) -> bool:
        """Atomic UPDATE ``version += 1 WHERE version = base_version``.

        Trả về True nếu thành công, False nếu version conflict (0 row affected).
        Application service map False → ``ReviewVersionConflict``.
        """
        ...

    async def add(self, review_item: ReviewItem) -> None: ...

    async def save(self, review_item: ReviewItem) -> None: ...
