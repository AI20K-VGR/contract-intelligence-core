"""Batch service — pure ORM CRUD wrapper, lives in infrastructure.

Layer: infrastructure/persistence (returns dicts, no domain entities).
Moved from contract.application.services để tuân thủ DDD dependency rule
(application layer KHÔNG được import infrastructure).
"""

from __future__ import annotations

import csv
import io
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.infrastructure.persistence.orm_others import BatchORM
from contract_intelligence.shared.base import new_ulid
from contract_intelligence.shared.exceptions import InvalidStateTransition, NotFoundError

_TERMINAL_STATUSES = frozenset({"completed", "cancelled", "failed", "partial_failed"})


class BatchService:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def create_batch(
        self,
        *,
        created_by: str,
        manifest_bytes: bytes,
        archive_bytes: bytes | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Create a batch from manifest.csv (+ optional ZIP archive).

        Manifest CSV columns: ``dossier_name,file,role,order`` (header required).
        """
        _ = archive_bytes  # reserved for ZIP fan-out
        dossier_names = self._parse_manifest(manifest_bytes)
        batch_id = new_ulid("bat_")
        dossier_ids = [new_ulid("dos_") for _ in dossier_names]
        job_ids = [new_ulid("job_") for _ in dossier_names]

        orm = BatchORM(
            id=batch_id,
            tenant_id=self._tenant_id,
            name=name or f"Batch {batch_id}",
            status="running",
            total_dossiers=len(dossier_ids),
            succeeded=0,
            failed=0,
            pending_review=0,
            total_cost_usd=0.0,
            created_by=created_by,
        )
        self._session.add(orm)
        await self._session.flush()

        return {
            "batch_id": batch_id,
            "dossier_count": len(dossier_ids),
            "dossier_ids": dossier_ids,
            "job_ids": job_ids,
        }

    async def list_batches(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = select(BatchORM).where(BatchORM.tenant_id == self._tenant_id)
        if status:
            if status == "processing":
                stmt = stmt.where(BatchORM.status.in_(("running", "paused", "processing")))
            else:
                stmt = stmt.where(BatchORM.status == status)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await self._session.execute(count_stmt)).scalar() or 0)
        stmt = stmt.order_by(BatchORM.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [self._to_dict(b) for b in result.scalars().all()], total

    async def get_batch(self, batch_id: str) -> dict[str, Any]:
        batch = await self._get_orm(batch_id)
        if batch is None:
            raise NotFoundError(entity_type="Batch", entity_id=batch_id)
        data = self._to_dict(batch)
        data["dossiers"] = []
        return data

    async def get_summary(self, batch_id: str) -> dict[str, Any]:
        batch = await self._get_orm(batch_id)
        if batch is None:
            raise NotFoundError(entity_type="Batch", entity_id=batch_id)
        total = int(batch.total_dossiers)
        succeeded = int(batch.succeeded)
        failed = int(batch.failed)
        pending_review = int(batch.pending_review)
        in_progress = max(0, total - succeeded - failed - pending_review)
        return {
            "batch_id": batch.id,
            "name": batch.name,
            "auto_paused": batch.status == "paused",
            "auto_pause_reason": None,
            "total": total,
            "done": succeeded,
            "needs_review": pending_review,
            "failed": failed,
            "in_progress": in_progress,
            "total_pages": 0,
            "total_cost_usd": float(batch.total_cost_usd),
            "wall_clock_seconds": 0.0,
            "dossiers_per_hour": 0.0,
            "error_code_distribution": {},
        }

    async def cancel_batch(self, batch_id: str) -> dict[str, Any]:
        batch = await self._get_orm(batch_id)
        if batch is None:
            raise NotFoundError(entity_type="Batch", entity_id=batch_id)
        if batch.status in _TERMINAL_STATUSES:
            raise InvalidStateTransition(
                from_state=batch.status,
                to_state="cancelled",
                entity="Batch",
            )
        batch.status = "cancelled"
        await self._session.flush()
        data = self._to_dict(batch)
        data["dossiers"] = []
        return data

    async def resume_batch(self, batch_id: str) -> dict[str, Any]:
        batch = await self._get_orm(batch_id)
        if batch is None:
            raise NotFoundError(entity_type="Batch", entity_id=batch_id)
        if batch.status not in ("paused", "failed", "partial_failed"):
            raise InvalidStateTransition(
                from_state=batch.status,
                to_state="running",
                entity="Batch",
            )
        batch.status = "running"
        await self._session.flush()
        data = self._to_dict(batch)
        data["dossiers"] = []
        return data

    async def _get_orm(self, batch_id: str) -> BatchORM | None:
        stmt = select(BatchORM).where(
            BatchORM.id == batch_id, BatchORM.tenant_id == self._tenant_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    def _parse_manifest(manifest_bytes: bytes) -> list[str]:
        text = manifest_bytes.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValueError("manifest.csv is empty or missing header")
        field_map = {h.strip().lower(): h for h in reader.fieldnames if h}
        name_key = field_map.get("dossier_name")
        if name_key is None:
            raise ValueError("manifest.csv must include dossier_name column")
        names: list[str] = []
        seen: set[str] = set()
        for row in reader:
            raw = (row.get(name_key) or "").strip()
            if not raw or raw in seen:
                continue
            seen.add(raw)
            names.append(raw)
        if not names:
            raise ValueError("manifest.csv has no dossier rows")
        return names

    @staticmethod
    def _to_dict(b: BatchORM) -> dict[str, Any]:
        return {
            "id": b.id,
            "batch_id": b.id,
            "name": b.name,
            "status": b.status,
            "total_dossiers": int(b.total_dossiers),
            "succeeded": int(b.succeeded),
            "failed": int(b.failed),
            "pending_review": int(b.pending_review),
            "total_cost_usd": float(b.total_cost_usd),
            "created_at": b.created_at,
        }


__all__ = ["BatchService"]
