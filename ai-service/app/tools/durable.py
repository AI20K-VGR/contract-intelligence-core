"""SQLite-backed run snapshots, event log, audit and outbox primitives.

The store is deliberately a local durable-friendly boundary.  SQLite
transactions prove the invariants exercised by this phase; they do not prove
production HA, queue delivery, or exactly-once external side effects.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4


class DurableStoreError(RuntimeError):
    """Base class for durable run-store invariant failures."""


class EventGapError(DurableStoreError):
    """An event sequence cannot be replayed contiguously."""


class EventDigestConflict(DurableStoreError):
    """A duplicate sequence or event id has a different digest."""


class SnapshotCorruptError(DurableStoreError):
    """The persisted snapshot no longer matches its digest."""


class SnapshotSequenceError(DurableStoreError):
    """A snapshot would move durable state backwards."""


class CheckpointConflict(DurableStoreError):
    """A checkpoint id was reused with different contents."""


class LeaseFencedError(DurableStoreError):
    """A worker attempted a write after its lease was reclaimed."""


class AuditAppendOnlyError(DurableStoreError):
    """Audit rows are append-only and cannot be mutated or deleted."""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


class DurableRunStore:
    """Transactional local store for one canonical run boundary.

    ``append_event`` commits the event and its outbox row in one SQLite
    transaction.  Consumers must use ``event_id`` as their idempotency key;
    a callback that succeeds and then loses its acknowledgement can still be
    invoked again after lease expiry.
    """

    def __init__(self, path: str | Path, *, now: Callable[[], Any] | None = None) -> None:
        self.path = str(path)
        self._clock = now or (lambda: time.time() * 1000)
        self._initialize()

    def _now_ms(self) -> int:
        value = self._clock()
        if hasattr(value, "timestamp"):
            return int(value.timestamp() * 1000)
        return int(value)

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
            cx.executescript(
                """
                CREATE TABLE IF NOT EXISTS durable_runs (
                    run_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    generation_id TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    snapshot_digest TEXT NOT NULL,
                    snapshot_sequence INTEGER NOT NULL,
                    event_sequence INTEGER NOT NULL DEFAULT 0,
                    state_version INTEGER NOT NULL,
                    created_ms INTEGER NOT NULL,
                    updated_ms INTEGER NOT NULL,
                    lease_owner TEXT,
                    lease_token TEXT,
                    lease_until_ms INTEGER
                );
                CREATE TABLE IF NOT EXISTS durable_checkpoints (
                    run_id TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    state_json TEXT NOT NULL,
                    state_digest TEXT NOT NULL,
                    created_ms INTEGER NOT NULL,
                    updated_ms INTEGER NOT NULL,
                    PRIMARY KEY (run_id, checkpoint_id)
                );
                CREATE TABLE IF NOT EXISTS durable_events (
                    event_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    state_version INTEGER NOT NULL,
                    generation_id TEXT NOT NULL,
                    created_ms INTEGER NOT NULL,
                    actor_id TEXT,
                    correlation_id TEXT NOT NULL,
                    causation_id TEXT,
                    payload_json TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    UNIQUE (run_id, sequence)
                );
                CREATE INDEX IF NOT EXISTS idx_durable_events_run
                    ON durable_events(run_id, sequence);
                CREATE TABLE IF NOT EXISTS durable_audit (
                    audit_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_ms INTEGER NOT NULL,
                    previous_digest TEXT,
                    digest TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS durable_outbox (
                    event_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    lease_token TEXT,
                    lease_until_ms INTEGER,
                    available_after_ms INTEGER NOT NULL,
                    published_ms INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_durable_outbox_pending
                    ON durable_outbox(status, available_after_ms);
                CREATE TRIGGER IF NOT EXISTS durable_audit_no_update
                    BEFORE UPDATE ON durable_audit
                    BEGIN SELECT RAISE(ABORT, 'durable audit is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS durable_audit_no_delete
                    BEFORE DELETE ON durable_audit
                    BEGIN SELECT RAISE(ABORT, 'durable audit is append-only'); END;
                """
            )
            columns = {row[1] for row in cx.execute("PRAGMA table_info(durable_runs)").fetchall()}
            if "event_sequence" not in columns:
                cx.execute("ALTER TABLE durable_runs ADD COLUMN event_sequence INTEGER NOT NULL DEFAULT 0")
            cx.commit()
        finally:
            cx.close()

    @staticmethod
    def _snapshot_digest(state: Mapping[str, Any]) -> str:
        return _digest(state)

    @staticmethod
    def _decode_snapshot(row: sqlite3.Row) -> dict[str, Any]:
        state = json.loads(row["snapshot_json"])
        if _digest(state) != row["snapshot_digest"]:
            raise SnapshotCorruptError(f"snapshot digest mismatch for run {row['run_id']}")
        return state

    @staticmethod
    def _decode_event(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "event_id": row["event_id"],
            "run_id": row["run_id"],
            "tenant_id": row["tenant_id"],
            "event_type": row["event_type"],
            "schema_version": row["schema_version"],
            "sequence": row["sequence"],
            "state_version": row["state_version"],
            "generation_id": row["generation_id"],
            "created_ms": row["created_ms"],
            "actor_id": row["actor_id"],
            "correlation_id": row["correlation_id"],
            "causation_id": row["causation_id"],
            "payload": json.loads(row["payload_json"]),
            "evidence_refs": json.loads(row["evidence_refs_json"]),
            "digest": row["digest"],
        }

    def create_run(
        self,
        *,
        run_id: str,
        tenant_id: str,
        generation_id: str,
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        now = self._now_ms()
        encoded = _json(state)
        digest = self._snapshot_digest(state)
        cx = self._connect()
        try:
            cx.execute(
                """
                INSERT INTO durable_runs(
                    run_id, tenant_id, generation_id, snapshot_json,
                    snapshot_digest, snapshot_sequence, event_sequence,
                    state_version, created_ms, updated_ms
                ) VALUES (?, ?, ?, ?, ?, 0, 0, 0, ?, ?)
                """,
                (run_id, tenant_id, generation_id, encoded, digest, now, now),
            )
            cx.commit()
        finally:
            cx.close()
        return self.get_run(run_id, tenant_id=tenant_id) or {}

    def get_run(self, run_id: str, *, tenant_id: str | None = None) -> dict[str, Any] | None:
        cx = self._connect()
        try:
            query = "SELECT * FROM durable_runs WHERE run_id=?"
            args: list[Any] = [run_id]
            if tenant_id is not None:
                query += " AND tenant_id=?"
                args.append(tenant_id)
            row = cx.execute(query, args).fetchone()
            if row is None:
                return None
            snapshot = self._decode_snapshot(row)
            checkpoint = cx.execute(
                """
                SELECT * FROM durable_checkpoints
                WHERE run_id=? ORDER BY sequence DESC, checkpoint_id DESC LIMIT 1
                """,
                (run_id,),
            ).fetchone()
            return {
                "run_id": row["run_id"],
                "tenant_id": row["tenant_id"],
                "generation_id": row["generation_id"],
                "snapshot": snapshot,
                "snapshot_digest": row["snapshot_digest"],
                "snapshot_sequence": row["snapshot_sequence"],
                "state_version": row["state_version"],
                "checkpoint": self._decode_checkpoint(checkpoint) if checkpoint else None,
                "lease_owner": row["lease_owner"],
                "lease_until_ms": row["lease_until_ms"],
            }
        finally:
            cx.close()

    @staticmethod
    def _decode_checkpoint(row: sqlite3.Row) -> dict[str, Any]:
        state = json.loads(row["state_json"])
        if _digest(state) != row["state_digest"]:
            raise SnapshotCorruptError(f"checkpoint digest mismatch for {row['checkpoint_id']}")
        return {
            "run_id": row["run_id"],
            "checkpoint_id": row["checkpoint_id"],
            "tenant_id": row["tenant_id"],
            "sequence": row["sequence"],
            "state": state,
            "state_digest": row["state_digest"],
            "created_ms": row["created_ms"],
            "updated_ms": row["updated_ms"],
        }

    def _assert_lease(self, cx: sqlite3.Connection, run_id: str, worker_token: str) -> sqlite3.Row:
        row = cx.execute(
            "SELECT * FROM durable_runs WHERE run_id=? AND lease_token=?",
            (run_id, worker_token),
        ).fetchone()
        if row is None or (row["lease_until_ms"] or 0) <= self._now_ms():
            raise LeaseFencedError(f"worker lease is not current for run {run_id}")
        return row

    def claim_lease(self, run_id: str, *, owner_id: str, lease_ms: int = 60_000) -> str | None:
        if lease_ms <= 0:
            raise ValueError("lease_ms must be positive")
        now = self._now_ms()
        token = uuid4().hex
        cx = self._connect()
        try:
            cx.execute("BEGIN IMMEDIATE")
            row = cx.execute("SELECT lease_until_ms FROM durable_runs WHERE run_id=?", (run_id,)).fetchone()
            if row is None or (row["lease_until_ms"] or 0) > now:
                cx.rollback()
                return None
            cx.execute(
                """
                UPDATE durable_runs SET lease_owner=?, lease_token=?, lease_until_ms=?, updated_ms=?
                WHERE run_id=?
                """,
                (owner_id, token, now + lease_ms, now, run_id),
            )
            cx.commit()
            return token
        finally:
            cx.close()

    def renew_lease(self, run_id: str, *, worker_token: str, lease_ms: int = 60_000) -> bool:
        now = self._now_ms()
        cx = self._connect()
        try:
            cur = cx.execute(
                """
                UPDATE durable_runs SET lease_until_ms=?, updated_ms=?
                WHERE run_id=? AND lease_token=? AND lease_until_ms>?
                """,
                (now + lease_ms, now, run_id, worker_token, now),
            )
            cx.commit()
            return cur.rowcount == 1
        finally:
            cx.close()

    def save_snapshot(
        self,
        run_id: str,
        *,
        state: Mapping[str, Any],
        sequence: int,
        worker_token: str | None = None,
    ) -> dict[str, Any]:
        now = self._now_ms()
        cx = self._connect()
        try:
            cx.execute("BEGIN IMMEDIATE")
            row = cx.execute("SELECT * FROM durable_runs WHERE run_id=?", (run_id,)).fetchone()
            if row is None:
                raise DurableStoreError(f"unknown run {run_id}")
            if worker_token is not None:
                row = self._assert_lease(cx, run_id, worker_token)
            if sequence < row["snapshot_sequence"]:
                raise SnapshotSequenceError("snapshot sequence cannot move backwards")
            cx.execute(
                """
                UPDATE durable_runs SET snapshot_json=?, snapshot_digest=?,
                    snapshot_sequence=?, state_version=?, updated_ms=?
                WHERE run_id=?
                """,
                (_json(state), self._snapshot_digest(state), sequence,
                 int(state.get("state_version", row["state_version"])), now, run_id),
            )
            cx.commit()
        finally:
            cx.close()
        return self.get_run(run_id) or {}

    def save_checkpoint(
        self,
        run_id: str,
        *,
        checkpoint_id: str,
        state: Mapping[str, Any],
        sequence: int,
        worker_token: str | None = None,
    ) -> dict[str, Any]:
        now = self._now_ms()
        state_json = _json(state)
        state_digest = _digest(state)
        cx = self._connect()
        try:
            cx.execute("BEGIN IMMEDIATE")
            run = cx.execute("SELECT tenant_id FROM durable_runs WHERE run_id=?", (run_id,)).fetchone()
            if run is None:
                raise DurableStoreError(f"unknown run {run_id}")
            if worker_token is not None:
                self._assert_lease(cx, run_id, worker_token)
            prior = cx.execute(
                "SELECT * FROM durable_checkpoints WHERE run_id=? AND checkpoint_id=?",
                (run_id, checkpoint_id),
            ).fetchone()
            if prior is not None:
                if prior["state_digest"] != state_digest or prior["sequence"] != sequence:
                    raise CheckpointConflict(f"checkpoint {checkpoint_id} was reused")
            else:
                cx.execute(
                    """
                    INSERT INTO durable_checkpoints(
                        run_id, checkpoint_id, tenant_id, sequence, state_json,
                        state_digest, created_ms, updated_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (run_id, checkpoint_id, run["tenant_id"], sequence, state_json,
                     state_digest, now, now),
                )
            cx.commit()
            row = cx.execute(
                "SELECT * FROM durable_checkpoints WHERE run_id=? AND checkpoint_id=?",
                (run_id, checkpoint_id),
            ).fetchone()
            return self._decode_checkpoint(row)
        finally:
            cx.close()

    def append_event(
        self,
        *,
        run_id: str,
        event_type: str,
        sequence: int,
        state_version: int,
        generation_id: str,
        correlation_id: str,
        payload: Mapping[str, Any],
        tenant_id: str | None = None,
        event_id: str | None = None,
        schema_version: str = "run.event.v1",
        actor_id: str | None = None,
        causation_id: str | None = None,
        evidence_refs: list[Mapping[str, Any]] | None = None,
        snapshot: Mapping[str, Any] | None = None,
        worker_token: str | None = None,
    ) -> dict[str, Any]:
        now = self._now_ms()
        event_id = event_id or f"evt_{uuid4().hex}"
        evidence_refs = evidence_refs or []
        cx = self._connect()
        try:
            run = cx.execute("SELECT tenant_id FROM durable_runs WHERE run_id=?", (run_id,)).fetchone()
        finally:
            cx.close()
        if run is None:
            raise DurableStoreError(f"unknown run {run_id}")
        resolved_tenant_id = run["tenant_id"]
        if tenant_id is not None and tenant_id != resolved_tenant_id:
            raise DurableStoreError("event tenant does not match run")
        unsigned = {
            "event_id": event_id,
            "run_id": run_id,
            "tenant_id": resolved_tenant_id,
            "event_type": event_type,
            "schema_version": schema_version,
            "sequence": sequence,
            "state_version": state_version,
            "generation_id": generation_id,
            "created_ms": now,
            "actor_id": actor_id,
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "payload": payload,
            "evidence_refs": evidence_refs,
        }
        digest = _digest(unsigned)
        cx = self._connect()
        try:
            cx.execute("BEGIN IMMEDIATE")
            run = cx.execute("SELECT * FROM durable_runs WHERE run_id=?", (run_id,)).fetchone()
            if run is None:
                raise DurableStoreError(f"unknown run {run_id}")
            if worker_token is not None:
                self._assert_lease(cx, run_id, worker_token)
            prior = cx.execute(
                "SELECT * FROM durable_events WHERE run_id=? AND sequence=?", (run_id, sequence)
            ).fetchone()
            if prior is not None:
                if prior["digest"] != digest:
                    raise EventDigestConflict(f"sequence {sequence} has a different digest")
                cx.commit()
                return self._decode_event(prior)
            prior_id = cx.execute(
                "SELECT * FROM durable_events WHERE event_id=?", (event_id,)
            ).fetchone()
            if prior_id is not None:
                if prior_id["digest"] != digest:
                    raise EventDigestConflict(f"event {event_id} has a different digest")
                cx.commit()
                return self._decode_event(prior_id)
            expected = cx.execute(
                "SELECT MAX(sequence) AS sequence FROM durable_events WHERE run_id=?", (run_id,)
            ).fetchone()["sequence"]
            if sequence != (expected or 0) + 1:
                raise EventGapError(f"expected sequence {(expected or 0) + 1}, got {sequence}")
            cx.execute(
                """
                INSERT INTO durable_events(
                    event_id, run_id, tenant_id, event_type, schema_version,
                    sequence, state_version, generation_id, created_ms,
                    actor_id, correlation_id, causation_id, payload_json,
                    evidence_refs_json, digest
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (event_id, run_id, run["tenant_id"], event_type, schema_version,
                 sequence, state_version, generation_id, now, actor_id,
                 correlation_id, causation_id, _json(payload), _json(evidence_refs), digest),
            )
            outbox_payload = dict(unsigned)
            outbox_payload["tenant_id"] = run["tenant_id"]
            outbox_payload["digest"] = digest
            cx.execute(
                """
                INSERT INTO durable_outbox(
                    event_id, run_id, payload_json, status, available_after_ms
                ) VALUES (?, ?, ?, 'PENDING', ?)
                """,
                (event_id, run_id, _json(outbox_payload), now),
            )
            cx.execute(
                "UPDATE durable_runs SET event_sequence=?, updated_ms=? WHERE run_id=?",
                (sequence, now, run_id),
            )
            if snapshot is not None:
                if worker_token is not None:
                    self._assert_lease(cx, run_id, worker_token)
                if sequence < run["snapshot_sequence"]:
                    raise SnapshotSequenceError("event snapshot sequence cannot move backwards")
                cx.execute(
                    """
                    UPDATE durable_runs SET snapshot_json=?, snapshot_digest=?,
                        snapshot_sequence=?, state_version=?, updated_ms=?
                    WHERE run_id=?
                    """,
                    (_json(snapshot), _digest(snapshot), sequence, state_version, now, run_id),
                )
            else:
                cx.execute(
                    "UPDATE durable_runs SET state_version=?, updated_ms=? WHERE run_id=?",
                    (state_version, now, run_id),
                )
            cx.commit()
            return self._decode_event(cx.execute("SELECT * FROM durable_events WHERE event_id=?", (event_id,)).fetchone())
        except Exception:
            cx.rollback()
            raise
        finally:
            cx.close()

    def list_events(self, run_id: str, *, after_sequence: int = 0) -> list[dict[str, Any]]:
        cx = self._connect()
        try:
            return [
                self._decode_event(row)
                for row in cx.execute(
                    "SELECT * FROM durable_events WHERE run_id=? AND sequence>? ORDER BY sequence",
                    (run_id, after_sequence),
                ).fetchall()
            ]
        finally:
            cx.close()

    def replay(self, run_id: str, *, after_sequence: int = 0) -> dict[str, Any]:
        cx = self._connect()
        try:
            run = cx.execute("SELECT * FROM durable_runs WHERE run_id=?", (run_id,)).fetchone()
            if run is None:
                raise DurableStoreError(f"unknown run {run_id}")
            snapshot = self._decode_snapshot(run)
            snapshot_sequence = run["snapshot_sequence"]
            base_sequence = snapshot_sequence if after_sequence < snapshot_sequence else after_sequence
            rows = cx.execute(
                "SELECT * FROM durable_events WHERE run_id=? AND sequence>? ORDER BY sequence",
                (run_id, base_sequence),
            ).fetchall()
            latest = run["event_sequence"] or 0
            if latest > base_sequence and (not rows or rows[0]["sequence"] != base_sequence + 1):
                raise EventGapError(f"event gap after sequence {base_sequence}")
            for previous, current in zip(rows, rows[1:]):
                if current["sequence"] != previous["sequence"] + 1:
                    raise EventGapError(f"event gap between {previous['sequence']} and {current['sequence']}")
            return {
                "run_id": run_id,
                "snapshot": snapshot,
                "snapshot_sequence": snapshot_sequence,
                "base_sequence": base_sequence,
                "used_snapshot_fallback": after_sequence < snapshot_sequence,
                "events": [self._decode_event(row) for row in rows],
            }
        finally:
            cx.close()

    def replay_state(
        self,
        run_id: str,
        *,
        after_sequence: int = 0,
        apply_event: Callable[[dict[str, Any], dict[str, Any]], Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        replay = self.replay(run_id, after_sequence=after_sequence)
        state = dict(replay["snapshot"])
        if apply_event is not None:
            for event in replay["events"]:
                state = dict(apply_event(state, event))
        return {**replay, "state": state}

    def append_audit(
        self,
        run_id: str,
        *,
        actor_id: str,
        action: str,
        details: Mapping[str, Any],
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        now = self._now_ms()
        cx = self._connect()
        try:
            cx.execute("BEGIN IMMEDIATE")
            run = cx.execute("SELECT tenant_id FROM durable_runs WHERE run_id=?", (run_id,)).fetchone()
            if run is None:
                raise DurableStoreError(f"unknown run {run_id}")
            if tenant_id is not None and tenant_id != run["tenant_id"]:
                raise DurableStoreError("audit tenant does not match run")
            previous = cx.execute(
                "SELECT digest FROM durable_audit WHERE run_id=? ORDER BY created_ms DESC, audit_id DESC LIMIT 1",
                (run_id,),
            ).fetchone()
            audit_id = f"audit_{uuid4().hex}"
            unsigned = {
                "audit_id": audit_id,
                "run_id": run_id,
                "tenant_id": run["tenant_id"],
                "actor_id": actor_id,
                "action": action,
                "details": details,
                "created_ms": now,
                "previous_digest": previous["digest"] if previous else None,
            }
            digest = _digest(unsigned)
            cx.execute(
                """
                INSERT INTO durable_audit(
                    audit_id, run_id, tenant_id, actor_id, action,
                    details_json, created_ms, previous_digest, digest
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (audit_id, run_id, run["tenant_id"], actor_id, action,
                 _json(details), now, unsigned["previous_digest"], digest),
            )
            cx.commit()
            return {**unsigned, "digest": digest}
        finally:
            cx.close()

    def list_audit(self, run_id: str) -> list[dict[str, Any]]:
        cx = self._connect()
        try:
            return [
                {
                    "audit_id": row["audit_id"],
                    "run_id": row["run_id"],
                    "tenant_id": row["tenant_id"],
                    "actor_id": row["actor_id"],
                    "action": row["action"],
                    "details": json.loads(row["details_json"]),
                    "created_ms": row["created_ms"],
                    "previous_digest": row["previous_digest"],
                    "digest": row["digest"],
                }
                for row in cx.execute(
                    "SELECT * FROM durable_audit WHERE run_id=? ORDER BY created_ms, audit_id", (run_id,)
                ).fetchall()
            ]
        finally:
            cx.close()

    def pending_outbox(self, run_id: str | None = None) -> list[dict[str, Any]]:
        now = self._now_ms()
        cx = self._connect()
        try:
            query = """
                SELECT * FROM durable_outbox
                WHERE status='PENDING' OR (status='CLAIMED' AND lease_until_ms<=?)
            """
            args: list[Any] = [now]
            if run_id is not None:
                query += " AND run_id=?"
                args.append(run_id)
            query += " ORDER BY available_after_ms, event_id"
            return [self._decode_outbox(row) for row in cx.execute(query, args).fetchall()]
        finally:
            cx.close()

    @staticmethod
    def _decode_outbox(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "event_id": row["event_id"],
            "run_id": row["run_id"],
            "payload": json.loads(row["payload_json"]),
            "status": row["status"],
            "attempts": row["attempts"],
            "lease_token": row["lease_token"],
            "lease_until_ms": row["lease_until_ms"],
            "available_after_ms": row["available_after_ms"],
            "published_ms": row["published_ms"],
        }

    def publish_outbox(
        self,
        publish: Callable[[dict[str, Any]], Any],
        *,
        limit: int = 100,
        lease_ms: int = 30_000,
    ) -> int:
        delivered = 0
        for _ in range(limit):
            now = self._now_ms()
            claim_token = uuid4().hex
            cx = self._connect()
            try:
                cx.execute("BEGIN IMMEDIATE")
                row = cx.execute(
                    """
                    SELECT * FROM durable_outbox
                    WHERE available_after_ms<=?
                      AND (status='PENDING' OR (status='CLAIMED' AND lease_until_ms<=?))
                    ORDER BY available_after_ms, event_id LIMIT 1
                    """,
                    (now, now),
                ).fetchone()
                if row is None:
                    cx.rollback()
                    break
                cx.execute(
                    """
                    UPDATE durable_outbox SET status='CLAIMED', lease_token=?,
                        lease_until_ms=?, attempts=attempts+1
                    WHERE event_id=?
                    """,
                    (claim_token, now + lease_ms, row["event_id"]),
                )
                cx.commit()
                item = self._decode_outbox(row)
                item["lease_token"] = claim_token
            finally:
                cx.close()
            try:
                publish(item)
            except Exception:
                cx = self._connect()
                try:
                    cx.execute(
                        """
                        UPDATE durable_outbox SET status='PENDING', lease_token=NULL, lease_until_ms=NULL
                        WHERE event_id=? AND lease_token=?
                        """,
                        (item["event_id"], claim_token),
                    )
                    cx.commit()
                finally:
                    cx.close()
                break
            cx = self._connect()
            try:
                cur = cx.execute(
                    """
                    UPDATE durable_outbox SET status='PUBLISHED', lease_token=NULL,
                        lease_until_ms=NULL, published_ms=?
                    WHERE event_id=? AND lease_token=?
                    """,
                    (self._now_ms(), item["event_id"], claim_token),
                )
                cx.commit()
                if cur.rowcount:
                    delivered += 1
            finally:
                cx.close()
        return delivered

    # These methods make invariant tests explicit without exposing mutation as
    # a supported runtime operation.
    def delete_event_for_test(self, run_id: str, *, sequence: int) -> None:
        cx = self._connect()
        try:
            cx.execute("DELETE FROM durable_events WHERE run_id=? AND sequence=?", (run_id, sequence))
            cx.commit()
        finally:
            cx.close()

    def corrupt_snapshot_for_test(self, run_id: str) -> None:
        cx = self._connect()
        try:
            cx.execute("UPDATE durable_runs SET snapshot_json=? WHERE run_id=?", ('{"corrupt":true}', run_id))
            cx.commit()
        finally:
            cx.close()

    def delete_audit_for_test(self, run_id: str) -> None:
        raise AuditAppendOnlyError(f"audit for {run_id} is append-only")


__all__ = [
    "AuditAppendOnlyError",
    "CheckpointConflict",
    "DurableRunStore",
    "DurableStoreError",
    "EventDigestConflict",
    "EventGapError",
    "LeaseFencedError",
    "SnapshotCorruptError",
    "SnapshotSequenceError",
]
