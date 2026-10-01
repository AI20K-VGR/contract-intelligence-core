"""Run-event delivery over PostgreSQL ``LISTEN/NOTIFY`` (DOC-11 §8).

SQLite has no NOTIFY, so this runs against a real Postgres migrated with
``alembic upgrade head``. Skipped unless ``CI_TEST_POSTGRES_URL`` points at a
disposable database (see ``test_postgres_invariants.py`` for a docker command).

- a committed status change reaches the listener and wakes that run's stream
- a rolled-back change sends nothing
- the SSE stream, fed only by the listener, delivers the change and closes
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM, JobORM
from contract_intelligence.extraction.infrastructure.persistence.orm import PipelineRunORM
from contract_intelligence.extraction.interfaces.api.routers.events_router import (
    _stream_run_events,
)
from contract_intelligence.shared.run_events import (
    PostgresRunEventListener,
    RunEventBroker,
    listen_dsn,
)

PG_URL = os.environ.get("CI_TEST_POSTGRES_URL", "")
TENANT_ID = "tenant-pg-events"
DOSSIER_ID = "dossier-pg-events"
JOB_ID = "job-pg-events"
RUN_ID = "run-pg-events"
BACKEND_DIR = Path(__file__).resolve().parents[2]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not PG_URL, reason="CI_TEST_POSTGRES_URL not set"),
]


@pytest.fixture(scope="module")
def migrated() -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": PG_URL},
        check=True,
    )


@pytest_asyncio.fixture
async def factory(migrated: None) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    engine = create_async_engine(PG_URL)
    async with engine.begin() as connection:
        tables = (
            await connection.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
                )
            )
        ).scalars()
        await connection.execute(text(f"TRUNCATE {', '.join(tables)} CASCADE"))
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        session.add(DossierORM(id=DOSSIER_ID, tenant_id=TENANT_ID, name="pg events"))
        await session.flush()
        session.add(
            JobORM(
                id=JOB_ID,
                tenant_id=TENANT_ID,
                dossier_id=DOSSIER_ID,
                status="processing",
                current_run_id=RUN_ID,
            )
        )
        await session.flush()
        session.add(
            PipelineRunORM(
                id=RUN_ID,
                tenant_id=TENANT_ID,
                job_id=JOB_ID,
                dossier_id=DOSSIER_ID,
                status="running",
                pipeline_version="test-v1",
            )
        )
        await session.commit()
    yield session_factory
    await engine.dispose()


@pytest_asyncio.fixture
async def listener_broker() -> AsyncGenerator[RunEventBroker, None]:
    broker = RunEventBroker()
    listener = PostgresRunEventListener(listen_dsn(PG_URL), broker)
    with broker.subscribe("__ready__") as ready:
        listener.start()
        # The listener wakes everyone once LISTEN is in place.
        await asyncio.wait_for(ready.wait(), timeout=10)
    yield broker
    await listener.stop()


async def _set_status(
    factory: async_sessionmaker[AsyncSession], status: str, *, commit: bool = True
) -> None:
    async with factory() as session:
        run = await session.get(PipelineRunORM, RUN_ID)
        assert run is not None
        run.status = status
        await session.flush()
        if commit:
            await session.commit()
        else:
            await session.rollback()


async def test_commit_notifies_and_rollback_does_not(
    factory: async_sessionmaker[AsyncSession], listener_broker: RunEventBroker
) -> None:
    with listener_broker.subscribe(RUN_ID) as wake:
        await _set_status(factory, "failed", commit=False)
        await asyncio.sleep(0.5)
        assert not wake.is_set(), "a rolled-back change must not notify"

        await _set_status(factory, "succeeded")
        await asyncio.wait_for(wake.wait(), timeout=5)


async def test_stream_fed_by_listener_delivers_and_closes(
    factory: async_sessionmaker[AsyncSession], listener_broker: RunEventBroker
) -> None:
    async with factory() as session:
        last_id = (
            await session.execute(
                text("SELECT max(id) FROM run_event WHERE run_id = :r"), {"r": RUN_ID}
            )
        ).scalar_one()

    stream = _stream_run_events(
        session_factory=factory,
        broker=listener_broker,
        tenant_id=TENANT_ID,
        run_id=RUN_ID,
        after_id=last_id,
        heartbeat_interval=30.0,  # far longer than the test: only NOTIFY can wake it
    )
    assert "run.started" in await anext(stream)
    pending = asyncio.ensure_future(anext(stream))
    await asyncio.sleep(0.2)
    assert not pending.done()

    loop = asyncio.get_running_loop()
    started = loop.time()
    await _set_status(factory, "succeeded")
    chunk = await asyncio.wait_for(pending, timeout=5)
    latency = loop.time() - started

    assert "event: run.status_changed" in chunk
    assert '"status": "succeeded"' in chunk
    assert latency < 1.0, f"commit → SSE took {latency:.3f}s"
    assert "event: run.completed" in await anext(stream)
