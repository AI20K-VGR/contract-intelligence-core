"""P4 edge persistence without PostgreSQL: row shape, digest, NUL filter, D9 metadata split,
migration DDL (offline), the downgrade entrypoint dispatch and the SQLite no-op (D7)."""

from __future__ import annotations

import importlib.util
import io
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app.contracts.contract_graph import ContractEdge, EdgeOp
from app.contracts.models import ReviewState
from app.db import tables
from app.pipeline.contract_graph.builder import build_contract_graph
from app.tools.contract_edge_store import edge_digest, edge_row
from fixtures import envelope
from fixtures.contract_graph_records import graph_record

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "app" / "db" / "migrations" / "versions"
TEXT_COLUMNS = {c.name for c in tables.contract_edges.columns if c.type.python_type is str}


@pytest.fixture(scope="module")
def edges() -> list[ContractEdge]:
    record = graph_record()
    return build_contract_graph(record, record.facts).edges


def _row(edge: ContractEdge) -> dict:
    return edge_row(edge, tenant_id="tenant_a", dossier_id="dossier_1", job_id="job_1", now_ms=123)


def test_edge_digest_is_stable_and_content_sensitive(edges):
    edge = edges[0]

    assert edge_digest(edge) == edge_digest(edge.model_copy(deep=True))
    assert len(edge_digest(edge)) == 64
    changed = edge.model_copy(update={"review_state": ReviewState.INSUFFICIENT_EVIDENCE})
    assert edge_digest(changed) != edge_digest(edge)
    assert len({edge_digest(e) for e in edges}) == len(edges)


def test_edge_row_has_every_table_column(edges):
    row = _row(edges[0])

    assert set(row) == {c.name for c in tables.contract_edges.columns}
    assert row["op"] == edges[0].op.value
    assert row["standard"] in (0, 1) and row["implicit"] in (0, 1)
    assert row["digest"] == edge_digest(edges[0])
    assert (row["job_id"], row["created_ms"]) == ("job_1", 123)
    assert row["source_snapshot_digest"] == edges[0].source_snapshot_digest
    for column in tables.contract_edges.columns:
        if not column.nullable:
            assert row[column.name] is not None, column.name


def test_contract_edges_table_not_in_initial_metadata():
    # D9: 0001 runs ``metadata.create_all``; sharing it would make 0005 hit DuplicateTable.
    assert "ai2.contract_edges" not in tables.metadata.tables
    assert "contract_edges" not in {t.name for t in tables.metadata.tables.values()}
    assert tables.contract_edges.metadata is tables.graph_metadata
    assert tables.contract_edges.schema == "ai2"


def test_edge_row_strips_nul_from_text_columns(edges):
    edge = edges[0]
    dirty_citation = edge.source_citation.model_copy(update={"text_span": "Sửa\x00 đổi"})
    dirty = edge.model_copy(
        update={
            "source_citation": dirty_citation,
            "new_text": "“c)\x00 Đợt 3”",
            "scope_text": "lô\x00 hàng",
            "target_address": "diem c\x00 khoan 1",
        }
    )

    row = _row(dirty)

    for name in TEXT_COLUMNS:
        value = row[name]
        assert value is None or "\x00" not in value, name
        assert value is None or "\\u0000" not in value, name
    assert row["new_text"] == "“c) Đợt 3”"
    assert "Sửa đổi" in row["source_citation_json"]


def _load_0005():
    path = VERSIONS / "0005_ai2_contract_edges.py"
    spec = importlib.util.spec_from_file_location("ai2_mig_0005", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _offline_sql(fn) -> str:
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    buf = io.StringIO()
    ctx = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": buf})
    with Operations.context(ctx):
        fn()
    return buf.getvalue()


def test_migration_chain_has_single_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config()
    config.set_main_option("script_location", str(ROOT / "app" / "db" / "migrations"))
    script = ScriptDirectory.from_config(config)

    assert len(script.get_heads()) == 1
    assert script.get_revision("0006_ai2_contract_pair_relations").down_revision == "0005_ai2_contract_edges"
    assert script.get_revision("0005_ai2_contract_edges").down_revision == "0004_ai2_job_indexes"


def test_0005_ddl_matches_table_declaration():
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable

    module = _load_0005()
    up = _offline_sql(module.upgrade)
    declared = str(CreateTable(tables.contract_edges).compile(dialect=postgresql.dialect()))

    def column_lines(sql: str) -> list[str]:
        body = sql[sql.index("CREATE TABLE ai2.contract_edges") :]
        body = body[: body.index(";")] if ";" in body else body
        return sorted(
            line.strip().rstrip(",")
            for line in body.splitlines()[1:]
            if line.strip() and not line.strip().startswith(("PRIMARY", "CONSTRAINT", "CHECK", ")"))
        )

    assert column_lines(up) == column_lines(declared)
    assert "PRIMARY KEY (tenant_id, dossier_id, edge_id)" in up
    ops = ", ".join(f"'{op.value}'" for op in EdgeOp)
    assert f"op IN ({ops})" in up
    assert "CREATE INDEX idx_ai2_contract_edges_job ON ai2.contract_edges (tenant_id, dossier_id, job_id)" in up
    down = _offline_sql(module.downgrade)
    assert "DROP INDEX ai2.idx_ai2_contract_edges_job" in down
    assert "DROP TABLE ai2.contract_edges" in down
    assert down.count("DROP TABLE") == 1


def test_migrate_cli_dispatches_downgrade(monkeypatch):
    from app.db import migrate as migrate_module

    calls = []
    monkeypatch.setenv("AI2_DATABASE_URL", "postgresql://u:p@db/x")
    monkeypatch.setattr(migrate_module, "_engine_from_env", lambda: "ENGINE")
    monkeypatch.setattr(migrate_module, "downgrade", lambda engine, rev: calls.append((engine, rev)))

    assert migrate_module.main(["downgrade", "0004_ai2_job_indexes"]) == 0
    assert calls == [("ENGINE", "0004_ai2_job_indexes")]
    with pytest.raises(SystemExit):
        migrate_module.main(["downgrade"])


def test_migrate_module_entrypoint_requires_database_url():
    env = {k: v for k, v in os.environ.items() if k != "AI2_DATABASE_URL"}
    proc = subprocess.run(
        [sys.executable, "-m", "app.db.migrate", "downgrade", "0004_ai2_job_indexes"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        timeout=120,
    )

    assert proc.returncode == 2
    assert b"AI2_DATABASE_URL" in proc.stderr


def test_sqlite_job_store_ignores_contract_edges(tmp_path, monkeypatch, edges):
    from app.tools import query_store
    from app.tools.jobs import SQLiteJobStore

    saved = []
    monkeypatch.setattr(query_store, "save_query_snapshot", lambda record, env: saved.append(record))
    path = tmp_path / "jobs.sqlite"
    store = SQLiteJobStore(path)
    record = graph_record()
    record.contract_edges = list(edges)
    record.contract_graph_ran = True
    job, _ = store.create_or_get(
        tenant_id=record.tenant_id, dossier_id=record.dossier_id, request_id="r", idempotency_key="k",
        attempt=1, request={}, wire={},
    )
    token = store.claim(job["job_id"], tenant_id=record.tenant_id, dossier_id=record.dossier_id)

    assert store.complete_with_snapshot(
        job["job_id"], tenant_id=record.tenant_id, dossier_id=record.dossier_id, worker_token=token,
        status="SUCCEEDED", wire={"status": "SUCCEEDED"}, record=record, envelope=envelope(),
    )
    assert saved == [record]
    with sqlite3.connect(path) as cx:
        names = {row[0] for row in cx.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert names == {"jobs", "service_nonces"}
