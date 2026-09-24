"""JobRepository — abstract."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from contract_intelligence.contract.domain.entities.job import Job, JobStatus
from contract_intelligence.shared.base import Page


@runtime_checkable
class JobRepository(Protocol):
    async def get(self, job_id: str) -> Job | None: ...

    async def list(
        self,
        *,
        dossier_id: str | None = None,
        status: JobStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[str]: ...

    async def add(self, job: Job) -> None: ...

    async def save(self, job: Job) -> None: ...

    async def delete(self, job_id: str) -> None: ...
