"""SQLAlchemy ORM models + service cho Batches bounded context.

Layer: infrastructure (persistence) + application (service).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.infrastructure.persistence.orm_others import BatchORM
from contract_intelligence.shared.exceptions import NotFoundError


class BatchService:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def list_batches(
        self, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        from sqlalchemy import func

        stmt = select(BatchORM).where(BatchORM.tenant_id == self._tenant_id)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await self._session.execute(count_stmt)).scalar() or 0)
        stmt = stmt.order_by(BatchORM.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [self._to_dict(b) for b in result.scalars().all()], total

    async def get_batch(self, batch_id: str) -> dict[str, Any]:
        batch = await self._get_orm(batch_id)
        if batch is None:
            raise NotFoundError(entity_type="Batch", entity_id=batch_id)
        return self._to_dict(batch)

    async def get_summary(self, batch_id: str) -> dict[str, Any]:
        batch = await self._get_orm(batch_id)
        if batch is None:
            raise NotFoundError(entity_type="Batch", entity_id=batch_id)
        return {
            "id": batch.id,
            "total_dossiers": int(batch.total_dossiers),
            "succeeded": int(batch.succeeded),
            "failed": int(batch.failed),
            "pending_review": int(batch.pending_review),
            "total_cost_usd": float(batch.total_cost_usd),
        }

    async def cancel_batch(self, batch_id: str) -> dict[str, Any]:
        batch = await self._get_orm(batch_id)
        if batch is None:
            raise NotFoundError(entity_type="Batch", entity_id=batch_id)
        batch.status = "cancelled"
        await self._session.flush()
        return {"id": batch.id, "status": batch.status}

    async def resume_batch(self, batch_id: str) -> dict[str, Any]:
        batch = await self._get_orm(batch_id)
        if batch is None:
            raise NotFoundError(entity_type="Batch", entity_id=batch_id)
        batch.status = "running"
        await self._session.flush()
        return {"id": batch.id, "status": batch.status}

    async def _get_orm(self, batch_id: str) -> BatchORM | None:
        stmt = select(BatchORM).where(
            BatchORM.id == batch_id, BatchORM.tenant_id == self._tenant_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    def _to_dict(b: BatchORM) -> dict[str, Any]:
        return {
            "id": b.id,
            "name": b.name,
            "status": b.status,
            "total_dossiers": int(b.total_dossiers),
            "succeeded": int(b.succeeded),
            "failed": int(b.failed),
            "pending_review": int(b.pending_review),
            "total_cost_usd": float(b.total_cost_usd),
            "created_at": b.created_at.isoformat(),
        }


__all__ = ["BatchService"]
