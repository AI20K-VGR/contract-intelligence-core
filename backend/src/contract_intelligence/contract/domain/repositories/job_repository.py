"""JobRepository — abstract."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, cast, runtime_checkable

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

    async def latest_by_dossiers(self, dossier_ids: Sequence[str]) -> dict[str, Job]:
        """Newest job of each given dossier, in one query.

        The default reads one dossier at a time, so a repository that does not
        override it still returns every job instead of an empty Protocol body.
        """
        latest: dict[str, Job] = {}
        for dossier_id in dossier_ids:
            job = await self.latest_for_dossier(dossier_id)
            if job is not None:
                latest[dossier_id] = job
        return latest

    async def add(self, job: Job) -> None: ...

    async def save(self, job: Job) -> None: ...

    async def delete(self, job_id: str) -> None: ...

    async def latest_for_dossier(self, dossier_id: str) -> Job | None:
        """Newest job of the dossier, or None (default: first row of ``list``)."""
        page = await self.list(dossier_id=dossier_id, limit=1, offset=0)
        return cast(Job, page.items[0]) if page.items else None
