"""Use case: truy vấn finding + conflict."""

from typing import Any

from contract_intelligence.conflict.domain.entities.finding import (
    Disposition,
    Severity,
)
from contract_intelligence.conflict.domain.repositories.finding_repository import (
    FindingRepository,
)


class ConflictQueryService:
    """Use case — GET /dossiers/{id}/findings, /conflicts."""

    def __init__(self, *, finding_repo: FindingRepository) -> None:
        self._finding_repo = finding_repo

    async def list_conflicts(self, dossier_id: str) -> list[dict[str, Any]]:
        return await self._finding_repo.list_conflicts_for_review(dossier_id)

    async def list_all(
        self,
        dossier_id: str,
        *,
        disposition: Disposition | None = None,
        severity: Severity | None = None,
    ) -> list[dict[str, Any]]:
        """List findings cho dossier (filters chưa được apply — refactor sprint sau)."""
        items, _total = await self._finding_repo.list_by_dossier(dossier_id, limit=50, offset=0)
        return items
