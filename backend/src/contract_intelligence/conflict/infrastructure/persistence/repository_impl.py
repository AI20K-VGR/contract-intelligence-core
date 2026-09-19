"""Conflict BC repositories — real SQLAlchemy async implementations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.conflict.infrastructure.persistence.orm import (
    AnnexLinkORM,
    FindingORM,
)


class FindingRepositoryImpl:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def list_by_dossier(
        self, dossier_id: str, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = select(FindingORM).where(
            FindingORM.dossier_id == dossier_id,
            FindingORM.tenant_id == self._tenant_id,
        )
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await self._session.execute(count_stmt)).scalar() or 0)
        stmt = stmt.order_by(FindingORM.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [self._finding_to_dict(f) for f in result.scalars().all()], total

    async def get(self, finding_id: str) -> dict[str, Any] | None:
        stmt = select(FindingORM).where(
            FindingORM.id == finding_id, FindingORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return self._finding_to_dict(orm) if orm else None

    def _finding_to_dict(self, orm: FindingORM) -> dict[str, Any]:
        return {
            "id": orm.id,
            "dossier_id": orm.dossier_id,
            "run_id": orm.run_id,
            "finding_type": orm.finding_type,
            "scope": orm.scope,
            "key_or_topic": orm.key_or_topic,
            "disposition": orm.disposition,
            "severity": orm.severity,
            "confidence": float(orm.confidence),
            "rationale": orm.rationale,
            "method": orm.method,
        }


class AnnexLinkRepositoryImpl:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def list_by_dossier(self, dossier_id: str) -> list[dict[str, Any]]:
        stmt = (
            select(AnnexLinkORM)
            .where(
                AnnexLinkORM.dossier_id == dossier_id,
                AnnexLinkORM.tenant_id == self._tenant_id,
            )
            .order_by(AnnexLinkORM.annex_sequence)
        )
        result = await self._session.execute(stmt)
        return [
            {
                "id": o.id,
                "annex_document_id": o.annex_document_id,
                "contract_document_id": o.contract_document_id,
                "score": float(o.score),
                "annex_sequence": int(o.annex_sequence),
                "effective_date": o.effective_date,
                "status": o.status,
                "citation_id": o.citation_id,
            }
            for o in result.scalars().all()
        ]


__all__ = ["AnnexLinkRepositoryImpl", "FindingRepositoryImpl"]
