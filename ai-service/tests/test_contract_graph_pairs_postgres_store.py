from __future__ import annotations

import os
import subprocess
import sys

import pytest
from sqlalchemy import insert, inspect, select
from sqlalchemy.exc import IntegrityError
from test_contract_graph_pair_projection import relation
from test_contract_graph_postgres_store import (
    ROOT,
    _ai2_tables,
    _edge_rows,
    _start,
    _store_and_owner,
    _version,
)
from test_contract_graph_postgres_store import fresh_url as fresh_url

from app.db.engine import get_engine
from app.db.migrate import migrate


def rows(engine, rec):
    from app.db.tables import contract_pair_relations as table
    with engine.connect() as cx:
        return list(cx.execute(select(table).where(table.c.tenant_id == rec.tenant_id,
                                                  table.c.dossier_id == rec.dossier_id)).mappings())


def owner(url):
    from fixtures.contract_graph_pair_records import pair_record
    store, base, env, edges = _store_and_owner(url)
    rec = pair_record()
    rec.dossier_id = base.dossier_id
    return store, rec, env, edges, relation(rec)


def finish(store, rec, env, job, token, *, relations, ran=True, edges=()):
    rec.pair_relations = list(relations)
    rec.pair_relations_ran = ran
    rec.contract_edges = list(edges)
    rec.contract_graph_ran = bool(edges)
    return store.complete_with_snapshot(job, tenant_id=rec.tenant_id, dossier_id=rec.dossier_id,
                                        worker_token=token, status="SUCCEEDED", wire={"status": "SUCCEEDED"},
                                        record=rec, envelope=env)


def test_fresh_database_migrates_to_head_with_pair_relations(fresh_url):
    from app.db.tables import contract_pair_relations as table
    engine = get_engine(fresh_url)
    migrate(engine)
    assert _version(engine) == "0006_ai2_contract_pair_relations"
    schema = inspect(engine)
    columns = {c["name"]: c for c in schema.get_columns(table.name, schema="ai2")}
    assert set(columns) == {c.name for c in table.columns}
    assert all(columns[c.name]["nullable"] == c.nullable for c in table.columns)
    assert schema.get_pk_constraint(table.name, schema="ai2")["constrained_columns"] == ["tenant_id", "dossier_id", "relation_id"]
    assert any(i["name"] == "idx_ai2_contract_pair_relations_job" and i["column_names"] == ["tenant_id", "dossier_id", "job_id"]
               for i in schema.get_indexes(table.name, schema="ai2"))


def test_0006_downgrade_entrypoint_then_upgrade(fresh_url):
    engine = get_engine(fresh_url)
    migrate(engine)
    before = _ai2_tables(engine)
    proc = subprocess.run([sys.executable, "-m", "app.db.migrate", "downgrade", "0005_ai2_contract_edges"],
                          cwd=ROOT, env={**os.environ, "AI2_DATABASE_URL": fresh_url}, capture_output=True, timeout=300)
    assert proc.returncode == 0, proc.stderr.decode("utf8", "replace")
    assert _version(engine) == "0005_ai2_contract_edges"
    assert _ai2_tables(engine) == before - {"contract_pair_relations"}
    migrate(engine)
    assert _version(engine) == "0006_ai2_contract_pair_relations"
    assert _ai2_tables(engine) == before


def test_completion_replaces_pair_relations_for_latest_success(fresh_url, monkeypatch):
    store, rec, env, edges, rel = owner(fresh_url)
    one = _start(store, rec, "one", 100, monkeypatch)
    assert finish(store, rec, env, *one, relations=[rel])
    two = _start(store, rec, "two", 200, monkeypatch)
    assert finish(store, rec, env, *two, relations=[rel])
    assert [r["job_id"] for r in rows(store.engine, rec)] == [two[0]]
    three = _start(store, rec, "three", 300, monkeypatch)
    assert finish(store, rec, env, *three, relations=[])
    assert rows(store.engine, rec) == []


def test_older_job_completion_does_not_overwrite_newer_relations(fresh_url, monkeypatch):
    store, rec, env, edges, rel = owner(fresh_url)
    old = _start(store, rec, "old", 100, monkeypatch)
    new = _start(store, rec, "new", 200, monkeypatch)
    assert finish(store, rec, env, *new, relations=[rel])
    assert finish(store, rec, env, *old, relations=[])
    assert [r["job_id"] for r in rows(store.engine, rec)] == [new[0]]


def test_ran_false_leaves_relations_untouched(fresh_url, monkeypatch):
    store, rec, env, edges, rel = owner(fresh_url)
    first = _start(store, rec, "first", 100, monkeypatch)
    assert finish(store, rec, env, *first, relations=[rel])
    second = _start(store, rec, "second", 200, monkeypatch)
    assert finish(store, rec, env, *second, relations=[], ran=False)
    assert [r["job_id"] for r in rows(store.engine, rec)] == [first[0]]


def test_pair_write_failure_keeps_job_succeeded_and_edges_written(fresh_url, monkeypatch):
    from app.tools import pair_relation_store
    store, rec, env, edges, rel = owner(fresh_url)
    first = _start(store, rec, "first", 100, monkeypatch)
    assert finish(store, rec, env, *first, relations=[rel])
    original = pair_relation_store.relation_row
    monkeypatch.setattr(pair_relation_store, "relation_row", lambda *a, **k: {**original(*a, **k), "label": "UNKNOWN"})
    second = _start(store, rec, "second", 200, monkeypatch)
    assert finish(store, rec, env, *second, relations=[rel], edges=edges[:1])
    assert store.get(second[0])["status"] == "SUCCEEDED"
    assert [r["job_id"] for r in rows(store.engine, rec)] == [first[0]]
    assert [r["job_id"] for r in _edge_rows(store.engine, rec.tenant_id, rec.dossier_id)] == [second[0]]


def test_check_constraint_rejects_unknown_label(fresh_url):
    from app.db.tables import contract_pair_relations as table
    from app.tools.pair_relation_store import relation_row
    store, rec, env, edges, rel = owner(fresh_url)
    row = relation_row(rel, tenant_id=rec.tenant_id, dossier_id=rec.dossier_id, job_id="j", now_ms=1)
    with pytest.raises(IntegrityError), store.engine.begin() as cx:
        cx.execute(insert(table).values(**{**row, "label": "UNRELATED"}))
    with store.engine.begin() as cx:
        cx.execute(insert(table).values(**row))
    assert len(rows(store.engine, rec)) == 1
