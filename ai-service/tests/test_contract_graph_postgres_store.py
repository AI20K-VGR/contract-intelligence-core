"""P4 on real PostgreSQL: migration 0005 up/down/up, edge replace under the completion fence,
savepoint isolation of edge writes (RT-03, RT-04, D7, D9).

Every test runs on its own freshly created database (``CREATE DATABASE`` on the ``pg_url``
server), so the downgrade test never leaves the session database below head. Run with
``AI2_REQUIRE_DOCKER=1`` so a missing PostgreSQL fails instead of skipping.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
OLD_HEAD = "0004_ai2_job_indexes"
NEW_HEAD = "0005_ai2_contract_edges"


@pytest.fixture
def fresh_url(pg_url):
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    from app.db.engine import get_engine

    admin_url = make_url(pg_url).set(drivername="postgresql+psycopg")
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    database = f"ai2_edges_{uuid4().hex[:10]}"
    with admin.connect() as cx:
        cx.execute(text(f'CREATE DATABASE "{database}"'))
    url = admin_url.set(database=database).render_as_string(hide_password=False)
    get_engine.cache_clear()  # a None-keyed engine cached by an earlier test must not answer for this DB
    try:
        yield url
    finally:
        get_engine(url).dispose()
        # get_engine() with no argument caches the env-resolved engine under key None; drop it so
        # later tests do not reuse an engine bound to the database dropped below.
        get_engine.cache_clear()
        with admin.connect() as cx:
            cx.execute(text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
        admin.dispose()


def _version(engine) -> str:
    from sqlalchemy import text

    with engine.connect() as cx:
        return cx.execute(text("SELECT version_num FROM ai2.alembic_version")).scalar()


def _ai2_tables(engine) -> set[str]:
    from sqlalchemy import inspect

    return set(inspect(engine).get_table_names(schema="ai2"))


def _edge_rows(engine, tenant_id: str, dossier_id: str) -> list[dict]:
    from sqlalchemy import select

    from app.db.tables import contract_edges

    with engine.connect() as cx:
        return [dict(r) for r in cx.execute(select(contract_edges).where(
            contract_edges.c.tenant_id == tenant_id, contract_edges.c.dossier_id == dossier_id,
        ).order_by(contract_edges.c.edge_id)).mappings()]


def test_fresh_database_migrates_to_0005_with_contract_edges(fresh_url):
    from sqlalchemy import inspect

    from app.db.engine import get_engine
    from app.db.migrate import migrate
    from app.db.tables import contract_edges

    engine = get_engine(fresh_url)
    migrate(engine)  # 0001 create_all must not already hold contract_edges (D9)
    migrate(engine)

    assert _version(engine) == NEW_HEAD
    columns = {c["name"]: c for c in inspect(engine).get_columns("contract_edges", schema="ai2")}
    assert set(columns) == {c.name for c in contract_edges.columns}
    for column in contract_edges.columns:
        assert columns[column.name]["nullable"] == column.nullable, column.name
    pk = inspect(engine).get_pk_constraint("contract_edges", schema="ai2")
    assert pk["constrained_columns"] == ["tenant_id", "dossier_id", "edge_id"]
    indexes = {i["name"]: i for i in inspect(engine).get_indexes("contract_edges", schema="ai2")}
    assert indexes["idx_ai2_contract_edges_job"]["column_names"] == ["tenant_id", "dossier_id", "job_id"]


def test_0005_downgrade_entrypoint_then_upgrade(fresh_url):
    from app.db.engine import get_engine
    from app.db.migrate import migrate

    engine = get_engine(fresh_url)
    migrate(engine)
    before = _ai2_tables(engine)
    assert "contract_edges" in before

    env = {**os.environ, "AI2_DATABASE_URL": fresh_url}
    proc = subprocess.run(
        [sys.executable, "-m", "app.db.migrate", "downgrade", OLD_HEAD],
        cwd=ROOT, env=env, capture_output=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")

    assert _version(engine) == OLD_HEAD
    assert _ai2_tables(engine) == before - {"contract_edges"}
    migrate(engine)
    assert _version(engine) == NEW_HEAD
    assert _ai2_tables(engine) == before


def _store_and_owner(url):
    from app.pipeline.contract_graph.builder import build_contract_graph
    from app.tools.jobs import PostgresJobStore
    from fixtures import envelope
    from fixtures.contract_graph_records import graph_record

    store = PostgresJobStore(url)
    record, env = graph_record(), envelope()
    record.dossier_id = uuid4().hex
    env.auth.dossier_id = record.dossier_id
    edges = build_contract_graph(record, record.facts).edges
    assert len(edges) >= 2
    return store, record, env, edges


def _start(store, record, name: str, now: int, monkeypatch):
    monkeypatch.setattr(store, "_now_ms", lambda: now)
    job, _ = store.create_or_get(tenant_id=record.tenant_id, dossier_id=record.dossier_id, attempt=1,
                                 request={}, wire={}, request_id=name, idempotency_key=record.dossier_id + name)
    token = store.claim(job["job_id"], tenant_id=record.tenant_id, dossier_id=record.dossier_id)
    return job["job_id"], token


def _finish(store, record, env, job_id, token, *, edges, ran=True):
    record.contract_edges = list(edges)
    record.contract_graph_ran = ran
    return store.complete_with_snapshot(job_id, tenant_id=record.tenant_id, dossier_id=record.dossier_id,
                                        worker_token=token, status="SUCCEEDED", wire={"status": "SUCCEEDED"},
                                        record=record, envelope=env)


def test_completion_replaces_edges_for_latest_success(fresh_url, monkeypatch):
    store, record, env, edges = _store_and_owner(fresh_url)
    first = _start(store, record, "one", 100, monkeypatch)
    assert _finish(store, record, env, *first, edges=edges[:2])
    rows = _edge_rows(store.engine, record.tenant_id, record.dossier_id)
    assert [r["job_id"] for r in rows] == [first[0]] * 2

    second = _start(store, record, "two", 200, monkeypatch)
    assert _finish(store, record, env, *second, edges=edges[2:3])
    rows = _edge_rows(store.engine, record.tenant_id, record.dossier_id)
    assert [(r["edge_id"], r["job_id"]) for r in rows] == [(edges[2].edge_id, second[0])]
    assert rows[0]["source_snapshot_digest"] == record.pins.source_snapshot_digest


def test_older_job_completion_does_not_overwrite_newer_edges(fresh_url, monkeypatch):
    store, record, env, edges = _store_and_owner(fresh_url)
    old = _start(store, record, "old", 100, monkeypatch)
    new = _start(store, record, "new", 200, monkeypatch)

    assert _finish(store, record, env, *new, edges=edges[:1])
    assert _finish(store, record, env, *old, edges=edges[:2])  # accepted, but not the latest
    rows = _edge_rows(store.engine, record.tenant_id, record.dossier_id)
    assert [(r["edge_id"], r["job_id"]) for r in rows] == [(edges[0].edge_id, new[0])]
    assert store.get(old[0])["status"] == "SUCCEEDED"


def test_record_without_graph_run_leaves_edges_untouched(fresh_url, monkeypatch):
    store, record, env, edges = _store_and_owner(fresh_url)
    first = _start(store, record, "one", 100, monkeypatch)
    assert _finish(store, record, env, *first, edges=edges[:2])

    second = _start(store, record, "two", 200, monkeypatch)
    assert _finish(store, record, env, *second, edges=[], ran=False)
    rows = _edge_rows(store.engine, record.tenant_id, record.dossier_id)
    assert [r["job_id"] for r in rows] == [first[0]] * 2


def test_edge_write_failure_keeps_job_succeeded(fresh_url, monkeypatch):
    from app.tools import contract_edge_store
    from app.tools.query_store import load_query_snapshot

    store, record, env, edges = _store_and_owner(fresh_url)
    first = _start(store, record, "one", 100, monkeypatch)
    assert _finish(store, record, env, *first, edges=edges[:2])

    original = contract_edge_store.edge_row

    def bad_row(edge, **kwargs):  # passes Python, fails the CHECK after DELETE already ran
        return {**original(edge, **kwargs), "op": "AMENDS"}

    monkeypatch.setattr(contract_edge_store, "edge_row", bad_row)
    record.pins.source_snapshot_digest = env.pins.source_snapshot_digest = "b" * 64
    second = _start(store, record, "two", 200, monkeypatch)
    assert _finish(store, record, env, *second, edges=edges[:1])

    assert store.get(second[0])["status"] == "SUCCEEDED"
    monkeypatch.setenv("AI2_DATABASE_URL", fresh_url)
    saved, _ = load_query_snapshot(record.dossier_id, tenant_id=record.tenant_id)
    assert saved.pins.source_snapshot_digest == "b" * 64  # the new job's snapshot committed
    rows = _edge_rows(store.engine, record.tenant_id, record.dossier_id)
    assert [r["job_id"] for r in rows] == [first[0]] * 2  # savepoint undid the DELETE


def test_worker_edge_write_failure_reports_succeeded_wire(fresh_url, monkeypatch):
    from fastapi.testclient import TestClient
    from test_a1_query_digest import _body_only_request, _poll

    from app.api import main
    from app.tools import contract_edge_store
    from app.tools.jobs import PostgresJobStore
    from app.tools.store import InMemorySnapshotStore

    calls = []

    def boom(*_args, **_kwargs):
        calls.append(1)
        raise RuntimeError("synthetic edge write failure")

    monkeypatch.setenv("AI2_DATABASE_URL", fresh_url)
    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "test-secret")
    monkeypatch.setenv("AI2_PROCESSING_EGRESS_ALLOWED", "false")
    monkeypatch.setenv("AI2_CONTRACT_GRAPH_ENABLED", "1")
    monkeypatch.setattr(contract_edge_store, "replace_contract_edges", boom)
    monkeypatch.setattr(main, "JOB_STORE", PostgresJobStore(fresh_url))
    monkeypatch.setattr(main, "STORE", InMemorySnapshotStore())
    payload = _body_only_request()
    with TestClient(main.app) as client:
        response = client.post("/jobs/idp", json=payload)
        assert response.status_code == 202
        wire = _poll(client, response.json()["job_id"], payload["dossier_id"])

    assert calls == [1]
    assert wire["status"] == "SUCCEEDED"
    assert not any(e["code"] == "AI2_WORKER_FAILED" for e in wire.get("errors", []))
    assert "contract_graph" in wire["result"]["index_contribution"]["coverage"]


def test_check_constraint_rejects_unknown_op(fresh_url):
    from sqlalchemy import insert
    from sqlalchemy.exc import IntegrityError

    from app.db.engine import get_engine
    from app.db.migrate import migrate
    from app.db.tables import contract_edges
    from app.pipeline.contract_graph.builder import build_contract_graph
    from app.tools.contract_edge_store import edge_row
    from fixtures.contract_graph_records import graph_record

    engine = get_engine(fresh_url)
    migrate(engine)
    record = graph_record()
    edge = build_contract_graph(record, record.facts).edges[0]
    row = edge_row(edge, tenant_id="t", dossier_id="d", job_id="j", now_ms=1)

    with pytest.raises(IntegrityError):
        with engine.begin() as cx:
            cx.execute(insert(contract_edges).values(**{**row, "op": "AMENDS"}))
    with engine.begin() as cx:
        cx.execute(insert(contract_edges).values(**row))
    assert len(_edge_rows(engine, "t", "d")) == 1
