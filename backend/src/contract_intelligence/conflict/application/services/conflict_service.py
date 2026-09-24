"""Conflict BC — application service."""

from __future__ import annotations

from typing import Any

from contract_intelligence.conflict.application.dtos.finding_dtos import FindingDTO
from contract_intelligence.conflict.domain.repositories import (
    AnnexLinkRepository,
    FindingRepository,
)
from contract_intelligence.shared.exceptions import NotFoundError


class ConflictService:
    def __init__(
        self,
        *,
        finding_repo: FindingRepository,
        annex_link_repo: AnnexLinkRepository,
        tenant_id: str,
    ) -> None:
        self._finding_repo = finding_repo
        self._annex_link_repo = annex_link_repo
        self._tenant_id = tenant_id

    async def list_findings(
        self,
        dossier_id: str,
        *,
        disposition: str | None = None,
        scope: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[FindingDTO], int]:
        rows, total = await self._finding_repo.list_by_dossier(
            dossier_id,
            disposition=disposition,
            scope=scope,
            limit=limit,
            offset=offset,
        )
        return [FindingDTO.from_row(r) for r in rows], total

    async def list_conflicts(
        self,
        dossier_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[FindingDTO], int]:
        """Findings needing reviewer attention (= v_conflict)."""
        rows, total = await self._finding_repo.list_conflicts_for_review(
            dossier_id, limit=limit, offset=offset
        )
        return [FindingDTO.from_row(r) for r in rows], total

    async def get_finding(self, finding_id: str) -> FindingDTO:
        finding = await self._finding_repo.get(finding_id)
        if finding is None:
            raise NotFoundError(entity_type="Finding", entity_id=finding_id)
        return FindingDTO.from_row(finding)

    async def list_annex_links(self, dossier_id: str) -> list[dict[str, Any]]:
        return await self._annex_link_repo.list_by_dossier(dossier_id)


__all__ = ["ConflictService"]
