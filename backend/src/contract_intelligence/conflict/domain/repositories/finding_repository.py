"""FindingRepository Protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from contract_intelligence.conflict.domain.entities.finding import (
    Disposition,
    Finding,
    Severity,
)


@runtime_checkable
class FindingRepository(Protocol):
    async def get(self, finding_id: str) -> Finding | None: ...

    async def list_for_dossier(
        self,
        dossier_id: str,
        *,
        disposition: Disposition | None = None,
        severity: Severity | None = None,
        min_confidence: float | None = None,
    ) -> list[Finding]: ...

    async def list_conflicts_for_review(self, dossier_id: str) -> list[Finding]: ...

    async def add(self, finding: Finding) -> None: ...
