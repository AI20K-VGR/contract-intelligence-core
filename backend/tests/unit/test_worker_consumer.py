"""Kafka consumer delivery semantics (offline).

- the offset is committed only after the handler succeeded or the record was
  dead-lettered, so a crash mid-handler redelivers the record
- a failing handler is retried, then parked on ``<topic>.dlq``
- undecodable records go straight to the DLQ instead of killing the loop
- if the DLQ publish itself fails the offset is NOT committed
- AI2 hand-off runs as a background task, one per run, and resumes after restart
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import AsyncGenerator, Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from aiokafka import TopicPartition
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import contract_intelligence.worker as worker
from contract_intelligence.config.settings import get_settings
from contract_intelligence.contract.infrastructure.persistence.orm import (
    DossierORM,
    JobORM,
)
from contract_intelligence.infrastructure import messaging
from contract_intelligence.shared.persistence import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models

TOPIC = "dossier_events"


@pytest.fixture(autouse=True)
def _fast_retries(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    settings = get_settings()
    monkeypatch.setattr(settings, "worker_handler_max_attempts", 3)
    monkeypatch.setattr(settings, "worker_handler_retry_backoff_seconds", 0.0)
    yield


@pytest.fixture(autouse=True)
def _reset_ai2_tasks() -> Iterator[None]:
    worker._ai2_tasks.clear()
    yield
    for task in worker._ai2_tasks.values():
        task.cancel()
    worker._ai2_tasks.clear()


@pytest_asyncio.fixture
async def factory(tmp_path: Any) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    import_all_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'consumer.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


def _record(value: bytes, *, offset: int = 41) -> SimpleNamespace:
    return SimpleNamespace(topic=TOPIC, partition=2, offset=offset, key=b"dos_1", value=value)


def _consumer() -> SimpleNamespace:
    return SimpleNamespace(commit=AsyncMock())


def _committed_offset(consumer: SimpleNamespace) -> int:
    consumer.commit.assert_awaited_once()
    (offsets,) = consumer.commit.await_args.args
    return offsets[TopicPartition(TOPIC, 2)]


def _dlq_calls() -> list[Any]:
    publish = messaging.publish_event
    assert isinstance(publish, AsyncMock)
    return [call for call in publish.await_args_list if call.args[0] == f"{TOPIC}.dlq"]


# ---------------------------------------------------------------------------
# Offset commit / retry / dead-letter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_success_commits_next_offset(factory: async_sessionmaker[AsyncSession]) -> None:
    handler = AsyncMock()
    consumer = _consumer()
    message = {"event": "dossier.uploaded", "dossier_id": "dos_1"}

    await worker._process_record(
        _record(json.dumps(message).encode()),
        consumer=consumer,
        handler=handler,
        session_factory=factory,
    )

    handler.assert_awaited_once()
    assert handler.await_args.args[1] == message
    assert _committed_offset(consumer) == 42
    assert _dlq_calls() == []


@pytest.mark.asyncio
async def test_transient_failure_is_retried_then_commits(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    handler = AsyncMock(side_effect=[RuntimeError("db blip"), None])
    consumer = _consumer()

    await worker._process_record(
        _record(b'{"event": "dossier.uploaded"}'),
        consumer=consumer,
        handler=handler,
        session_factory=factory,
    )

    assert handler.await_count == 2
    assert _committed_offset(consumer) == 42
    assert _dlq_calls() == []


@pytest.mark.asyncio
async def test_persistent_failure_is_dead_lettered_then_committed(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    handler = AsyncMock(side_effect=RuntimeError("still broken"))
    consumer = _consumer()

    await worker._process_record(
        _record(b'{"event": "dossier.uploaded", "dossier_id": "dos_1"}'),
        consumer=consumer,
        handler=handler,
        session_factory=factory,
    )

    assert handler.await_count == 3
    (dlq,) = _dlq_calls()
    payload = dlq.args[1]
    assert payload["source_topic"] == TOPIC
    assert (payload["partition"], payload["offset"], payload["attempts"]) == (2, 41, 3)
    assert payload["reason"] == "handler_failed"
    assert "still broken" in payload["error"]
    assert payload["value"] == {"event": "dossier.uploaded", "dossier_id": "dos_1"}
    assert dlq.kwargs["key"] == "dos_1"
    assert _committed_offset(consumer) == 42


@pytest.mark.asyncio
async def test_large_failed_record_is_parked_as_a_pointer(
    factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An AI1 result of several MB must not be copied into the DLQ message."""
    monkeypatch.setattr(get_settings(), "kafka_dead_letter_max_value_bytes", 64)
    raw = json.dumps({"event": "ocr", "text": "Điều 1. Hợp đồng " * 50}).encode()
    consumer = _consumer()

    await worker._process_record(
        _record(raw),
        consumer=consumer,
        handler=AsyncMock(side_effect=RuntimeError("boom")),
        session_factory=factory,
    )

    (dlq,) = _dlq_calls()
    payload = dlq.args[1]
    assert "value" not in payload
    assert payload["value_omitted"] is True
    assert payload["value_bytes"] == len(raw)
    assert payload["value_sha256"] == hashlib.sha256(raw).hexdigest()
    assert (payload["source_topic"], payload["partition"], payload["offset"]) == (TOPIC, 2, 41)
    assert _committed_offset(consumer) == 42


@pytest.mark.asyncio
async def test_undecodable_record_is_dead_lettered_without_calling_handler(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    handler = AsyncMock()
    consumer = _consumer()

    await worker._process_record(
        _record(b"not-json{"),
        consumer=consumer,
        handler=handler,
        session_factory=factory,
    )

    handler.assert_not_awaited()
    (dlq,) = _dlq_calls()
    assert dlq.args[1]["reason"] == "invalid_message"
    assert dlq.args[1]["value"] == "not-json{"
    assert _committed_offset(consumer) == 42


@pytest.mark.asyncio
async def test_dlq_publish_failure_leaves_offset_uncommitted(
    factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        messaging, "publish_event", AsyncMock(side_effect=RuntimeError("kafka down"))
    )
    consumer = _consumer()

    with pytest.raises(RuntimeError, match="kafka down"):
        await worker._process_record(
            _record(b'{"event": "x"}'),
            consumer=consumer,
            handler=AsyncMock(side_effect=RuntimeError("boom")),
            session_factory=factory,
        )

    consumer.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# AI2 hand-off: background task, one per run, resumed after restart
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ai2_hand_off_does_not_block_and_runs_once_per_run(
    factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    release = asyncio.Event()
    calls: list[str] = []

    async def slow_ai2(
        _session: AsyncSession, *, dossier_id: str, tenant_id: str, run_id: str
    ) -> None:
        calls.append(run_id)
        await release.wait()

    monkeypatch.setattr(worker, "_run_ai2_if_ready", slow_ai2)
    monkeypatch.setattr(worker, "_session_factory", factory)

    worker._schedule_ai2(dossier_id="dos_1", tenant_id="t1", run_id="run_1")
    worker._schedule_ai2(dossier_id="dos_1", tenant_id="t1", run_id="run_1")  # in flight
    for _ in range(5):
        await asyncio.sleep(0)

    assert calls == ["run_1"]
    assert "run_1" in worker._ai2_tasks

    release.set()
    await asyncio.gather(*worker._ai2_tasks.values())
    await asyncio.sleep(0)
    assert "run_1" not in worker._ai2_tasks


@pytest.mark.asyncio
async def test_superseded_run_cancels_its_ai2_task(
    factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def never_returns(_session: AsyncSession, **_kwargs: str) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(worker, "_run_ai2_if_ready", never_returns)
    monkeypatch.setattr(worker, "_session_factory", factory)

    worker._schedule_ai2(dossier_id="dos_1", tenant_id="t1", run_id="run_old")
    task = worker._ai2_tasks["run_old"]
    await asyncio.sleep(0)

    worker._forget_run("run_old")
    with pytest.raises(asyncio.CancelledError):
        await task

    assert task.cancelled()
    assert "run_old" not in worker._ai2_tasks


@pytest.mark.asyncio
async def test_resume_schedules_ai2_for_extracted_jobs_only(
    factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    async with factory() as session:
        for index, status in enumerate(("extracted", "processing", "pending_review")):
            session.add(DossierORM(id=f"dos_{index}", tenant_id="t1", name=status))
            session.add(
                JobORM(
                    id=f"job_{index}",
                    tenant_id="t1",
                    dossier_id=f"dos_{index}",
                    status=status,
                    current_run_id=f"run_{index}",
                )
            )
        await session.commit()

    scheduled: list[dict[str, str]] = []
    monkeypatch.setattr(worker, "_schedule_ai2", lambda **kwargs: scheduled.append(kwargs))

    await worker._resume_pending_ai2(factory)

    assert scheduled == [{"dossier_id": "dos_0", "tenant_id": "t1", "run_id": "run_0"}]


# ---------------------------------------------------------------------------
# processed_event: a redelivered record is not handled twice (DOC-11 #8)
# ---------------------------------------------------------------------------


def _named_handler(**kwargs: Any) -> AsyncMock:
    handler = AsyncMock(**kwargs)
    handler.__name__ = "handle_test"
    return handler


@pytest.mark.asyncio
async def test_redelivered_record_is_handled_once(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """Restart before the offset commit → Kafka redelivers the same record."""
    handler = _named_handler()
    raw = json.dumps({"event": "dossier.uploaded", "dossier_id": "dos_1"}).encode()

    await worker._process_record(
        _record(raw), consumer=_consumer(), handler=handler, session_factory=factory
    )
    redelivery = _consumer()
    await worker._process_record(
        _record(raw), consumer=redelivery, handler=handler, session_factory=factory
    )

    handler.assert_awaited_once()
    assert _committed_offset(redelivery) == 42  # skipped, but the offset moves on


@pytest.mark.asyncio
async def test_same_event_id_at_another_offset_is_skipped(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    handler = _named_handler()
    raw = json.dumps({"event_id": "evt_1", "event_type": "ai1.ocr.completed"}).encode()

    await worker._process_record(
        _record(raw, offset=41), consumer=_consumer(), handler=handler, session_factory=factory
    )
    await worker._process_record(
        _record(raw, offset=77), consumer=_consumer(), handler=handler, session_factory=factory
    )

    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_record_leaves_no_marker(factory: async_sessionmaker[AsyncSession]) -> None:
    raw = json.dumps({"event": "dossier.uploaded", "dossier_id": "dos_1"}).encode()
    failing = _named_handler(side_effect=RuntimeError("down"))
    await worker._process_record(
        _record(raw), consumer=_consumer(), handler=failing, session_factory=factory
    )

    # Replayed from the DLQ later, the same record must still run.
    handler = _named_handler()
    await worker._process_record(
        _record(raw), consumer=_consumer(), handler=handler, session_factory=factory
    )
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_markers_are_per_handler(factory: async_sessionmaker[AsyncSession]) -> None:
    raw = json.dumps({"event_id": "evt_shared"}).encode()
    first, second = _named_handler(), AsyncMock()
    second.__name__ = "handle_other"

    for handler in (first, second):
        await worker._process_record(
            _record(raw), consumer=_consumer(), handler=handler, session_factory=factory
        )

    first.assert_awaited_once()
    second.assert_awaited_once()
