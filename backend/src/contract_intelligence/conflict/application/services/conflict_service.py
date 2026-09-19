"""Conflict BC — application service."""

from __future__ import annotations

from typing import Any

from contract_intelligence.conflict.infrastructure.persistence.repository_impl import (
    AnnexLinkRepositoryImpl,
    FindingRepositoryImpl,
)
from contract_intelligence.shared.exceptions import NotFoundError


class ConflictService:
    def __init__(
        self,
        *,
        finding_repo: FindingRepositoryImpl,
        annex_link_repo: AnnexLinkRepositoryImpl,
        tenant_id: str,
    ) -> None:
        self._finding_repo = finding_repo
        self._annex_link_repo = annex_link_repo
        self._tenant_id = tenant_id

    async def list_findings(
        self, dossier_id: str, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        return await self._finding_repo.list_by_dossier(dossier_id, limit=limit, offset=offset)

    async def get_finding(self, finding_id: str) -> dict[str, Any]:
        finding = await self._finding_repo.get(finding_id)
        if finding is None:
            raise NotFoundError(entity_type="Finding", entity_id=finding_id)
        return finding

    async def list_annex_links(self, dossier_id: str) -> list[dict[str, Any]]:
        return await self._annex_link_repo.list_by_dossier(dossier_id)


__all__ = ["ConflictService"]
