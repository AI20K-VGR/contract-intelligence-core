"""PageRepository Protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from contract_intelligence.extraction.domain.entities.page import Page


@runtime_checkable
class PageRepository(Protocol):
    async def get(self, page_id: str) -> Page | None: ...

    async def list_by_document(self, document_id: str) -> list[Page]: ...

    async def add(self, page: Page) -> None: ...
