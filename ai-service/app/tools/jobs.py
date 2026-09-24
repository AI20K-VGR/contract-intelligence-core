"""Durable local job state for the Backend -> AI2 wire contract."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

# P3 keeps the legacy Backend job path intact while exposing the canonical
# durable run boundary from the existing tools entrypoint.
from app.tools.durable import (
    DurableRunStore,
    EventDigestConflict,
    EventGapError,
    LeaseFencedError,
    SnapshotCorruptError,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "ai2" / "jobs.sqlite"


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
                    worker_token=?, lease_until_ms=?, updated_ms=?
                WHERE job_id=? AND tenant_id=? AND dossier_id=? AND worker_token=?
                """,
                (
                    status,
                    json.dumps(wire, ensure_ascii=False),
                    json.dumps(result, ensure_ascii=False) if result is not None else None,
                    None if terminal else worker_token,
                    None if terminal else now + 60_000,
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

    def clear(self) -> None:
        """Clear jobs for isolated tests and local development resets."""

        cx = self._connect()
        try:
            cx.execute("DELETE FROM jobs")
            cx.commit()
        finally:
            cx.close()
