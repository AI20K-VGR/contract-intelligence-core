"""CitationRepository Protocol.

Concrete impl (CitationRepositoryImpl) trả về ``dict[str, Any] | None``.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CitationRepository(Protocol):
    async def get(self, citation_id: str) -> dict[str, Any] | None: ...

    async def list_for_document(self, document_id: str, run_id: str) -> list[dict[str, Any]]: ...

    async def add(self, citation: object) -> None: ...
