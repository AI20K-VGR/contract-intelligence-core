"""Stub SQLAlchemy implementation cho FactRepository."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.extraction.domain.entities.fact import Fact


class SqlFactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, fact_id: str) -> Fact | None:
        raise NotImplementedError

    async def list_by_document(self, document_id: str, run_id: str) -> list[Fact]:
        raise NotImplementedError

    async def list_by_key(self, key: str) -> list[Fact]:
        raise NotImplementedError

    async def add(self, fact: Fact) -> None:
        raise NotImplementedError
