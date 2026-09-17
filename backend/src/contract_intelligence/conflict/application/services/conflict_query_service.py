"""Use case: truy vấn finding + conflict."""

from contract_intelligence.conflict.domain.entities.finding import (
    Disposition,
    Finding,
    Severity,
)
from contract_intelligence.conflict.domain.repositories.finding_repository import (
    FindingRepository,
)


class ConflictQueryService:
    """Use case — GET /dossiers/{id}/findings, /conflicts."""

    def __init__(self, *, finding_repo: FindingRepository) -> None:
        self._finding_repo = finding_repo

    async def list_conflicts(self, dossier_id: str) -> list[Finding]:
        return await self._finding_repo.list_conflicts_for_review(dossier_id)

    async def list_all(
        self,
        dossier_id: str,
        *,
        disposition: Disposition | None = None,
        severity: Severity | None = None,
    ) -> list[Finding]:
        return await self._finding_repo.list_for_dossier(
            dossier_id,
            disposition=disposition,
            severity=severity,
        )
