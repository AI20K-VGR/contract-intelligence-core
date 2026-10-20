"""SQLAlchemy persistence cho Document — stub Sprint 2."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.domain.entities.document import Document, DocumentRole
from contract_intelligence.contract.domain.repositories.document_repository import (
    DocumentRepository,
)
from contract_intelligence.shared.base import Page


class SqlDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, document_id: str) -> Document | None:
        raise NotImplementedError

    async def list_by_dossier(self, dossier_id: str) -> list[Document]:
        raise NotImplementedError

    async def list(
        self,
        *,
        dossier_id: str | None = None,
        role: DocumentRole | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[str]:
        raise NotImplementedError

    async def add(self, document: Document) -> None:
        raise NotImplementedError

    async def save(self, document: Document) -> None:
        raise NotImplementedError

    async def delete(self, document_id: str) -> None:
        raise NotImplementedError


_: type[DocumentRepository] = SqlDocumentRepository
