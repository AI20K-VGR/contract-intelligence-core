"""CitationRepository Protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from contract_intelligence.extraction.domain.entities.citation import Citation


@runtime_checkable
class CitationRepository(Protocol):
    async def get(self, citation_id: str) -> Citation | None: ...

    async def list_for_document(self, document_id: str, run_id: str) -> list[Citation]: ...

    async def add(self, citation: Citation) -> None: ...
