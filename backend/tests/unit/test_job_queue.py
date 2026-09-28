"""Unit tests for Postgres job queue claim / reaper (no Redis/Celery)."""

from __future__ import annotations

from datetime import timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from contract_intelligence.contract.infrastructure.persistence.orm import (
    DossierORM,
    JobORM,
)
from contract_intelligence.shared.base import new_ulid, utcnow
from contract_intelligence.shared.persistence.base import Base
from contract_intelligence.shared.persistence.job_queue import (
    claim_next_job,
    complete_job,
    enqueue_job,
    fail_job,
    reap_expired_leases,
)
from contract_intelligence.shared.persistence.orm_registry import import_all_models

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    import_all_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess:
        # Seed dossier + job
        dos_id = new_ulid("dos_")
        sess.add(
            DossierORM(
                id=dos_id,
                tenant_id="ten_test",
                name="Queue Test",
                status="uploaded",
            )
        )
        await sess.flush()
        job_id = new_ulid("job_")
        sess.add(
            JobORM(
                id=job_id,
                tenant_id="ten_test",
                dossier_id=dos_id,
                status="uploaded",
            )
        )
        await sess.commit()
        yield sess
    await engine.dispose()


async def test_claim_next_job(session: AsyncSession) -> None:
    claimed = await claim_next_job(session, worker_id="w1", lease_seconds=30)
    assert claimed is not None
    assert claimed.status == "processing"
    assert claimed.lease_owner == "w1"
    await session.commit()

    # Second claim finds nothing
    again = await claim_next_job(session, worker_id="w2", lease_seconds=30)
    assert again is None


async def test_reaper_requeues_expired_lease(session: AsyncSession) -> None:
    claimed = await claim_next_job(session, worker_id="w1", lease_seconds=30)
    assert claimed is not None
    # Force lease expiry
    job = await session.get(JobORM, claimed.id)
    assert job is not None
    job.lease_expires_at = utcnow() - timedelta(seconds=5)
    await session.commit()

    count = await reap_expired_leases(session)
    await session.commit()
    assert count == 1

    session.expire_all()
    job2 = await session.get(JobORM, claimed.id)
    assert job2 is not None
    assert job2.status == "uploaded"
    assert job2.lease_owner is None

    reclaimed = await claim_next_job(session, worker_id="w2", lease_seconds=30)
    assert reclaimed is not None
    assert reclaimed.id == claimed.id
    assert reclaimed.lease_owner == "w2"


async def test_complete_and_fail(session: AsyncSession) -> None:
    claimed = await claim_next_job(session, worker_id="w1", lease_seconds=30)
    assert claimed is not None
    await complete_job(session, job_id=claimed.id, worker_id="w1", status="pending_review")
    await session.commit()
    session.expire_all()
    job = await session.get(JobORM, claimed.id)
    assert job is not None
    assert job.status == "pending_review"
    assert job.lease_owner is None

    await enqueue_job(session, job_id=claimed.id, current_run_id="run_x")
    await session.commit()
    claimed2 = await claim_next_job(session, worker_id="w1", lease_seconds=30)
    assert claimed2 is not None
    await fail_job(
        session,
        job_id=claimed2.id,
        worker_id="w1",
        error_code="BOOM",
        error_detail="test",
    )
    await session.commit()
    session.expire_all()
    job3 = await session.get(JobORM, claimed2.id)
    assert job3 is not None
    assert job3.status == "failed"
    assert job3.error_code == "BOOM"
