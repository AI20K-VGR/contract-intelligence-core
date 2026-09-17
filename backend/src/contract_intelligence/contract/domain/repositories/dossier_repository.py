"""DossierRepository — abstract.

Triển khai cụ thể ở ``infrastructure/persistence/dossier_repository_impl.py``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from contract_intelligence.contract.domain.entities.dossier import Dossier
from contract_intelligence.shared.base import Page


@runtime_checkable
class DossierRepository(Protocol):
    """Protocol để application service có thể type-hint mà không cần ABC kế thừa.

    Triển khai concrete trong infrastructure. Application chỉ type-hint Protocol.
    """

    async def get(self, dossier_id: str) -> Dossier | None: ...

    async def list(
        self,
        *,
        batch_id: str | None = None,
        has_conflicts: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page: ...

    async def add(self, dossier: Dossier) -> None: ...

    async def save(self, dossier: Dossier) -> None: ...

    async def delete(self, dossier_id: str) -> None: ...
