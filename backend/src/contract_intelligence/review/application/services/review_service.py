"""Review BC — application service (HITL queue + optimistic concurrency)."""

from __future__ import annotations

from typing import Any, Protocol

from contract_intelligence.review.application.dtos.review_dtos import (
    ReviewActionResponseDTO,
    ReviewItemDTO,
    ReviewItemRevisionDTO,
)
from contract_intelligence.review.domain.entities.review_action import ReviewActionType
from contract_intelligence.review.domain.entities.review_item import (
    ReviewItemStatus,
    ReviewPriority,
)
from contract_intelligence.shared.exceptions import NotFoundError, ValidationError


class ReviewRepositoryPort(Protocol):
    """Port used by ReviewService — infrastructure implements this."""

    async def list_by_dossier(
        self,
        dossier_id: str,
        *,
        priority: ReviewPriority | None = None,
        status_filter: ReviewItemStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]: ...

    async def get_item(self, item_id: str) -> dict[str, Any] | None: ...

    async def list_revisions(self, item_id: str) -> list[dict[str, Any]]: ...

    async def submit_action(
        self,
        *,
        item_id: str,
        action_type: ReviewActionType,
        base_version: int,
        reviewer_id: str,
        corrected_value: dict[str, Any] | None = None,
        corrected_bbox: list[Any] | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]: ...


class ReviewService:
    def __init__(
        self,
        *,
        repo: ReviewRepositoryPort,
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
    ) -> tuple[list[ReviewItemDTO], int]:
        rows, total = await self._repo.list_by_dossier(
            dossier_id,
            priority=priority,
            status_filter=status_filter,
            limit=limit,
            offset=offset,
        )
        return [ReviewItemDTO.from_row(r) for r in rows], total

    async def get_review_item(self, item_id: str) -> ReviewItemDTO:
        item = await self._repo.get_item(item_id)
        if item is None:
            raise NotFoundError(entity_type="ReviewItem", entity_id=item_id)
        return ReviewItemDTO.from_row(item)

    async def list_revisions(self, item_id: str) -> list[ReviewItemRevisionDTO]:
        await self.get_review_item(item_id)
        rows = await self._repo.list_revisions(item_id)
        return [
            ReviewItemRevisionDTO.from_action_row(row, revision_number=idx)
            for idx, row in enumerate(rows, start=1)
        ]

    async def submit_action(
        self,
        *,
        item_id: str,
        action_type: ReviewActionType,
        base_version: int,
        reviewer_id: str,
        corrected_value: dict[str, Any] | None = None,
        corrected_bbox: list[Any] | None = None,
        comment: str | None = None,
    ) -> ReviewActionResponseDTO:
        if action_type == ReviewActionType.CORRECT and not corrected_value and not corrected_bbox:
            raise ValidationError(
                "action=correct requires corrected_value or corrected_bbox",
                field="corrected_value",
            )

        result = await self._repo.submit_action(
            item_id=item_id,
            action_type=action_type,
            base_version=base_version,
            reviewer_id=reviewer_id,
            corrected_value=corrected_value,
            corrected_bbox=corrected_bbox,
            comment=comment,
        )
        return ReviewActionResponseDTO(
            review_action_id=str(result.get("review_action_id") or result.get("action_id")),
            item_status=str(result.get("item_status") or "open"),
            new_version=int(result["new_version"]),
            effective_value=result.get("effective_value"),
            machine_value=result.get("machine_value"),
            job_status=result.get("job_status"),
            open_items_remaining=result.get("open_items_remaining"),
            idempotent_replay=bool(result.get("idempotent_replay", False)),
        )


__all__ = ["ReviewRepositoryPort", "ReviewService"]
