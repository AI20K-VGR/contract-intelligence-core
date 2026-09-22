"""SQLAlchemy ORM mapping cho Dossier — Sprint 2 sẽ implement đầy đủ.

Tạm thời file này giữ Protocol stub để import-linter pass. Khi Sprint 2
bắt đầu, thay bằng SQLAlchemy 2.x mapping.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.domain.entities.dossier import Dossier
from contract_intelligence.contract.domain.repositories.dossier_repository import (
    DossierRepository,
)
from contract_intelligence.shared.base import Page


class SqlDossierRepository:
    """Triển khai ``DossierRepository`` Protocol bằng SQLAlchemy async.

    Stub — Sprint 2 sẽ thay bằng implementation thật.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, dossier_id: str) -> Dossier | None:
        raise NotImplementedError("Sprint 2 — implement SQLAlchemy query")

    async def get_for_update(self, dossier_id: str) -> Dossier | None:
        raise NotImplementedError("Sprint 2 — implement SQLAlchemy query")

    async def list(
        self,
        *,
        batch_id: str | None = None,
        has_conflicts: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[str]:
        raise NotImplementedError

    async def add(self, dossier: Dossier) -> None:
        raise NotImplementedError

    async def save(self, dossier: Dossier) -> None:
        raise NotImplementedError

    async def delete(self, dossier_id: str) -> None:
        raise NotImplementedError


# Type-check assertion: SqlDossierRepository thỏa mãn Protocol
_: type[DossierRepository] = SqlDossierRepository  # type: ignore[assignment]
