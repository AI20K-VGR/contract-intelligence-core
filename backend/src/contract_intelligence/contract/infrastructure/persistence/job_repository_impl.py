"""SQLAlchemy persistence cho Job — stub Sprint 2."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.domain.entities.job import Job, JobStatus
from contract_intelligence.contract.domain.repositories.job_repository import JobRepository
from contract_intelligence.shared.base import Page


class SqlJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, job_id: str) -> Job | None:
        raise NotImplementedError

    async def list(
        self,
        *,
        dossier_id: str | None = None,
        status: JobStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page:
        raise NotImplementedError

    async def add(self, job: Job) -> None:
        raise NotImplementedError

    async def save(self, job: Job) -> None:
        raise NotImplementedError

    async def delete(self, job_id: str) -> None:
        raise NotImplementedError


_: type[JobRepository] = SqlJobRepository
