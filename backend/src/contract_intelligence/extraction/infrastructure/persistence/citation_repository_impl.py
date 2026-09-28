"""Stub SQLAlchemy implementation cho CitationRepository."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.extraction.domain.entities.citation import Citation


class SqlCitationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, citation_id: str) -> Citation | None:
        raise NotImplementedError

    async def list_for_document(self, document_id: str, run_id: str) -> list[Citation]:
        raise NotImplementedError

    async def add(self, citation: Citation) -> None:
        raise NotImplementedError
