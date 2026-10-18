"""The newest job of a dossier is the same on the list and the detail page."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM, JobORM
from contract_intelligence.contract.infrastructure.persistence.repository_impl import (
    JobRepositoryImpl,
)
from contract_intelligence.shared.persistence import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models

TENANT = "ten_tie"


@pytest_asyncio.fixture
async def factory(tmp_path: Any) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    import_all_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'tie.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    same = datetime(2026, 10, 17, 8, 0, tzinfo=UTC)
    async with factory() as session:
        session.add(DossierORM(id="dos_tie", tenant_id=TENANT, name="d"))
        await session.flush()
        # Same created_at: the larger id wins, whatever order the rows were written in.
        for job_id in ("job_a", "job_z", "job_m"):
            session.add(JobORM(id=job_id, tenant_id=TENANT, dossier_id="dos_tie", created_at=same))
        await session.commit()
    yield factory
    await engine.dispose()


async def test_jobs_with_the_same_created_at_pick_the_same_newest(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as session:
        repo = JobRepositoryImpl(session, TENANT)
        by_dossier = await repo.latest_by_dossiers(["dos_tie"])
        latest = await repo.latest_for_dossier("dos_tie")
        page = await repo.list(dossier_id="dos_tie", limit=3)

    assert by_dossier["dos_tie"].id == "job_z"
    assert latest is not None and latest.id == "job_z"
    assert [job.id for job in page.items] == ["job_z", "job_m", "job_a"]
