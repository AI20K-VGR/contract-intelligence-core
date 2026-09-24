"""Durable read model for production AI2 queries.

The Kafka IDP worker and the HTTP query API are separate processes.  Keeping
the adapted snapshot only in ``InMemorySnapshotStore`` makes a completed IDP
job impossible to query after the worker returns or restarts.  This module
stores the public, citation-bearing ``DossierRecord`` and its ``ToolEnvelope``
in the same SQLite data root used by AI2's other durable stores.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from app.contracts.models import ToolEnvelope
from app.tools.persist import DATA, record_from_dict, record_to_dict
from app.tools.store import DossierRecord

DB = DATA / "runs.sqlite"


def _conn() -> sqlite3.Connection:
    DATA.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS dossier_query_snapshots (
            tenant_id TEXT NOT NULL,
            dossier_id TEXT NOT NULL,
            snapshot_digest TEXT NOT NULL,
            payload TEXT NOT NULL,
            updated_ms INTEGER NOT NULL,
            PRIMARY KEY (tenant_id, dossier_id)
        )
        """
    )
    return connection


def save_query_snapshot(record: DossierRecord, envelope: ToolEnvelope) -> None:
    """Upsert one citation-bearing snapshot for the query read model."""

    payload: dict[str, Any] = {
        "record": record_to_dict(record),
        "envelope": envelope.model_dump(),
    }
    connection = _conn()
    try:
        connection.execute(
            """
            INSERT INTO dossier_query_snapshots
                (tenant_id, dossier_id, snapshot_digest, payload, updated_ms)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (tenant_id, dossier_id) DO UPDATE SET
                snapshot_digest = excluded.snapshot_digest,
                payload = excluded.payload,
                updated_ms = excluded.updated_ms
            """,
            (
                record.tenant_id,
                record.dossier_id,
                record.pins.source_snapshot_digest,
                json.dumps(payload, ensure_ascii=False),
                int(time.time() * 1000),
            ),
        )
        connection.commit()
    finally:
        connection.close()


def load_query_snapshot(
    dossier_id: str,
    *,
    tenant_id: str | None = None,
) -> tuple[DossierRecord, ToolEnvelope] | None:
    """Load a snapshot, optionally enforcing tenant scope.

    The current Backend query contract does not yet forward tenant_id.  When
    it is absent, the dossier ULID is used as the lookup key and the stored
    tenant remains attached to the returned envelope.  Callers should pass
    tenant_id as soon as the upstream contract exposes it.
    """

    connection = _conn()
    try:
        if tenant_id:
            row = connection.execute(
                "SELECT payload FROM dossier_query_snapshots WHERE tenant_id = ? AND dossier_id = ?",
                (tenant_id, dossier_id),
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT payload FROM dossier_query_snapshots WHERE dossier_id = ? ORDER BY updated_ms DESC LIMIT 1",
                (dossier_id,),
            ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    payload = json.loads(row[0])
    return record_from_dict(payload["record"]), ToolEnvelope.model_validate(payload["envelope"])


__all__ = ["load_query_snapshot", "save_query_snapshot"]
