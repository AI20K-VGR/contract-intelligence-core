"""Reprocess on a dossier that has more than one job."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM, JobORM
from contract_intelligence.extraction.application.services.extraction_service import (
    ReprocessRequestConflict,
)
from contract_intelligence.extraction.infrastructure.persistence.repository_impl import (
    PipelineRunRepositoryImpl,
)
from contract_intelligence.shared.persistence import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models

TENANT_ID = "tenant-reprocess"
DOSSIER_ID = "dossier-reprocess"


@pytest_asyncio.fixture
async def factory(tmp_path: Path) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    import_all_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'reprocess.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    now = datetime.now(tz=UTC)
    async with session_factory() as session:
        session.add(DossierORM(id=DOSSIER_ID, tenant_id=TENANT_ID, name="two jobs"))
        await session.flush()
        for index, run_id in enumerate(("run-old", "run-new")):
            session.add(
                JobORM(
                    id=f"job-{index}",
                    tenant_id=TENANT_ID,
                    dossier_id=DOSSIER_ID,
                    current_run_id=run_id,
                    created_at=now + timedelta(minutes=index),
                )
            )
        await session.commit()
    yield session_factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_reprocess_uses_the_newest_job_instead_of_failing(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """Before: MultipleResultsFound (HTTP 500). Now the newest job is judged:
    its current run is ``run-new``, so a request based on ``run-old`` conflicts."""
    async with factory() as session:
        with pytest.raises(ReprocessRequestConflict):
            await PipelineRunRepositoryImpl(session, TENANT_ID).create_reprocess(
                dossier_id=DOSSIER_ID,
                actor_id="operator",
                idempotency_key="key-1",
                base_run_id="run-old",
                source_snapshot_digest="a" * 64,
                trace_id=None,
            )
