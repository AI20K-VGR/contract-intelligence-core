"""Stub SQLAlchemy implementation cho PageRepository."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.extraction.domain.entities.page import Page


class SqlPageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, page_id: str) -> Page | None:
        raise NotImplementedError("Sprint 2")

    async def list_by_document(self, document_id: str) -> list[Page]:
        raise NotImplementedError

    async def add(self, page: Page) -> None:
        raise NotImplementedError
