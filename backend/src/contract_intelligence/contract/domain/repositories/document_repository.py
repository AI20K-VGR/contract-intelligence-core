"""DocumentRepository — abstract."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from contract_intelligence.contract.domain.entities.document import Document, DocumentRole
from contract_intelligence.shared.base import Page


@runtime_checkable
class DocumentRepository(Protocol):
    async def get(self, document_id: str) -> Document | None: ...

    async def list_by_dossier(self, dossier_id: str) -> list[Document]: ...

    async def list(
        self,
        *,
        dossier_id: str | None = None,
        role: DocumentRole | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[str]: ...

    async def add(self, document: Document) -> None: ...

    async def save(self, document: Document) -> None: ...

    async def delete(self, document_id: str) -> None: ...
