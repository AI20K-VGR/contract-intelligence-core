"""FactRepository Protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from contract_intelligence.extraction.domain.entities.fact import Fact


@runtime_checkable
class FactRepository(Protocol):
    async def get(self, fact_id: str) -> Fact | None: ...

    async def list_by_document(self, document_id: str, run_id: str) -> list[Fact]: ...

    async def list_by_key(self, key: str) -> list[Fact]: ...

    async def add(self, fact: Fact) -> None: ...
