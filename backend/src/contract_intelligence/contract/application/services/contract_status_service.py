"""Use case: truy vấn trạng thái job + dossier."""

from __future__ import annotations

from dataclasses import dataclass

from contract_intelligence.contract.application.dtos.contract_status_response import (
    ContractStatusResponse,
)
from contract_intelligence.contract.domain.entities.dossier import Dossier
from contract_intelligence.contract.domain.entities.job import Job
from contract_intelligence.contract.domain.repositories.dossier_repository import (
    DossierRepository,
)
from contract_intelligence.contract.domain.repositories.job_repository import JobRepository
from contract_intelligence.shared.exceptions import NotFoundError


class ContractStatusService:
    """Use case — GET /dossiers/{id}, GET /jobs/{id}."""

    def __init__(self, *, dossier_repo: DossierRepository, job_repo: JobRepository) -> None:
        self._dossier_repo = dossier_repo
        self._job_repo = job_repo

    async def get_dossier_status(self, dossier_id: str) -> ContractStatusResponse:
        dossier = await self._dossier_repo.get(dossier_id)
        if dossier is None:
            raise NotFoundError("Dossier", dossier_id)
        latest = dossier.latest_job()
        return ContractStatusResponse.from_domain(dossier=dossier, latest_job=latest)

    async def get_job_status(self, job_id: str) -> Job:
        job = await self._job_repo.get(job_id)
        if job is None:
            raise NotFoundError("Job", job_id)
        return job
