"""Stub SQLAlchemy impl cho FindingRepository."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.conflict.domain.entities.finding import (
    Disposition,
    Finding,
    Severity,
)


class SqlFindingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, finding_id: str) -> Finding | None:
        raise NotImplementedError

    async def list_for_dossier(
        self,
        dossier_id: str,
        *,
        disposition: Disposition | None = None,
        severity: Severity | None = None,
        min_confidence: float | None = None,
    ) -> list[Finding]:
        raise NotImplementedError

    async def list_conflicts_for_review(self, dossier_id: str) -> list[Finding]:
        raise NotImplementedError

    async def add(self, finding: Finding) -> None:
        raise NotImplementedError
