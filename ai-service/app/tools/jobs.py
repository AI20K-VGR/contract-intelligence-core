"""Durable local job state for the Backend -> AI2 wire contract."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

# P3 keeps the legacy Backend job path intact while exposing the canonical
# durable run boundary from the existing tools entrypoint.
from app.tools.durable import (
    DurableRunStore as DurableRunStore,
)
from app.tools.durable import (
    EventDigestConflict as EventDigestConflict,
)
from app.tools.durable import (
    EventGapError as EventGapError,
)
from app.tools.durable import (
    LeaseFencedError as LeaseFencedError,
)
from app.tools.durable import (
    SnapshotCorruptError as SnapshotCorruptError,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "ai2" / "jobs.sqlite"
log = logging.getLogger(__name__)


class JobOwnershipConflict(ValueError):
    """An idempotency key was reused for a different dossier owner."""


class JobNonceReplayConflict(ValueError):
    """A signed nonce was reused with a different request payload."""


class JobPayloadConflict(ValueError):
    """An idempotency key was reused with a different signed payload."""


class SQLiteJobStore:
    """Small transactional job store with tenant-scoped idempotency.

    The store deliberately persists the public wire envelope rather than
    coupling the durable layer to internal ``JobResult`` models. This keeps
    polling stable if the extraction implementation evolves.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        configured = path or os.getenv("AI2_JOB_DB") or DEFAULT_DB
        self.path = str(configured)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        cx = sqlite3.connect(self.path, timeout=10.0)
        cx.row_factory = sqlite3.Row
        cx.execute("PRAGMA busy_timeout=10000")
        if self.path != ":memory:":
            cx.execute("PRAGMA journal_mode=WAL")
        return cx

    def _initialize(self) -> None:
        cx = self._connect()
        try:
            cx.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    dossier_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    wire_json TEXT NOT NULL,
                    result_json TEXT,
                    request_fingerprint TEXT,
                    worker_token TEXT,
                    lease_until_ms INTEGER,
                    created_ms INTEGER NOT NULL,
                    updated_ms INTEGER NOT NULL,
                    UNIQUE (tenant_id, idempotency_key, attempt)
                )
                """
            )
            cx.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_owner ON jobs(tenant_id, dossier_id, updated_ms)"
            )
            columns = {row[1] for row in cx.execute("PRAGMA table_info(jobs)").fetchall()}
            if "request_fingerprint" not in columns:
                cx.execute("ALTER TABLE jobs ADD COLUMN request_fingerprint TEXT")
            cx.execute(
                """
                CREATE TABLE IF NOT EXISTS service_nonces (
                    tenant_id TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    payload_fingerprint TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    created_ms INTEGER NOT NULL,
                    PRIMARY KEY (tenant_id, nonce)
                )
                """
            )
            cx.commit()
        finally:
            cx.close()

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)

    @staticmethod
    def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "job_id": row["job_id"],
            "tenant_id": row["tenant_id"],
            "dossier_id": row["dossier_id"],
            "request_id": row["request_id"],
            "idempotency_key": row["idempotency_key"],
            "attempt": row["attempt"],
            "status": row["status"],
            "request": json.loads(row["request_json"]),
            "wire": json.loads(row["wire_json"]),
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "request_fingerprint": row["request_fingerprint"],
            "worker_token": row["worker_token"],
            "lease_until_ms": row["lease_until_ms"],
            "created_ms": row["created_ms"],
            "updated_ms": row["updated_ms"],
        }

    def create_or_get(
        self,
        *,
        tenant_id: str,
        dossier_id: str,
        request_id: str,
        idempotency_key: str,
        attempt: int,
        request: dict[str, Any],
        wire: dict[str, Any],
        nonce: str | None = None,
        request_fingerprint: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Atomically create a queued job or return the existing job.

        The boolean is ``True`` only for a newly inserted job.
        """

        now = self._now_ms()
        cx = self._connect()
        try:
            cx.execute("BEGIN IMMEDIATE")
            nonce_row = None
            if nonce is not None:
                nonce_row = cx.execute(
                    "SELECT payload_fingerprint, job_id FROM service_nonces WHERE tenant_id=? AND nonce=?",
                    (tenant_id, nonce),
                ).fetchone()
                if nonce_row is not None:
                    if nonce_row["payload_fingerprint"] != (request_fingerprint or ""):
                        cx.rollback()
                        raise JobNonceReplayConflict("service nonce was reused with another payload")
                    existing_job = cx.execute(
                        "SELECT * FROM jobs WHERE job_id=?", (nonce_row["job_id"],)
                    ).fetchone()
                    if existing_job is not None:
                        cx.commit()
                        return self._decode(existing_job) or {}, False
            row = cx.execute(
                """
                SELECT * FROM jobs
                WHERE tenant_id=? AND idempotency_key=? AND attempt=?
                """,
                (tenant_id, idempotency_key, attempt),
            ).fetchone()
            if row is not None:
                if row["dossier_id"] != dossier_id:
                    cx.rollback()
                    raise JobOwnershipConflict(
                        "idempotency key is already associated with another dossier"
                    )
                stored_fingerprint = row["request_fingerprint"] or ""
                if stored_fingerprint and request_fingerprint and stored_fingerprint != request_fingerprint:
                    cx.rollback()
                    raise JobPayloadConflict("idempotency key was reused with another payload")
                cx.commit()
                if nonce is not None:
                    cx.execute(
                        """
                        INSERT INTO service_nonces(tenant_id, nonce, payload_fingerprint, job_id, created_ms)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (tenant_id, nonce, request_fingerprint or "", row["job_id"], now),
                    )
                    cx.commit()
                return self._decode(row) or {}, False
            job_id = f"job_{uuid4().hex[:10]}"
            stored_wire = dict(wire)
            stored_wire["job_id"] = job_id
            cx.execute(
                """
                INSERT INTO jobs(
                    job_id, tenant_id, dossier_id, request_id, idempotency_key,
                    attempt, status, request_json, wire_json, request_fingerprint, created_ms, updated_ms
                ) VALUES (?, ?, ?, ?, ?, ?, 'QUEUED', ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    tenant_id,
                    dossier_id,
                    request_id,
                    idempotency_key,
                    attempt,
                    json.dumps(request, ensure_ascii=False, sort_keys=True),
                    json.dumps(stored_wire, ensure_ascii=False),
                    request_fingerprint,
                    now,
                    now,
                ),
            )
            row = cx.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if nonce is not None:
                cx.execute(
                    """
                    INSERT INTO service_nonces(tenant_id, nonce, payload_fingerprint, job_id, created_ms)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (tenant_id, nonce, request_fingerprint or "", job_id, now),
                )
            cx.commit()
            return self._decode(row) or {}, True
        finally:
            cx.close()

    def claim(
        self,
        job_id: str,
        *,
        tenant_id: str,
        dossier_id: str,
        lease_ms: int = 60_000,
    ) -> str | None:
        """Claim a queued job, or reclaim an expired running job."""

        now = self._now_ms()
        token = uuid4().hex
        cx = self._connect()
        try:
            cx.execute("BEGIN IMMEDIATE")
            row = cx.execute(
                "SELECT status, lease_until_ms FROM jobs WHERE job_id=? AND tenant_id=? AND dossier_id=?",
                (job_id, tenant_id, dossier_id),
            ).fetchone()
            if row is None or row["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                cx.rollback()
                return None
            if row["status"] == "RUNNING" and (row["lease_until_ms"] or 0) > now:
                cx.rollback()
                return None
            cx.execute(
                """
                UPDATE jobs SET status='RUNNING', worker_token=?, lease_until_ms=?, updated_ms=?
                WHERE job_id=? AND tenant_id=? AND dossier_id=?
                """,
                (token, now + lease_ms, now, job_id, tenant_id, dossier_id),
            )
            cx.commit()
            return token
        finally:
            cx.close()

    def set_wire(
        self,
        job_id: str,
        *,
        tenant_id: str,
        dossier_id: str,
        worker_token: str,
        status: str,
        wire: dict[str, Any],
        result: dict[str, Any] | None = None,
    ) -> bool:
        now = self._now_ms()
        cx = self._connect()
        try:
            cx.execute("BEGIN IMMEDIATE")
            terminal = status in {"SUCCEEDED", "FAILED", "CANCELLED"}
            cur = cx.execute(
                """
                UPDATE jobs SET status=?, wire_json=?, result_json=?,
                    worker_token=?, lease_until_ms=CASE WHEN ? THEN NULL ELSE lease_until_ms END, updated_ms=?
                WHERE job_id=? AND tenant_id=? AND dossier_id=? AND worker_token=?
                """,
                (
                    status,
                    json.dumps(wire, ensure_ascii=False),
                    json.dumps(result, ensure_ascii=False) if result is not None else None,
                    None if terminal else worker_token,
                    int(terminal),
                    now,
                    job_id,
                    tenant_id,
                    dossier_id,
                    worker_token,
                ),
            )
            cx.commit()
            return cur.rowcount == 1
        finally:
            cx.close()

    def _fail_rows(self, cx: sqlite3.Connection, rows: list[sqlite3.Row], update: dict[str, Any], now: int) -> None:
        for row in rows:
            wire = {**json.loads(row["wire_json"]), **update, "status": "FAILED"}
            cx.execute(
                """
                UPDATE jobs SET status='FAILED', wire_json=?, worker_token=NULL,
                    lease_until_ms=NULL, updated_ms=?
                WHERE job_id=?
                """,
                (json.dumps(wire, ensure_ascii=False), now, row["job_id"]),
            )

    def fail_unclaimed(self, job_id: str, update: dict[str, Any]) -> bool:
        """Fail a job the worker gave up on before claiming it (still QUEUED)."""

        now = self._now_ms()
        cx = self._connect()
        try:
            cx.execute("BEGIN IMMEDIATE")
            rows = cx.execute(
                "SELECT job_id, wire_json FROM jobs WHERE job_id=? AND status='QUEUED'", (job_id,)
            ).fetchall()
            self._fail_rows(cx, rows, update, now)
            cx.commit()
            return bool(rows)
        finally:
            cx.close()

    def hold_queued(self, job_ids: list[str], *, lease_ms: int) -> None:
        """Renew the lease a live process holds on QUEUED jobs it will still run.

        A held QUEUED job is not an orphan, however long it waits for a worker
        thread; once the holder stops renewing, the lease lapses and any
        replica's sweep fails it.
        """

        if not job_ids:
            return
        cx = self._connect()
        try:
            cx.execute("BEGIN IMMEDIATE")
            cx.execute(
                f"UPDATE jobs SET lease_until_ms=? WHERE status='QUEUED' AND job_id IN ({','.join('?' * len(job_ids))})",
                (self._now_ms() + lease_ms, *job_ids),
            )
            cx.commit()
        finally:
            cx.close()

    def sweep_stale(self, update: dict[str, Any], *, queued_grace_ms: int = 60_000) -> list[str]:
        """Fail jobs no live worker owns: RUNNING past the lease, or QUEUED past
        its hold lease (or, never held, older than ``queued_grace_ms``)."""

        now = self._now_ms()
        cx = self._connect()
        try:
            cx.execute("BEGIN IMMEDIATE")
            rows = cx.execute(
                """
                SELECT job_id, wire_json FROM jobs
                WHERE (status='RUNNING' AND COALESCE(lease_until_ms, 0) <= ?)
                   OR (status='QUEUED' AND COALESCE(lease_until_ms, updated_ms + ?) <= ?)
                """,
                (now, queued_grace_ms, now),
            ).fetchall()
            self._fail_rows(cx, rows, update, now)
            cx.commit()
            return [row["job_id"] for row in rows]
        finally:
            cx.close()

    def complete_with_snapshot(self, job_id, *, tenant_id, dossier_id, worker_token,
                               status, wire, record, envelope, result=None):
        from app.tools.query_store import save_query_snapshot

        accepted = self.set_wire(job_id, tenant_id=tenant_id, dossier_id=dossier_id,
                                 worker_token=worker_token, status=status, wire=wire, result=result)
        if accepted and status == "SUCCEEDED":
            save_query_snapshot(record, envelope)
        return accepted

    def get(
        self,
        job_id: str,
        *,
        tenant_id: str | None = None,
        dossier_id: str | None = None,
    ) -> dict[str, Any] | None:
        cx = self._connect()
        try:
            query = "SELECT * FROM jobs WHERE job_id=?"
            args: list[Any] = [job_id]
            if tenant_id is not None:
                query += " AND tenant_id=?"
                args.append(tenant_id)
            if dossier_id is not None:
                query += " AND dossier_id=?"
                args.append(dossier_id)
            return self._decode(cx.execute(query, args).fetchone())
        finally:
            cx.close()

    def list_succeeded(self) -> list[dict[str, Any]]:
        """Return successful jobs in creation order for snapshot rehydration."""

        cx = self._connect()
        try:
            rows = cx.execute(
                "SELECT * FROM jobs WHERE status='SUCCEEDED' ORDER BY updated_ms ASC"
            ).fetchall()
            return [decoded for row in rows if (decoded := self._decode(row)) is not None]
        finally:
            cx.close()

    def clear(self) -> None:
        """Clear jobs for isolated tests and local development resets."""

        cx = self._connect()
        try:
            cx.execute("DELETE FROM jobs")
            cx.commit()
        finally:
            cx.close()


class PostgresJobStore(SQLiteJobStore):
    """Atomic job/nonce writes and row-fenced claims in AI2's own schema."""

    def __init__(self, url: str | None = None):
        from app.db.engine import ensure_database, get_engine
        self.engine = get_engine(url)
        ensure_database(self.engine)

    def _connect(self):
        from app.db.engine import DurableConnection
        return DurableConnection(self.engine)

    def create_or_get(self, *, tenant_id, dossier_id, request_id, idempotency_key, attempt,
                      request, wire, nonce=None, request_fingerprint=None):
        from sqlalchemy import select
        from sqlalchemy.dialects.postgresql import insert

        from app.db.tables import jobs, service_nonces
        now = self._now_ms()
        job_id = f"job_{uuid4().hex}"
        with self.engine.begin() as cx:
            if nonce is not None:
                prior = cx.execute(select(service_nonces).where(
                    service_nonces.c.tenant_id == tenant_id, service_nonces.c.nonce == nonce,
                ).with_for_update()).mappings().first()
                if prior:
                    if prior["payload_fingerprint"] != (request_fingerprint or ""):
                        raise JobNonceReplayConflict("service nonce was reused with another payload")
                    row = cx.execute(select(jobs).where(jobs.c.job_id == prior["job_id"])).mappings().first()
                    if row:
                        return self._decode(row), False
            inserted = cx.execute(insert(jobs).values(
                job_id=job_id, tenant_id=tenant_id, dossier_id=dossier_id, request_id=request_id,
                idempotency_key=idempotency_key, attempt=attempt, status="QUEUED",
                request_json=json.dumps(request, ensure_ascii=False, sort_keys=True),
                wire_json=json.dumps({**wire, "job_id": job_id}, ensure_ascii=False),
                request_fingerprint=request_fingerprint, created_ms=now, updated_ms=now,
            ).on_conflict_do_nothing(index_elements=[jobs.c.tenant_id, jobs.c.idempotency_key, jobs.c.attempt])
                .returning(jobs.c.job_id)).scalar()
            row = cx.execute(select(jobs).where(
                jobs.c.tenant_id == tenant_id, jobs.c.idempotency_key == idempotency_key, jobs.c.attempt == attempt,
            ).with_for_update()).mappings().one()
            if row["dossier_id"] != dossier_id:
                raise JobOwnershipConflict("idempotency key is already associated with another dossier")
            if row["request_fingerprint"] and request_fingerprint and row["request_fingerprint"] != request_fingerprint:
                raise JobPayloadConflict("idempotency key was reused with another payload")
            if nonce is not None:
                cx.execute(insert(service_nonces).values(
                    tenant_id=tenant_id, nonce=nonce, payload_fingerprint=request_fingerprint or "",
                    job_id=row["job_id"], created_ms=now,
                ).on_conflict_do_nothing(index_elements=[service_nonces.c.tenant_id, service_nonces.c.nonce]))
                saved = cx.execute(select(service_nonces).where(
                    service_nonces.c.tenant_id == tenant_id, service_nonces.c.nonce == nonce,
                ).with_for_update()).mappings().one()
                if saved["payload_fingerprint"] != (request_fingerprint or "") or saved["job_id"] != row["job_id"]:
                    raise JobNonceReplayConflict("service nonce was reused with another payload")
            return self._decode(row), bool(inserted)

    def claim(self, job_id, *, tenant_id, dossier_id, lease_ms=60_000):
        from sqlalchemy import and_, func, or_, update

        from app.db.tables import jobs
        now, token = self._now_ms(), uuid4().hex
        with self.engine.begin() as cx:
            return cx.execute(update(jobs).where(
                jobs.c.job_id == job_id, jobs.c.tenant_id == tenant_id, jobs.c.dossier_id == dossier_id,
                or_(jobs.c.status == "QUEUED", and_(jobs.c.status == "RUNNING", func.coalesce(jobs.c.lease_until_ms, 0) <= now)),
            ).values(status="RUNNING", worker_token=token, lease_until_ms=now + lease_ms,
                     updated_ms=now).returning(jobs.c.worker_token)).scalar()

    def set_wire(self, job_id, *, tenant_id, dossier_id, worker_token, status, wire, result=None):
        from sqlalchemy import update

        from app.db.tables import jobs
        terminal = status in {"SUCCEEDED", "FAILED", "CANCELLED"}
        values = dict(status=status, wire_json=json.dumps(wire, ensure_ascii=False),
                      result_json=json.dumps(result, ensure_ascii=False) if result is not None else None,
                      updated_ms=self._now_ms())
        if terminal:
            values.update(worker_token=None, lease_until_ms=None)
        with self.engine.begin() as cx:
            return cx.execute(update(jobs).where(
                jobs.c.job_id == job_id, jobs.c.tenant_id == tenant_id, jobs.c.dossier_id == dossier_id,
                jobs.c.worker_token == worker_token,
            ).values(**values)).rowcount == 1

    def complete_with_snapshot(self, job_id, *, tenant_id, dossier_id, worker_token,
                               status, wire, record, envelope, result=None):
        """Commit the fenced result and its query read model in one transaction."""
        from sqlalchemy import select, text, update
        from sqlalchemy.dialects.postgresql import insert

        from app.db.tables import jobs, query_snapshots
        from app.tools.persist import record_to_dict

        if (record.tenant_id != tenant_id or record.dossier_id != dossier_id
                or envelope.auth.tenant_id != tenant_id or envelope.auth.dossier_id != dossier_id
                or record.pins.source_snapshot_digest != envelope.pins.source_snapshot_digest
                or wire.get("query_snapshot_digest", record.pins.source_snapshot_digest)
                   != record.pins.source_snapshot_digest):
            raise ValueError("job query snapshot ownership or digest mismatch")
        payload = json.dumps({"record": record_to_dict(record), "envelope": envelope.model_dump()}, ensure_ascii=False)
        with self.engine.begin() as cx:
            # All completion writers for a dossier use the same transaction lock.
            cx.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
                       {"scope": json.dumps([tenant_id, dossier_id])})
            accepted = cx.execute(update(jobs).where(
                jobs.c.job_id == job_id, jobs.c.tenant_id == tenant_id, jobs.c.dossier_id == dossier_id,
                jobs.c.worker_token == worker_token, jobs.c.status == "RUNNING",
            ).values(status=status, wire_json=json.dumps(wire, ensure_ascii=False),
                     result_json=json.dumps(result, ensure_ascii=False) if result is not None else None,
                     worker_token=None, lease_until_ms=None, updated_ms=self._now_ms())
                .returning(jobs.c.job_id)).scalar()
            if not accepted:
                return False
            latest = cx.execute(select(jobs.c.job_id).where(
                jobs.c.tenant_id == tenant_id, jobs.c.dossier_id == dossier_id, jobs.c.status == "SUCCEEDED",
            ).order_by(jobs.c.created_ms.desc(), jobs.c.job_id.desc()).limit(1)).scalar()
            if status == "SUCCEEDED" and latest == job_id:
                stmt = insert(query_snapshots).values(tenant_id=tenant_id, dossier_id=dossier_id,
                    snapshot_digest=record.pins.source_snapshot_digest, payload=payload, updated_ms=self._now_ms())
                cx.execute(stmt.on_conflict_do_update(index_elements=[query_snapshots.c.tenant_id, query_snapshots.c.dossier_id],
                    set_={"snapshot_digest": stmt.excluded.snapshot_digest, "payload": stmt.excluded.payload,
                          "updated_ms": stmt.excluded.updated_ms}))
                if getattr(record, "contract_graph_ran", False):
                    self._replace_contract_edges(cx, record, job_id)
            return True

    def _replace_contract_edges(self, cx, record, job_id) -> None:
        """D7/RT-04: edges are enrichment; a failed write rolls back its savepoint only.

        The job stays SUCCEEDED with its new snapshot and the previous edge rows stay as they were.
        """
        from app.tools import contract_edge_store

        try:
            with cx.begin_nested():
                contract_edge_store.replace_contract_edges(
                    cx, tenant_id=record.tenant_id, dossier_id=record.dossier_id, job_id=job_id,
                    edges=record.contract_edges, now_ms=self._now_ms())
        except Exception as exc:  # enrichment only: never fail the completion
            log.warning("ai2.contract_edges_write_failed job_id=%s tenant_id=%s dossier_id=%s cause=%s",
                        job_id, record.tenant_id, record.dossier_id, type(exc).__name__)

    def _fail_matching(self, condition, update):
        from sqlalchemy import select
        from sqlalchemy import update as sql_update

        from app.db.tables import jobs
        with self.engine.begin() as cx:
            rows = cx.execute(select(jobs).where(condition).with_for_update()).mappings().all()
            for row in rows:
                wire = {**json.loads(row["wire_json"]), **update, "status": "FAILED"}
                cx.execute(sql_update(jobs).where(jobs.c.job_id == row["job_id"]).values(
                    status="FAILED", wire_json=json.dumps(wire, ensure_ascii=False),
                    worker_token=None, lease_until_ms=None, updated_ms=self._now_ms(),
                ))
            return [row["job_id"] for row in rows]

    def fail_unclaimed(self, job_id, update):
        from sqlalchemy import and_

        from app.db.tables import jobs
        return bool(self._fail_matching(and_(jobs.c.job_id == job_id, jobs.c.status == "QUEUED"), update))

    def hold_queued(self, job_ids, *, lease_ms):
        from sqlalchemy import update

        from app.db.tables import jobs
        if not job_ids:
            return
        with self.engine.begin() as cx:
            cx.execute(update(jobs).where(jobs.c.status == "QUEUED", jobs.c.job_id.in_(list(job_ids)))
                       .values(lease_until_ms=self._now_ms() + lease_ms))

    def sweep_stale(self, update, *, queued_grace_ms=60_000):
        from sqlalchemy import and_, func, or_

        from app.db.tables import jobs
        now = self._now_ms()
        return self._fail_matching(or_(
            and_(jobs.c.status == "RUNNING", func.coalesce(jobs.c.lease_until_ms, 0) <= now),
            and_(jobs.c.status == "QUEUED",
                 func.coalesce(jobs.c.lease_until_ms, jobs.c.updated_ms + queued_grace_ms) <= now),
        ), update)


def job_store_from_env():
    from app.db.engine import database_url, validate_database_config
    validate_database_config()
    return PostgresJobStore() if database_url() else SQLiteJobStore()
