"""PostgreSQL dossier erasure; metadata-only tombstones survive content deletion."""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.contracts.errors import DossierDeletedError
from app.db.engine import ensure_database, get_engine


def is_deleted_write(exc: Exception) -> bool:
    """Recognize the DB fence without serializing SQL parameters into errors/logs."""
    original = getattr(exc, "orig", None)
    diag = getattr(original, "diag", None)
    return isinstance(exc, DossierDeletedError) or (
        getattr(original, "sqlstate", None) == "23514"
        and getattr(diag, "message_primary", None) == "AI2_DOSSIER_DELETED"
    )


def is_dossier_deleted(tenant_id: str, dossier_id: str) -> bool:
    engine = get_engine()
    ensure_database(engine)
    with engine.connect() as cx:
        return bool(cx.execute(text("""SELECT 1 FROM ai2.dossier_tombstones
            WHERE tenant_id=:tenant AND dossier_id=:dossier"""),
            {"tenant": tenant_id, "dossier": dossier_id}).scalar())


def require_live_dossier(tenant_id: str, dossier_id: str) -> None:
    if is_dossier_deleted(tenant_id, dossier_id):
        raise DossierDeletedError("AI2_DOSSIER_DELETED")


def retry_pending_purges(*, data_dir: Path, limit: int = 10) -> None:
    """Resume committed erasures whose file cleanup failed or process crashed."""
    engine = get_engine()
    ensure_database(engine)
    with engine.connect() as cx:
        pending = list(cx.execute(text("""SELECT tenant_id,dossier_id FROM ai2.dossier_tombstones
            WHERE status='pending' ORDER BY deleted_ms LIMIT :limit"""), {"limit": limit}))
    for tenant, dossier in pending:
        try:
            purge_dossier(tenant, dossier, data_dir=data_dir)
        except (OSError, SQLAlchemyError):
            # Leave pending for the next sweep and for Backend's signed retry.
            continue


def purge_dossier(tenant_id: str, dossier_id: str, *, data_dir: Path) -> dict:
    """Commit DB erasure first; retained session IDs make file cleanup retryable.

    No payload/text/path from the deleted content is retained in the ledger.
    Postgres sessions store blobs in DB; the file pass also removes legacy blobs.
    """
    engine = get_engine()
    ensure_database(engine)
    scope = {"tenant": tenant_id, "dossier": dossier_id}
    with engine.begin() as cx:
        cx.execute(text("SELECT pg_advisory_xact_lock(131, 2)"))
        cx.execute(text("""INSERT INTO ai2.dossier_tombstones(tenant_id,dossier_id,deleted_ms)
            VALUES (:tenant,:dossier,:now) ON CONFLICT DO NOTHING"""),
            {**scope, "now": int(time.time() * 1000)})
        prior = cx.execute(text("""SELECT evidence_json FROM ai2.dossier_tombstones
            WHERE tenant_id=:tenant AND dossier_id=:dossier FOR UPDATE"""), scope).scalar_one()
        evidence = json.loads(prior)
        deleted = {}
        for kind, child, key in (
            ("sessions", "session_blobs", "session_id"),
            ("durable_runs", "durable_outbox", "run_id"),
            ("durable_runs", "durable_events", "run_id"),
            ("durable_runs", "durable_checkpoints", "run_id"),
            ("durable_runs", "durable_audit", "run_id"),
            ("sessions", "sessions", "session_id"),
            ("durable_runs", "durable_runs", "run_id"),
        ):
            deleted[child] = cx.execute(text(f"""DELETE FROM ai2.{child} c
                WHERE EXISTS (SELECT 1 FROM ai2.dossier_resource_refs r
                    WHERE r.tenant_id=:tenant AND r.dossier_id=:dossier
                      AND r.resource_kind=:kind AND r.resource_id=c.{key})"""),
                {**scope, "kind": kind}).rowcount
        for table in (
            "contract_edges", "contract_pair_relations", "contract_graph_write_receipts",
            "ai2_processing_trace_events", "dossier_query_snapshots", "jobs",
        ):
            deleted[table] = cx.execute(text(f"""DELETE FROM ai2.{table}
                WHERE tenant_id=:tenant AND dossier_id=:dossier"""), scope).rowcount
        deleted["vector_segments"] = cx.execute(text("""WITH unreferenced AS (
                SELECT DISTINCT owned.snapshot_digest FROM ai2.dossier_resource_refs owned
                WHERE owned.tenant_id=:tenant AND owned.dossier_id=:dossier
                  AND owned.snapshot_digest<>'' AND NOT EXISTS (
                    SELECT 1 FROM ai2.dossier_resource_refs live
                    WHERE live.snapshot_digest=owned.snapshot_digest AND NOT EXISTS (
                        SELECT 1 FROM ai2.dossier_tombstones t
                        WHERE t.tenant_id=live.tenant_id AND t.dossier_id=live.dossier_id)))
            DELETE FROM ai2.vector_segments WHERE snapshot_digest IN (
                SELECT snapshot_digest FROM unreferenced UNION ALL
                SELECT 'sha256:' || snapshot_digest FROM unreferenced)"""), scope).rowcount
        session_ids = list(cx.execute(text("""SELECT DISTINCT resource_id FROM ai2.dossier_resource_refs
            WHERE tenant_id=:tenant AND dossier_id=:dossier AND resource_kind='sessions'"""), scope).scalars())
        cumulative = dict(evidence.get("deleted", {}))
        for table, count in deleted.items():
            cumulative[table] = cumulative.get(table, 0) + count
        evidence["deleted"] = cumulative
        cx.execute(text("""UPDATE ai2.dossier_tombstones SET status='pending', evidence_json=:evidence
            WHERE tenant_id=:tenant AND dossier_id=:dossier"""),
            {**scope, "evidence": json.dumps(evidence)})

    # Identifiers are bounded path components; never trust paths inside session payload.
    removed_dirs = 0
    root = Path(data_dir).resolve() / "blobs"
    if root.is_symlink() or getattr(root, "is_junction", lambda: False)():
        raise OSError("AI2_PURGE_UNSAFE_SESSION_PATH")
    for sid in session_ids:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", sid):
            raise OSError("AI2_PURGE_UNSAFE_SESSION_PATH")
        candidate = root / sid
        if candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)():
            raise OSError("AI2_PURGE_UNSAFE_SESSION_PATH")
        resolved = candidate.resolve()
        if not resolved.is_relative_to(root.resolve()):
            raise OSError("AI2_PURGE_UNSAFE_SESSION_PATH")
        if candidate.exists():
            try:
                shutil.rmtree(candidate)
                removed_dirs += 1
            except FileNotFoundError:
                # Another retry may have removed a child while rmtree was walking.
                # Only absence of the entire directory proves cleanup completed.
                if candidate.exists():
                    raise OSError("AI2_PURGE_INCOMPLETE") from None
    with engine.begin() as cx:
        cx.execute(text("SELECT pg_advisory_xact_lock(131, 2)"))
        # Merge after re-reading: overlapping retries cannot lose accumulated evidence.
        evidence = json.loads(cx.execute(text("""SELECT evidence_json FROM ai2.dossier_tombstones
            WHERE tenant_id=:tenant AND dossier_id=:dossier FOR UPDATE"""), scope).scalar_one())
        evidence["blob_directories"] = evidence.get("blob_directories", 0) + removed_dirs
        cx.execute(text("""UPDATE ai2.dossier_tombstones SET status='completed', evidence_json=:evidence
            WHERE tenant_id=:tenant AND dossier_id=:dossier"""),
            {**scope, "evidence": json.dumps(evidence)})
    return {"status": "completed", "deleted": deleted, "evidence": evidence}
