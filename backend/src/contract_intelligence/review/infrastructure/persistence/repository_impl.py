"""Review BC repositories + ReviewService với optimistic locking (P0-05)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.review.domain.entities.review_action import (
    ReviewActionType,
)
from contract_intelligence.review.domain.entities.review_item import (
    ReviewItemStatus,
    ReviewPriority,
)
from contract_intelligence.review.infrastructure.persistence.orm import (
    ReviewActionORM,
    ReviewItemORM,
)
from contract_intelligence.shared.base import new_ulid
from contract_intelligence.shared.exceptions import ReviewVersionConflict


class ReviewRepositoryImpl:
    """Review item + action repositories."""

    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    # -------------------------------------------------------------------------
    # ReviewItem
    # -------------------------------------------------------------------------

    async def list_by_dossier(
        self,
        dossier_id: str,
        *,
        priority: ReviewPriority | None = None,
        status_filter: ReviewItemStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = select(ReviewItemORM).where(
            ReviewItemORM.dossier_id == dossier_id,
            ReviewItemORM.tenant_id == self._tenant_id,
        )
        if priority:
            stmt = stmt.where(ReviewItemORM.priority == priority.value)
        if status_filter:
            stmt = stmt.where(ReviewItemORM.status == status_filter.value)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await self._session.execute(count_stmt)).scalar() or 0)
        # Sort priority P1 → P2 → P3 then by created_at
        stmt = (
            stmt.order_by(
                ReviewItemORM.priority.asc(),
                ReviewItemORM.created_at.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [self._item_to_dict(o) for o in result.scalars().all()], total

    async def get_item(self, item_id: str) -> dict[str, Any] | None:
        stmt = select(ReviewItemORM).where(
            ReviewItemORM.id == item_id, ReviewItemORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return self._item_to_dict(orm) if orm else None

    async def list_revisions(self, item_id: str) -> list[dict[str, Any]]:
        stmt = (
            select(ReviewActionORM)
            .where(
                ReviewActionORM.review_item_id == item_id,
                ReviewActionORM.tenant_id == self._tenant_id,
            )
            .order_by(ReviewActionORM.created_at)
        )
        result = await self._session.execute(stmt)
        return [
            {
                "id": a.id,
                "review_item_id": a.review_item_id,
                "action": a.action,
                "base_version": a.base_version,
                "corrected_value": a.corrected_value,
                "comment": a.comment,
                "reviewer_id": a.reviewer_id,
                "created_at": a.created_at.isoformat(),
            }
            for a in result.scalars().all()
        ]

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
        """Atomic submit với optimistic lock (P0-05).

        Returns:
            {action_id, new_version, current_version} sau khi UPDATE thành công.

        Raises:
            ReviewVersionConflict: nếu base_version không match current version.
            NotFoundError: nếu item không tồn tại.
        """
        # Lock row với SELECT FOR UPDATE — tránh race condition với retry
        stmt = (
            select(ReviewItemORM)
            .where(
                ReviewItemORM.id == item_id,
                ReviewItemORM.tenant_id == self._tenant_id,
            )
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            from contract_intelligence.shared.exceptions import NotFoundError

            raise NotFoundError(entity_type="ReviewItem", entity_id=item_id)

        if orm.version != base_version:
            # Conflict — client cần refetch
            raise ReviewVersionConflict(
                review_item_id=item_id,
                expected_version=base_version,
                current_version=orm.version,
            )

        # Insert action (append-only)
        action_orm = ReviewActionORM(
            id=new_ulid("ra_"),
            tenant_id=self._tenant_id,
            review_item_id=item_id,
            target_type=orm.target_type,
            target_id=orm.target_id,
            action=action_type.value,
            base_version=base_version,
            corrected_value=json.dumps(corrected_value) if corrected_value else None,
            corrected_bbox=json.dumps(corrected_bbox) if corrected_bbox else None,
            comment=comment,
            reviewer_id=reviewer_id,
        )
        self._session.add(action_orm)

        # Bump version + status transition
        new_version = orm.version + 1
        orm.version = new_version
        if action_type == ReviewActionType.CONFIRM:
            orm.status = ReviewItemStatus.RESOLVED.value
        elif action_type == ReviewActionType.NEEDS_MORE_EVIDENCE:
            orm.status = ReviewItemStatus.AWAITING_EVIDENCE.value

        from contract_intelligence.shared.base import utcnow

        orm.updated_at = utcnow()

        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ReviewVersionConflict(
                review_item_id=item_id,
                expected_version=base_version,
                current_version=orm.version,
            ) from exc

        return {
            "action_id": action_orm.id,
            "new_version": new_version,
            "current_version": new_version,
        }

    @staticmethod
    def _item_to_dict(orm: ReviewItemORM) -> dict[str, Any]:
        return {
            "id": orm.id,
            "dossier_id": orm.dossier_id,
            "run_id": orm.run_id,
            "target_type": orm.target_type,
            "target_id": orm.target_id,
            "reason": orm.reason,
            "priority": orm.priority,
            "status": orm.status,
            "version": orm.version,
            "source_trace_id": orm.source_trace_id,
            "source_observation_id": orm.source_observation_id,
            "created_at": orm.created_at.isoformat(),
            "updated_at": orm.updated_at.isoformat(),
        }


__all__ = ["ReviewRepositoryImpl"]
