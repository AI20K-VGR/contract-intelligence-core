"""Run-event outbox and SSE stream (sqlite, offline) — DOC-11 §8.

- a job/run/step status change stages one ``run_event`` in the same transaction
- rolled-back changes leave no event and wake nobody
- the stream replays from ``Last-Event-ID``, delivers live events, closes on a
  terminal run, and holds no DB session between reads
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM, JobORM
from contract_intelligence.contract.infrastructure.persistence.repository_impl import (
    DossierRepositoryImpl,
)
from contract_intelligence.extraction.infrastructure.persistence.orm import (
    PipelineRunORM,
    PipelineStepORM,
)
from contract_intelligence.extraction.interfaces.api.routers.events_router import (
    _format_event,
    _resume_id,
    _stream_run_events,
)
from contract_intelligence.shared.persistence import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models
from contract_intelligence.shared.run_events import (
    PostgresRunEventListener,
    RunEventBroker,
    RunEventORM,
    get_run_event_broker,
    listen_dsn,
    record_run_event,
)

TENANT = "tenant_test"
DOSSIER = "dos_test"
JOB = "job_test"
RUN = "run_test"


@pytest_asyncio.fixture
async def factory(tmp_path: Any) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    import_all_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'events.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        session.add(DossierORM(id=DOSSIER, tenant_id=TENANT, name="Events fixture"))
        session.add(
            JobORM(
                id=JOB,
                tenant_id=TENANT,
                dossier_id=DOSSIER,
                status="processing",
                current_run_id=RUN,
            )
        )
        await session.flush()
        session.add(
            PipelineRunORM(
                id=RUN, tenant_id=TENANT, job_id=JOB, dossier_id=DOSSIER, status="running"
            )
        )
        await session.commit()
    yield session_factory
    await engine.dispose()


async def _events(factory: async_sessionmaker[AsyncSession]) -> list[RunEventORM]:
    async with factory() as session:
        result = await session.execute(select(RunEventORM).order_by(RunEventORM.id))
        return list(result.scalars())


async def _set_run_status(
    factory: async_sessionmaker[AsyncSession], status: str, error_code: str | None = None
) -> None:
    async with factory() as session:
        run = await session.get(PipelineRunORM, RUN)
        assert run is not None
        run.status = status
        run.error_code = error_code
        await session.commit()


def _parse(chunks: list[str]) -> list[tuple[int | None, str, dict[str, Any] | None]]:
    """(id, event, data) per SSE message; heartbeats come back as ('', ...)."""
    parsed: list[tuple[int | None, str, dict[str, Any] | None]] = []
    for chunk in chunks:
        if chunk.startswith(":"):
            parsed.append((None, "", None))
            continue
        fields = dict(line.split(": ", 1) for line in chunk.strip().splitlines())
        event_id = int(fields["id"]) if "id" in fields else None
        data = json.loads(fields["data"]) if "data" in fields else None
        parsed.append((event_id, fields["event"], data))
    return parsed


# ──────────────────────────────────────────────────────────────────────────────
# Outbox hook
# ──────────────────────────────────────────────────────────────────────────────


async def test_fixture_rows_stage_their_initial_events(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    events = await _events(factory)
    assert [(e.type, json.loads(e.payload)["status"]) for e in events] == [
        ("job.status_changed", "processing"),
        ("run.status_changed", "running"),
    ]
    assert {e.run_id for e in events} == {RUN}
    assert {e.tenant_id for e in events} == {TENANT}


async def test_status_change_stages_one_event_and_unchanged_status_none(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    before = len(await _events(factory))
    await _set_run_status(factory, "running")  # same value → no event
    assert len(await _events(factory)) == before

    await _set_run_status(factory, "failed", "AI1_TIMEOUT")
    events = await _events(factory)
    assert len(events) == before + 1
    assert events[-1].type == "run.status_changed"
    assert json.loads(events[-1].payload) == {
        "run_id": RUN,
        "dossier_id": DOSSIER,
        "status": "failed",
        "error_code": "AI1_TIMEOUT",
    }


async def test_step_rows_stage_step_events(factory: async_sessionmaker[AsyncSession]) -> None:
    async with factory() as session:
        session.add(PipelineStepORM(tenant_id=TENANT, run_id=RUN, step="S2", status="running"))
        await session.commit()
    async with factory() as session:
        step = (await session.execute(select(PipelineStepORM))).scalar_one()
        step.status = "succeeded"
        step.pages = 12
        await session.commit()

    steps = [json.loads(e.payload) for e in await _events(factory) if e.type == "step.changed"]
    assert [(s["step"], s["status"]) for s in steps] == [("S2", "running"), ("S2", "succeeded")]
    assert steps[-1]["pages"] == 12


async def test_job_without_run_stages_nothing(factory: async_sessionmaker[AsyncSession]) -> None:
    before = len(await _events(factory))
    async with factory() as session:
        session.add(JobORM(id="job_2", tenant_id=TENANT, dossier_id=DOSSIER, status="uploaded"))
        await session.commit()
    assert len(await _events(factory)) == before


async def test_rollback_leaves_no_event_and_wakes_nobody(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    before = len(await _events(factory))
    broker = get_run_event_broker()
    with broker.subscribe(RUN) as wake:
        async with factory() as session:
            run = await session.get(PipelineRunORM, RUN)
            assert run is not None
            run.status = "failed"
            await session.flush()
            await session.rollback()
        assert not wake.is_set()
    assert len(await _events(factory)) == before


async def test_commit_wakes_local_subscribers_without_postgres(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    broker = get_run_event_broker()
    with broker.subscribe(RUN) as wake, broker.subscribe("other_run") as other:
        await _set_run_status(factory, "succeeded")
        assert wake.is_set()
        assert not other.is_set()
    assert broker.subscriber_count() == 0


async def test_dossier_deletion_closes_open_runs_with_an_event(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as session:
        assert await DossierRepositoryImpl(session, TENANT).begin_deletion(DOSSIER, "user_1")
        await session.commit()
    last = (await _events(factory))[-1]
    assert last.type == "run.status_changed"
    assert json.loads(last.payload)["status"] == "cancelled"
    assert json.loads(last.payload)["error_code"] == "DOSSIER_DELETED"


# ──────────────────────────────────────────────────────────────────────────────
# SSE stream
# ──────────────────────────────────────────────────────────────────────────────


async def test_stream_replays_after_last_event_id_then_closes_on_terminal_run(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    await _set_run_status(factory, "failed", "AI2_TIMEOUT")
    events = await _events(factory)
    resume_from = events[0].id  # client already saw the first event

    chunks = [
        chunk
        async for chunk in _stream_run_events(
            session_factory=factory,
            broker=RunEventBroker(),
            tenant_id=TENANT,
            run_id=RUN,
            after_id=resume_from,
        )
    ]
    parsed = _parse(chunks)

    assert parsed[0][1] == "run.started"
    assert parsed[0][0] is None  # the snapshot must not move Last-Event-ID
    assert parsed[0][2] is not None and parsed[0][2]["status"] == "failed"
    replayed_ids = [event_id for event_id, _, _ in parsed[1:-1]]
    assert replayed_ids == [e.id for e in events[1:]]
    assert parsed[-1][1:] == (
        "run.completed",
        {"run_id": RUN, "status": "failed", "error_code": "AI2_TIMEOUT"},
    )


async def test_stream_delivers_live_events_when_woken(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    broker = get_run_event_broker()  # the commit hook wakes this one
    already = (await _events(factory))[-1].id
    stream = _stream_run_events(
        session_factory=factory,
        broker=broker,
        tenant_id=TENANT,
        run_id=RUN,
        after_id=already,
        heartbeat_interval=5.0,
    )
    first = await anext(stream)
    assert "run.started" in first

    pending = asyncio.ensure_future(anext(stream))
    await asyncio.sleep(0.05)
    assert not pending.done()  # nothing new yet: the stream waits, it does not poll

    async with factory() as session:
        session.add(PipelineStepORM(tenant_id=TENANT, run_id=RUN, step="S3", status="running"))
        await session.commit()
    step_chunk = await asyncio.wait_for(pending, timeout=2.0)
    (_, event, data) = _parse([step_chunk])[0]
    assert event == "step.changed"
    assert data is not None and data["step"] == "S3"

    await _set_run_status(factory, "succeeded")
    rest = _parse([chunk async for chunk in stream])
    assert [e for _, e, _ in rest] == ["run.status_changed", "run.completed"]
    assert broker.subscriber_count(RUN) == 0


async def test_stream_sends_heartbeat_when_idle(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    stream = _stream_run_events(
        session_factory=factory,
        broker=RunEventBroker(),
        tenant_id=TENANT,
        run_id=RUN,
        after_id=(await _events(factory))[-1].id,
        heartbeat_interval=0.05,
    )
    await anext(stream)  # run.started
    assert await asyncio.wait_for(anext(stream), timeout=2.0) == ":heartbeat\n\n"
    await stream.aclose()


async def test_stream_other_tenant_sees_run_not_found(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    chunks = [
        chunk
        async for chunk in _stream_run_events(
            session_factory=factory,
            broker=RunEventBroker(),
            tenant_id="tenant_other",
            run_id=RUN,
        )
    ]
    assert _parse(chunks) == [(None, "error", {"error": "RUN_NOT_FOUND", "run_id": RUN})]


def test_format_event_and_resume_id() -> None:
    assert _format_event(event="step.changed", data={"a": 1}, event_id=7) == (
        'id: 7\nevent: step.changed\ndata: {"a": 1}\n\n'
    )
    assert _format_event(event="run.started") == "event: run.started\n\n"
    assert _resume_id("12", None) == 12
    assert _resume_id(None, 5) == 5
    assert _resume_id("12", 5) == 12
    assert _resume_id(None, None) == 0


# ──────────────────────────────────────────────────────────────────────────────
# PostgreSQL listener pieces that run without a server
# ──────────────────────────────────────────────────────────────────────────────


def test_listen_dsn_drops_the_sqlalchemy_driver() -> None:
    assert (
        listen_dsn("postgresql+asyncpg://ci:s3cret@db:5432/ci")
        == "postgresql://ci:s3cret@db:5432/ci"
    )


async def test_notification_wakes_only_that_run() -> None:
    broker = RunEventBroker()
    listener = PostgresRunEventListener("postgresql://unused", broker)
    with broker.subscribe(RUN) as wake, broker.subscribe("other") as other:
        listener._on_notification(None, 1, "run_events", json.dumps({"id": 3, "run_id": RUN}))
        listener._on_notification(None, 1, "run_events", "not json")
        assert wake.is_set()
        assert not other.is_set()


async def test_record_run_event_serialises_payload(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as session:
        record_run_event(
            session,
            tenant_id=TENANT,
            run_id=RUN,
            type="pages.progress",
            payload={"pages_done": 3, "total_pages": 10},
        )
        await session.commit()
    last = (await _events(factory))[-1]
    assert last.type == "pages.progress"
    assert json.loads(last.payload) == {"pages_done": 3, "total_pages": 10}
