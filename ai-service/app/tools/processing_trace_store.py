"""Append-only, best-effort trace for the signed AI2 HTTP worker lane."""

from __future__ import annotations

import logging
import re
import sqlite3
import time
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

_STATUSES = {"STARTED", "COMPLETED", "FAILED", "SKIPPED", "INTERRUPTED_UNKNOWN"}
_TERMINAL = _STATUSES - {"STARTED"}
_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


class LeaseFencedTraceWrite(RuntimeError):
    """The worker no longer owns the job lease and cannot append trace events."""


@dataclass(frozen=True, slots=True)
class ProcessingTraceEvent:
    tenant_id: str
    dossier_id: str
    job_id: str
    snapshot_digest: str
    execution_id: str
    sequence: int
    stage_id: str
    status: str
    created_ms: int
    started_ms: int | None = None
    duration_ms: int | None = None
    item_count: int | None = None
    reason_code: str | None = None


class ProcessingTraceStore:
    """Stateless adapter that uses the selected job database for durability."""

    def __init__(self, job_store: Any) -> None:
        self.job_store = job_store

    def _is_postgres(self) -> bool:
        return hasattr(self.job_store, "engine")

    @staticmethod
    def _validate(event: dict[str, Any]) -> None:
        for key in ("tenant_id", "dossier_id", "job_id", "snapshot_digest", "execution_id", "stage_id"):
            value = event.get(key)
            if not isinstance(value, str) or not value.strip() or len(value) > 512:
                raise ValueError(f"invalid trace field: {key}")
        if event["status"] not in _STATUSES:
            raise ValueError("invalid trace status")
        if event.get("reason_code") is not None and not _CODE.fullmatch(event["reason_code"]):
            raise ValueError("invalid trace reason code")
        for key in ("duration_ms", "item_count"):
            value = event.get(key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ValueError(f"invalid trace field: {key}")

    @staticmethod
    def _event(row: Any) -> ProcessingTraceEvent:
        if hasattr(row, "_mapping"):
            row = row._mapping
        return ProcessingTraceEvent(**{field: row[field] for field in ProcessingTraceEvent.__dataclass_fields__})

    def append(
        self, *, tenant_id: str, dossier_id: str, job_id: str, snapshot_digest: str,
        execution_id: str, stage_id: str, status: str, worker_token: str | None,
        started_ms: int | None = None, duration_ms: int | None = None,
        item_count: int | None = None, reason_code: str | None = None,
    ) -> ProcessingTraceEvent:
        event = {
            "tenant_id": tenant_id, "dossier_id": dossier_id, "job_id": job_id,
            "snapshot_digest": snapshot_digest, "execution_id": execution_id,
            "stage_id": stage_id, "status": status, "started_ms": started_ms,
            "duration_ms": duration_ms, "item_count": item_count,
            "reason_code": reason_code,
        }
        self._validate(event)
        if self._is_postgres():
            return self._append_postgres(event, worker_token)
        return self._append_sqlite(event, worker_token)

    def _append_sqlite(self, event: dict[str, Any], worker_token: str | None) -> ProcessingTraceEvent:
        cx = self.job_store._connect()
        try:
            cx.execute("BEGIN IMMEDIATE")
            self._ensure_sqlite_table(cx)
            job = cx.execute("SELECT status, worker_token, current_execution_id FROM jobs WHERE job_id=? AND tenant_id=? AND dossier_id=?",
                             (event["job_id"], event["tenant_id"], event["dossier_id"])).fetchone()
            if (job is None or job["status"] != "RUNNING" or not worker_token
                    or job["worker_token"] != worker_token
                    or job["current_execution_id"] != event["execution_id"]):
                raise LeaseFencedTraceWrite("worker lease is no longer current")
            sequence = cx.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM ai2_processing_trace_events WHERE tenant_id=? AND dossier_id=? AND job_id=? AND snapshot_digest=?",
                (event["tenant_id"], event["dossier_id"], event["job_id"], event["snapshot_digest"]),
            ).fetchone()[0]
            saved = self._insert_sqlite(cx, event, sequence)
            cx.commit()
            return saved
        except Exception:
            cx.rollback()
            raise
        finally:
            cx.close()

    @staticmethod
    def _ensure_sqlite_table(cx: sqlite3.Connection) -> None:
        cx.execute("""CREATE TABLE IF NOT EXISTS ai2_processing_trace_events (
            tenant_id TEXT NOT NULL, dossier_id TEXT NOT NULL, job_id TEXT NOT NULL,
            snapshot_digest TEXT NOT NULL, execution_id TEXT NOT NULL, sequence INTEGER NOT NULL,
            stage_id TEXT NOT NULL, status TEXT NOT NULL, created_ms INTEGER NOT NULL,
            started_ms INTEGER, duration_ms INTEGER, item_count INTEGER, reason_code TEXT,
            PRIMARY KEY (tenant_id, dossier_id, job_id, snapshot_digest, execution_id, sequence),
            CHECK(status IN ('STARTED','COMPLETED','FAILED','SKIPPED','INTERRUPTED_UNKNOWN')),
            CHECK(duration_ms IS NULL OR duration_ms >= 0), CHECK(item_count IS NULL OR item_count >= 0)
        )""")
        cx.execute("CREATE INDEX IF NOT EXISTS idx_ai2_trace_scope ON ai2_processing_trace_events(tenant_id,dossier_id,job_id,snapshot_digest,sequence)")

    def _insert_sqlite(self, cx: sqlite3.Connection, event: dict[str, Any], sequence: int) -> ProcessingTraceEvent:
        row = {**event, "sequence": sequence, "created_ms": self._now_ms()}
        cx.execute("""INSERT INTO ai2_processing_trace_events(
            tenant_id,dossier_id,job_id,snapshot_digest,execution_id,sequence,stage_id,status,
            created_ms,started_ms,duration_ms,item_count,reason_code
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", tuple(row[k] for k in (
            "tenant_id", "dossier_id", "job_id", "snapshot_digest", "execution_id", "sequence",
            "stage_id", "status", "created_ms", "started_ms", "duration_ms", "item_count", "reason_code")))
        return ProcessingTraceEvent(**row)

    def _append_postgres(self, event: dict[str, Any], worker_token: str | None) -> ProcessingTraceEvent:
        from sqlalchemy import func, select

        from app.db.tables import jobs, processing_trace_events

        with self.job_store.engine.begin() as cx:
            job = cx.execute(select(jobs.c.status, jobs.c.worker_token, jobs.c.current_execution_id).where(
                jobs.c.job_id == event["job_id"], jobs.c.tenant_id == event["tenant_id"],
                jobs.c.dossier_id == event["dossier_id"],
            ).with_for_update()).first()
            if (job is None or job.status != "RUNNING" or not worker_token
                    or job.worker_token != worker_token
                    or job.current_execution_id != event["execution_id"]):
                raise LeaseFencedTraceWrite("worker lease is no longer current")
            sequence = cx.execute(select(func.coalesce(func.max(processing_trace_events.c.sequence), 0) + 1).where(
                processing_trace_events.c.tenant_id == event["tenant_id"],
                processing_trace_events.c.dossier_id == event["dossier_id"],
                processing_trace_events.c.job_id == event["job_id"],
                processing_trace_events.c.snapshot_digest == event["snapshot_digest"],
            )).scalar_one()
            row = {**event, "sequence": sequence, "created_ms": self._now_ms()}
            cx.execute(processing_trace_events.insert().values(**row))
            return ProcessingTraceEvent(**row)

    def read_events(self, *, tenant_id: str, dossier_id: str, job_id: str,
                    snapshot_digest: str, execution_id: str | None = None) -> list[ProcessingTraceEvent]:
        if self._is_postgres():
            from sqlalchemy import select

            from app.db.tables import processing_trace_events
            stmt = select(processing_trace_events).where(
                processing_trace_events.c.tenant_id == tenant_id,
                processing_trace_events.c.dossier_id == dossier_id,
                processing_trace_events.c.job_id == job_id,
                processing_trace_events.c.snapshot_digest == snapshot_digest,
            )
            if execution_id is not None:
                stmt = stmt.where(processing_trace_events.c.execution_id == execution_id)
            stmt = stmt.order_by(processing_trace_events.c.sequence)
            with self.job_store.engine.connect() as cx:
                return [self._event(row) for row in cx.execute(stmt).mappings().all()]
        cx = self.job_store._connect()
        try:
            self._ensure_sqlite_table(cx)
            sql = "SELECT * FROM ai2_processing_trace_events WHERE tenant_id=? AND dossier_id=? AND job_id=? AND snapshot_digest=?"
            params: list[Any] = [tenant_id, dossier_id, job_id, snapshot_digest]
            if execution_id is not None:
                sql += " AND execution_id=?"
                params.append(execution_id)
            rows = cx.execute(sql + " ORDER BY sequence", params).fetchall()
            return [self._event(row) for row in rows]
        finally:
            cx.close()

    def read_latest_execution(self, *, tenant_id: str, dossier_id: str, job_id: str,
                              snapshot_digest: str) -> list[ProcessingTraceEvent]:
        job = self.job_store.get(job_id, tenant_id=tenant_id, dossier_id=dossier_id)
        execution_id = job.get("current_execution_id") if job else None
        if not execution_id:
            return []
        return self.read_events(tenant_id=tenant_id, dossier_id=dossier_id, job_id=job_id,
                                snapshot_digest=snapshot_digest, execution_id=execution_id)

    def finalize_stale_job(self, job_id: str) -> int:
        """Mark any open stages interrupted after the job is terminal and unfenced."""
        if self._is_postgres():
            return self._finalize_postgres(job_id)
        cx = self.job_store._connect()
        try:
            cx.execute("BEGIN IMMEDIATE")
            self._ensure_sqlite_table(cx)
            job = cx.execute("SELECT status, worker_token FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if job is None or job["status"] not in {"FAILED", "SUCCEEDED", "CANCELLED"} or job["worker_token"]:
                cx.commit()
                return 0
            rows = cx.execute("SELECT * FROM ai2_processing_trace_events WHERE job_id=? ORDER BY sequence",
                              (job_id,)).fetchall()
            events = [self._event(row) for row in rows]
            open_starts = _open_stages(events)
            inserted = 0
            for start in open_starts:
                seq = max((event.sequence for event in events if event.snapshot_digest == start.snapshot_digest), default=0) + 1
                marker = ProcessingTraceEvent(
                    tenant_id=start.tenant_id, dossier_id=start.dossier_id, job_id=start.job_id,
                    snapshot_digest=start.snapshot_digest, execution_id=start.execution_id, sequence=seq,
                    stage_id=start.stage_id, status="INTERRUPTED_UNKNOWN", created_ms=self._now_ms(),
                    started_ms=start.started_ms or start.created_ms, reason_code="WORKER_INTERRUPTED",
                )
                cx.execute("""INSERT INTO ai2_processing_trace_events(
                    tenant_id,dossier_id,job_id,snapshot_digest,execution_id,sequence,stage_id,status,
                    created_ms,started_ms,duration_ms,item_count,reason_code
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", tuple(getattr(marker, k) for k in ProcessingTraceEvent.__dataclass_fields__))
                events.append(marker)
                inserted += 1
            cx.commit()
            return inserted
        except Exception:
            cx.rollback()
            raise
        finally:
            cx.close()

    def _finalize_postgres(self, job_id: str) -> int:
        from sqlalchemy import select

        from app.db.tables import jobs, processing_trace_events
        with self.job_store.engine.begin() as cx:
            job = cx.execute(select(jobs.c.status, jobs.c.worker_token).where(
                jobs.c.job_id == job_id).with_for_update()).first()
            if job is None or job.status not in {"FAILED", "SUCCEEDED", "CANCELLED"} or job.worker_token:
                return 0
            rows = cx.execute(select(processing_trace_events).where(
                processing_trace_events.c.job_id == job_id
            ).order_by(processing_trace_events.c.sequence)).mappings().all()
            events = [self._event(row) for row in rows]
            opens = _open_stages(events)
            for start in opens:
                seq = max((event.sequence for event in events if event.snapshot_digest == start.snapshot_digest), default=0) + 1
                marker = ProcessingTraceEvent(
                    tenant_id=start.tenant_id, dossier_id=start.dossier_id, job_id=start.job_id,
                    snapshot_digest=start.snapshot_digest, execution_id=start.execution_id, sequence=seq,
                    stage_id=start.stage_id, status="INTERRUPTED_UNKNOWN", created_ms=self._now_ms(),
                    started_ms=start.started_ms or start.created_ms, reason_code="WORKER_INTERRUPTED",
                )
                cx.execute(processing_trace_events.insert().values(**{
                    field: getattr(marker, field) for field in ProcessingTraceEvent.__dataclass_fields__
                }))
                events.append(marker)
            return len(opens)

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)


def _open_stages(events: list[ProcessingTraceEvent]) -> list[ProcessingTraceEvent]:
    terminal = {(event.execution_id, event.stage_id) for event in events if event.status in _TERMINAL}
    return [event for event in events if event.status == "STARTED" and
            (event.execution_id, event.stage_id) not in terminal]


class ProcessingTraceWriter:
    """Small worker-scoped facade; telemetry errors never escape into pipeline work."""

    def __init__(self, store: ProcessingTraceStore, *, tenant_id: str, dossier_id: str,
                 job_id: str, snapshot_digest: str, execution_id: str, worker_token: str) -> None:
        self.store = store
        self.scope = dict(tenant_id=tenant_id, dossier_id=dossier_id, job_id=job_id,
                          snapshot_digest=snapshot_digest, execution_id=execution_id,
                          worker_token=worker_token)
        self.trace_status = "AVAILABLE"
        self._started: dict[str, tuple[int, int]] = {}

    def start(self, stage_id: str) -> None:
        now = self.store._now_ms()
        try:
            self.store.append(**self.scope, stage_id=stage_id, status="STARTED", started_ms=now)
            self._started[stage_id] = (now, time.monotonic_ns())
        except Exception as exc:
            self._unavailable(exc)

    def skip(self, stage_id: str, reason_code: str) -> None:
        """Persist an explicit non-run state without inventing a stage start."""
        if self.trace_status == "UNAVAILABLE":
            return
        try:
            self.store.append(**self.scope, stage_id=stage_id, status="SKIPPED",
                              reason_code=reason_code)
        except Exception as exc:
            self._unavailable(exc)

    def finish(self, stage_id: str, status: str, *, item_count: int | None = None,
               reason_code: str | None = None) -> None:
        started = self._started.pop(stage_id, None)
        if started is None or self.trace_status == "UNAVAILABLE":
            return
        started_ms, started_ns = started
        try:
            self.store.append(**self.scope, stage_id=stage_id, status=status,
                              started_ms=started_ms,
                              duration_ms=max(0, (time.monotonic_ns() - started_ns) // 1_000_000),
                              item_count=item_count, reason_code=reason_code)
        except Exception as exc:
            self._unavailable(exc)

    def _unavailable(self, exc: Exception) -> None:
        if isinstance(exc, LeaseFencedTraceWrite):
            self.trace_status = "FENCED"
            log.info("ai2.processing_trace_fenced")
            return
        self.trace_status = "UNAVAILABLE"
        log.warning("ai2.processing_trace_unavailable code=%s", type(exc).__name__)
        try:
            self.store.job_store.mark_trace_unavailable(
                self.scope["job_id"], tenant_id=self.scope["tenant_id"],
                dossier_id=self.scope["dossier_id"], worker_token=self.scope["worker_token"],
            )
        except Exception as marker_exc:
            log.warning("ai2.processing_trace_status_write_failed code=%s", type(marker_exc).__name__)


def project_processing_trace(events: list[ProcessingTraceEvent], *, terminal_job: bool = False) -> dict[str, Any]:
    if not events:
        return {"status": "TRACE_UNAVAILABLE", "execution_id": None, "stages": []}
    execution_id = events[0].execution_id
    stages: dict[str, dict[str, Any]] = {}
    starts: dict[str, ProcessingTraceEvent] = {}
    for event in events:
        if event.execution_id != execution_id:
            continue
        if event.status == "STARTED":
            starts[event.stage_id] = event
            stages[event.stage_id] = {"stage_id": event.stage_id, "status": "RUNNING",
                                      "started_ms": event.started_ms or event.created_ms,
                                      "duration_ms": None, "item_count": None, "reason_code": None}
        else:
            stages[event.stage_id] = {"stage_id": event.stage_id, "status": event.status,
                                      "started_ms": event.started_ms, "duration_ms": event.duration_ms,
                                      "item_count": event.item_count, "reason_code": event.reason_code}
    for stage_id, start in starts.items():
        if stages.get(stage_id, {}).get("status") == "RUNNING" and terminal_job:
            stages[stage_id].update(status="INCOMPLETE_UNKNOWN", reason_code="TERMINAL_WITH_OPEN_STAGE")
    values = list(stages.values())
    if any(stage["status"] == "INCOMPLETE_UNKNOWN" for stage in values):
        status = "INCOMPLETE_UNKNOWN"
    elif any(stage["status"] == "INTERRUPTED_UNKNOWN" for stage in values):
        status = "INTERRUPTED_UNKNOWN"
    elif any(stage["status"] == "RUNNING" for stage in values):
        status = "IN_PROGRESS"
    else:
        status = "COMPLETE"
    return {"status": status, "execution_id": execution_id, "stages": values}
