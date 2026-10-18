"""JobRepository's default latest-job reads work for a repository with only ``list``."""

from __future__ import annotations

from typing import Any

import pytest

from contract_intelligence.contract.domain.entities.job import Job, JobStatus
from contract_intelligence.contract.domain.repositories.job_repository import JobRepository
from contract_intelligence.shared.base import Page


class _ListOnlyJobs(JobRepository):
    """Subclasses the Protocol and overrides only ``list``, newest first."""

    def __init__(self, jobs: list[Job]) -> None:
        self._jobs = jobs

    async def list(
        self,
        *,
        dossier_id: str | None = None,
        status: JobStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[str]:
        rows: list[Any] = [j for j in self._jobs if j.dossier_id == dossier_id]
        return Page(
            items=rows[offset : offset + limit], total=len(rows), limit=limit, offset=offset
        )


@pytest.mark.asyncio
async def test_inherited_latest_reads_return_jobs_not_none() -> None:
    newest = Job(dossier_id="dos_a")
    repo = _ListOnlyJobs([newest, Job(dossier_id="dos_a"), Job(dossier_id="dos_b")])

    assert await repo.latest_for_dossier("dos_a") is newest
    assert await repo.latest_for_dossier("dos_none") is None
    latest = await repo.latest_by_dossiers(["dos_a", "dos_b", "dos_none"])
    assert set(latest) == {"dos_a", "dos_b"}
    assert latest["dos_a"] is newest
