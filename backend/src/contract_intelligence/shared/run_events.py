"""Run-event outbox and fan-out for real-time pipeline progress (DOC-11 §8).

Every status change of a ``job``, ``pipeline_run`` or ``pipeline_step`` row
becomes one ``run_event`` row, staged by a flush hook in the same transaction as
the change. On PostgreSQL the same flush calls ``pg_notify('run_events', …)``;
Postgres delivers it only when the transaction commits, so a listener never
hears about a change that was rolled back.

Each API process holds one ``LISTEN`` connection (:class:`PostgresRunEventListener`)
and wakes the SSE streams of the notified run through :class:`RunEventBroker`.
Streams then read the new rows by id, so the table — not the notification — is
the source of truth: a client reconnecting with ``Last-Event-ID`` gets every
event it missed, and a notification lost while the listener reconnects is
covered by waking every stream once the connection is back.

Without PostgreSQL (sqlite tests, single-process dev) the commit hook wakes the
local broker directly.

Status writes done with raw SQL bypass the hook; such call sites stage their
events with :func:`record_run_event`.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Iterator
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import BigInteger, DateTime, Index, Integer, Text, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Mapped, Session, attributes, mapped_column

from contract_intelligence.shared.base import utcnow
from contract_intelligence.shared.persistence.base import Base

logger = structlog.get_logger(__name__)

CHANNEL = "run_events"
TERMINAL_RUN_STATUSES = frozenset({"succeeded", "failed", "cancelled", "dead"})

_PENDING_KEY = "run_event_pending_run_ids"
_LOCAL_DELIVERY_KEY = "run_event_local_delivery"

# table name -> columns whose change is worth an event
_WATCHED: dict[str, tuple[str, ...]] = {
    "job": ("status", "error_code"),
    "pipeline_run": ("status", "error_code"),
    "pipeline_step": ("status", "attempt"),
}


class RunEventORM(Base):
    """One progress event of a pipeline run, in commit order (``id``)."""

    __tablename__ = "run_event"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str] = mapped_column(Text, nullable=False)
    dossier_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (Index("ix_run_event_run_id_id", "run_id", "id"),)


def record_run_event(
    session: Session | Any,
    *,
    tenant_id: str,
    run_id: str,
    type: str,  # noqa: A002 — mirrors the column
    payload: dict[str, Any],
    dossier_id: str | None = None,
) -> RunEventORM:
    """Stage one event on ``session`` (sync or async); the caller owns the commit."""
    row = RunEventORM(
        tenant_id=tenant_id or "unknown",
        run_id=run_id,
        dossier_id=dossier_id,
        type=type,
        payload=json.dumps(payload, ensure_ascii=False, default=str),
    )
    session.add(row)
    return row


# ──────────────────────────────────────────────────────────────────────────────
# Flush hooks — registered on every Session (sync and the ones behind AsyncSession)
# ──────────────────────────────────────────────────────────────────────────────


def _changed(obj: Any, columns: tuple[str, ...]) -> bool:
    return any(attributes.get_history(obj, column).has_changes() for column in columns)


def _event_for(obj: Any, table: str) -> dict[str, Any] | None:
    if table == "job":
        if not obj.current_run_id:
            return None
        return {
            "run_id": obj.current_run_id,
            "type": "job.status_changed",
            "payload": {
                "run_id": obj.current_run_id,
                "job_id": obj.id,
                "dossier_id": obj.dossier_id,
                "status": obj.status or "uploaded",
                "error_code": obj.error_code,
            },
        }
    if table == "pipeline_run":
        return {
            "run_id": obj.id,
            "type": "run.status_changed",
            "payload": {
                "run_id": obj.id,
                "dossier_id": obj.dossier_id,
                "status": obj.status or "queued",
                "error_code": obj.error_code,
            },
        }
    return {
        "run_id": obj.run_id,
        "type": "step.changed",
        "payload": {
            "run_id": obj.run_id,
            "step": obj.step,
            "document_id": obj.document_id,
            "status": obj.status or "queued",
            "attempt": obj.attempt or 1,
            "pages": obj.pages,
            "duration_ms": obj.duration_ms,
        },
    }


@event.listens_for(Session, "before_flush")
def _stage_run_events(session: Session, _flush_context: Any, _instances: Any) -> None:
    new = set(session.new)
    for obj in [*new, *session.dirty]:
        table = getattr(obj, "__tablename__", None)
        columns = _WATCHED.get(table or "")
        if columns is None or obj in session.deleted:
            continue
        if obj not in new and not _changed(obj, columns):
            continue
        staged = _event_for(obj, table or "")
        if staged is None:
            continue
        record_run_event(
            session,
            tenant_id=obj.tenant_id,
            run_id=staged["run_id"],
            dossier_id=staged["payload"].get("dossier_id"),
            type=staged["type"],
            payload=staged["payload"],
        )


@event.listens_for(Session, "after_flush")
def _notify_run_events(session: Session, _flush_context: Any) -> None:
    rows = [obj for obj in session.new if isinstance(obj, RunEventORM)]
    if not rows:
        return
    connection = session.connection()
    if connection.dialect.name == "postgresql":
        for row in rows:
            payload = json.dumps({"id": row.id, "run_id": row.run_id, "tenant_id": row.tenant_id})
            connection.execute(
                text("SELECT pg_notify(:channel, :payload)"),
                {
                    "channel": CHANNEL,
                    "payload": payload,
                },
            )
        return
    session.info[_LOCAL_DELIVERY_KEY] = True
    session.info.setdefault(_PENDING_KEY, set()).update(row.run_id for row in rows)


@event.listens_for(Session, "after_commit")
def _deliver_locally(session: Session) -> None:
    run_ids = session.info.pop(_PENDING_KEY, None)
    if run_ids and session.info.pop(_LOCAL_DELIVERY_KEY, False):
        broker = get_run_event_broker()
        for run_id in run_ids:
            broker.notify(run_id)


@event.listens_for(Session, "after_rollback")
def _drop_pending(session: Session) -> None:
    session.info.pop(_PENDING_KEY, None)
    session.info.pop(_LOCAL_DELIVERY_KEY, None)


# ──────────────────────────────────────────────────────────────────────────────
# Fan-out inside one process
# ──────────────────────────────────────────────────────────────────────────────


class RunEventBroker:
    """Wakes the streams that follow a run. Carries no data: streams read the table."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Event]] = {}

    @contextlib.contextmanager
    def subscribe(self, run_id: str) -> Iterator[asyncio.Event]:
        wake = asyncio.Event()
        self._subscribers.setdefault(run_id, set()).add(wake)
        try:
            yield wake
        finally:
            waiters = self._subscribers.get(run_id)
            if waiters is not None:
                waiters.discard(wake)
                if not waiters:
                    del self._subscribers[run_id]

    def notify(self, run_id: str) -> None:
        for wake in self._subscribers.get(run_id, ()):
            wake.set()

    def notify_all(self) -> None:
        for waiters in self._subscribers.values():
            for wake in waiters:
                wake.set()

    def subscriber_count(self, run_id: str | None = None) -> int:
        if run_id is not None:
            return len(self._subscribers.get(run_id, ()))
        return sum(len(waiters) for waiters in self._subscribers.values())


_broker = RunEventBroker()


def get_run_event_broker() -> RunEventBroker:
    return _broker


# ──────────────────────────────────────────────────────────────────────────────
# PostgreSQL LISTEN — one connection per API process
# ──────────────────────────────────────────────────────────────────────────────


def listen_dsn(database_url: str) -> str:
    """``postgresql+asyncpg://…`` → plain ``postgresql://…`` for :func:`asyncpg.connect`."""
    return make_url(database_url).set(drivername="postgresql").render_as_string(hide_password=False)


class PostgresRunEventListener:
    """Keeps a ``LISTEN run_events`` connection open and feeds the broker."""

    def __init__(
        self,
        dsn: str,
        broker: RunEventBroker,
        *,
        ping_interval: float = 30.0,
        retry_delay: float = 2.0,
        max_retry_delay: float = 30.0,
    ) -> None:
        self._dsn = dsn
        self._broker = broker
        self._ping_interval = ping_interval
        self._retry_delay = retry_delay
        self._max_retry_delay = max_retry_delay
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="run-event-listener")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    def _on_notification(self, _conn: Any, _pid: int, _channel: str, payload: str) -> None:
        try:
            run_id = json.loads(payload)["run_id"]
        except (ValueError, KeyError, TypeError):
            logger.warning("run_events.bad_payload", payload=payload[:200])
            return
        self._broker.notify(str(run_id))

    async def _run(self) -> None:
        import asyncpg  # type: ignore[import-untyped]

        delay = self._retry_delay
        while True:
            connection = None
            try:
                connection = await asyncpg.connect(self._dsn)
                closed = asyncio.Event()
                connection.add_termination_listener(lambda _conn, done=closed: done.set())
                await connection.add_listener(CHANNEL, self._on_notification)
                logger.info("run_events.listening")
                delay = self._retry_delay
                # Anything committed while we were not listening is in the table.
                self._broker.notify_all()
                while not closed.is_set():
                    try:
                        await asyncio.wait_for(closed.wait(), timeout=self._ping_interval)
                    except TimeoutError:
                        await connection.execute("SELECT 1")
                logger.warning("run_events.connection_closed")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("run_events.listen_failed", error=str(exc), retry_in=delay)
            finally:
                if connection is not None and not connection.is_closed():
                    with contextlib.suppress(Exception):
                        await connection.close()
            await asyncio.sleep(delay)
            delay = min(self._max_retry_delay, delay * 2)


__all__ = [
    "CHANNEL",
    "TERMINAL_RUN_STATUSES",
    "PostgresRunEventListener",
    "RunEventBroker",
    "RunEventORM",
    "get_run_event_broker",
    "listen_dsn",
    "record_run_event",
]
