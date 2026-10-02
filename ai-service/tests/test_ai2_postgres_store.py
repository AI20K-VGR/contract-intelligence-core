"""Real PostgreSQL controls for schema isolation and all five store boundaries."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest


def test_job_persists_its_own_record_when_another_job_changes_shared_store(pg_url, monkeypatch):
    import copy

    from fastapi.testclient import TestClient
    from test_a1_query_digest import _body_only_request, _poll

    from app.api import main
    from app.tools.jobs import PostgresJobStore
    from app.tools.query_store import load_query_snapshot
    from app.tools.store import InMemorySnapshotStore

    monkeypatch.setenv("AI2_DATABASE_URL", pg_url)
    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "test-secret")
    monkeypatch.setenv("AI2_PROCESSING_EGRESS_ALLOWED", "false")
    monkeypatch.setattr(main, "JOB_STORE", PostgresJobStore(pg_url))
    monkeypatch.setattr(main, "STORE", InMemorySnapshotStore())
    original = main.run_idp

    def interleaved(record, envelope, **kwargs):
        result = original(record, envelope, **kwargs)
        later = copy.deepcopy(record)
        later.pins = later.pins.model_copy(update={"source_snapshot_digest": "f" * 64})
        main.STORE.put(later)
        return result

    monkeypatch.setattr(main, "run_idp", interleaved)
    payload = _body_only_request()
    with TestClient(main.app) as client:
        response = client.post("/jobs/idp", json=payload)
        assert response.status_code == 202
        wire = _poll(client, response.json()["job_id"], payload["dossier_id"])
    record, envelope = load_query_snapshot(payload["dossier_id"], tenant_id="tenant_a")
    assert wire["status"] == "SUCCEEDED"
    assert record.pins.source_snapshot_digest == envelope.pins.source_snapshot_digest == wire["query_snapshot_digest"]


@pytest.mark.parametrize("interleave_cache_write", [False, True])
def test_query_reads_current_postgres_snapshot_instead_of_cached_previous_version(pg_url, monkeypatch, interleave_cache_write):
    import copy

    from fastapi.testclient import TestClient

    from app.api import main
    from app.security.service_envelope import build_service_envelope
    from app.tools.query_store import save_query_snapshot
    from app.tools.store import InMemorySnapshotStore
    from fixtures import envelope as make_envelope
    from fixtures import mock_record

    monkeypatch.setenv("AI2_DATABASE_URL", pg_url)
    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "test-secret")
    monkeypatch.setenv("AI2_QUERY_EGRESS_ALLOWED", "false")
    record, envelope = mock_record(), make_envelope()
    record.dossier_id = uuid4().hex
    envelope.auth.dossier_id = record.dossier_id
    cache = InMemorySnapshotStore()
    previous = copy.deepcopy(record)
    cache.put(previous)
    monkeypatch.setattr(main, "STORE", cache)
    record.pins.source_snapshot_digest = "b" * 64
    envelope.pins.source_snapshot_digest = "b" * 64
    save_query_snapshot(record, envelope)
    if interleave_cache_write:
        original = main.QueryRouter

        def interleaved_router(*args, **kwargs):
            main.STORE.put(previous)
            return original(*args, **kwargs)

        monkeypatch.setattr(main, "QueryRouter", interleaved_router)
    query = dict(query="contract value", dossier_id=record.dossier_id, snapshot_digest="b" * 64)
    query["service_envelope"] = build_service_envelope(query, secret="test-secret", tenant_id=record.tenant_id,
        dossier_id=record.dossier_id, scopes=["ai2.query"])
    response = TestClient(main.app).post("/query", json=query)
    assert response.status_code == 200
    assert response.json()["retrieval_layer"]["source"] == "ai2.canonical.store"
    assert response.json()["state"] != "BLOCKED"
    assert response.json()["citations"]
    if not interleave_cache_write:
        assert main.STORE.get(record.tenant_id, record.dossier_id).pins.source_snapshot_digest == "b" * 64


def test_job_completion_fences_snapshot_and_keeps_newer_success(pg_url, monkeypatch):
    from app.tools.jobs import PostgresJobStore
    from app.tools.query_store import load_query_snapshot
    from fixtures.llm_units_snapshot import llm_units_envelope, llm_units_record

    monkeypatch.setenv("AI2_DATABASE_URL", pg_url)
    store = PostgresJobStore(pg_url)
    record, envelope = llm_units_record(), llm_units_envelope()
    record.dossier_id = uuid4().hex
    envelope.auth.dossier_id = record.dossier_id
    args = dict(tenant_id=record.tenant_id, dossier_id=record.dossier_id, attempt=1, request={}, wire={})
    monkeypatch.setattr(store, "_now_ms", lambda: 100)
    old, _ = store.create_or_get(**args, request_id="old", idempotency_key=record.dossier_id + ":old")
    old_token = store.claim(old["job_id"], tenant_id=record.tenant_id, dossier_id=record.dossier_id)
    monkeypatch.setattr(store, "_now_ms", lambda: 200)
    new, _ = store.create_or_get(**args, request_id="new", idempotency_key=record.dossier_id + ":new")
    new_token = store.claim(new["job_id"], tenant_id=record.tenant_id, dossier_id=record.dossier_id)

    def finish(job, token):
        return store.complete_with_snapshot(job["job_id"], tenant_id=record.tenant_id,
            dossier_id=record.dossier_id, worker_token=token, status="SUCCEEDED", wire={"status": "SUCCEEDED"},
            record=record, envelope=envelope)

    assert not finish(old, "stale")
    assert load_query_snapshot(record.dossier_id, tenant_id=record.tenant_id) is None
    record.pins.source_snapshot_digest = "b" * 64
    envelope.pins.source_snapshot_digest = "b" * 64
    assert finish(new, new_token)
    record.pins.source_snapshot_digest = "a" * 64
    envelope.pins.source_snapshot_digest = "a" * 64
    assert finish(old, old_token)
    saved, _ = load_query_snapshot(record.dossier_id, tenant_id=record.tenant_id)
    assert saved.pins.source_snapshot_digest == "b" * 64
    assert store.get(old["job_id"])["status"] == "SUCCEEDED"


def test_session_payload_and_blobs_are_read_from_one_database_snapshot(pg_url, monkeypatch):
    from sqlalchemy import event

    from app.db.engine import get_engine
    from app.tools import persist
    from app.tools.store import InMemorySnapshotStore
    from fixtures.llm_units_snapshot import llm_units_envelope, llm_units_record

    monkeypatch.setenv("AI2_DATABASE_URL", pg_url)
    sid = uuid4().hex
    store = InMemorySnapshotStore()
    old = dict(record=llm_units_record(), envelope=llm_units_envelope(), filename="old.pdf",
               source="synthetic", step="extract", blobs={"contract": b"old-bytes"})
    new = {**old, "filename": "new.pdf", "blobs": {"contract": b"new-bytes"}}
    persist.save_session(sid, old, store)
    engine = get_engine()
    triggered = False

    def after_select(conn, cursor, statement, parameters, context, executemany):
        nonlocal triggered
        if not triggered and statement.lstrip().upper().startswith("SELECT") and "sessions" in statement:
            triggered = True
            persist.save_session(sid, new, store)

    event.listen(engine, "after_cursor_execute", after_select)
    try:
        loaded = persist.load_session(sid, store)
    finally:
        event.remove(engine, "after_cursor_execute", after_select)
    assert triggered
    assert loaded["filename"] == "old.pdf"
    assert loaded["blobs"] == {"contract": b"old-bytes"}


def test_migrations_stay_inside_ai2_and_are_repeatable(pg_url):
    from sqlalchemy import inspect, text

    from app.db.engine import get_engine
    from app.db.migrate import migrate

    engine = get_engine(pg_url)
    with engine.begin() as cx:
        cx.execute(text("CREATE TABLE IF NOT EXISTS public.ai2_probe_marker (value text)"))
    migrate(engine)
    migrate(engine)
    names = set(inspect(engine).get_table_names(schema="ai2"))
    indexes = inspect(engine).get_indexes("vector_segments", schema="ai2")
    assert any(index["column_names"] == ["snapshot_digest", "embedding_model", "dimensions"] for index in indexes)
    assert {"jobs", "service_nonces", "dossier_query_snapshots", "durable_runs", "durable_events", "durable_audit", "durable_outbox", "sessions", "vector_segments", "alembic_version"} <= names
    assert "ai2_probe_marker" in inspect(engine).get_table_names(schema="public")


def test_jobs_concurrent_dedupe_claim_and_fencing(pg_url):
    from app.tools.jobs import PostgresJobStore

    store = PostgresJobStore(pg_url)
    key = uuid4().hex
    arguments = dict(tenant_id="pg-test", dossier_id=key, request_id=key, idempotency_key=key,
                     attempt=1, request={}, wire={"status": "QUEUED"}, nonce=key, request_fingerprint="same")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: store.create_or_get(**arguments), range(4)))
    assert sum(created for _, created in results) == 1
    assert len({job["job_id"] for job, _ in results}) == 1
    job_id = results[0][0]["job_id"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        tokens = list(pool.map(lambda _: store.claim(job_id, tenant_id="pg-test", dossier_id=key), range(4)))
    assert sum(token is not None for token in tokens) == 1
    assert not store.set_wire(job_id, tenant_id="pg-test", dossier_id=key, worker_token="stale", status="SUCCEEDED", wire={})
    token = next(token for token in tokens if token)
    assert store.set_wire(job_id, tenant_id="pg-test", dossier_id=key, worker_token=token, status="SUCCEEDED", wire={"status": "SUCCEEDED"})
    store.engine.dispose()
    reopened = PostgresJobStore(pg_url)
    assert reopened.get(job_id, tenant_id="pg-test", dossier_id=key)["status"] == "SUCCEEDED"


def test_nonce_conflict_rolls_back_new_job(pg_url):
    from app.tools.jobs import JobNonceReplayConflict, PostgresJobStore

    store = PostgresJobStore(pg_url)
    nonce = uuid4().hex
    args = dict(tenant_id="pg-test", dossier_id=nonce, request_id=nonce, attempt=1, request={}, wire={}, nonce=nonce)
    store.create_or_get(**args, idempotency_key=nonce, request_fingerprint="first")
    with pytest.raises(JobNonceReplayConflict):
        store.create_or_get(**args, idempotency_key=uuid4().hex, request_fingerprint="second")


def test_query_snapshot_survives_engine_restart(pg_url, monkeypatch):
    from app.db.engine import get_engine
    from app.tools.persist import record_to_dict
    from app.tools.query_store import load_query_snapshot, save_query_snapshot
    from fixtures.llm_units_snapshot import llm_units_envelope, llm_units_record

    monkeypatch.setenv("AI2_DATABASE_URL", pg_url)
    record, envelope = llm_units_record(), llm_units_envelope()
    record.dossier_id = uuid4().hex
    save_query_snapshot(record, envelope)
    get_engine(pg_url).dispose()
    loaded = load_query_snapshot(record.dossier_id, tenant_id=record.tenant_id)
    assert record_to_dict(loaded[0]) == record_to_dict(record)
    assert loaded[1] == envelope
    assert load_query_snapshot(record.dossier_id, tenant_id="wrong-tenant") is None


def test_vector_backend_uses_extension_or_degrades(pg_url, monkeypatch):
    from sqlalchemy import text
    from test_st067_bounded_jobs import FakeEmbeddings

    from app.db.engine import get_engine
    from app.reasoning.vector_recall import PostgresVectorIndex, VectorRecallService
    from fixtures import mock_record

    monkeypatch.setenv("AI2_DATABASE_URL", pg_url)
    index = PostgresVectorIndex(pg_url)
    with get_engine(pg_url).connect() as cx:
        available = bool(cx.execute(text("SELECT 1 FROM pg_extension WHERE extname='vector'")).scalar())
    fake = FakeEmbeddings()
    result = VectorRecallService(embedding_client=fake, index=index, enabled=True).recall(mock_record(), "Thanh toán?")
    if available:
        assert result.status == "READY"
        assert result.candidates and result.candidates[0].citation.node_id
    else:
        assert result.trace["reason_code"] == "VECTOR_EXTENSION_UNAVAILABLE"
        assert fake.embedded_texts == 0


def test_durable_transactions_leases_audit_and_outbox(pg_url, monkeypatch, tmp_path):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from app.db.engine import get_engine
    from app.tools.durable import DurableRunStore, LeaseFencedError

    monkeypatch.setenv("AI2_DATABASE_URL", pg_url)
    store = DurableRunStore(tmp_path / "must-not-exist.sqlite")
    run_id = uuid4().hex
    store.create_run(run_id=run_id, tenant_id="pg-test", generation_id="gen", state={"value": 1})
    token = store.claim_lease(run_id, owner_id="worker")
    with pytest.raises(LeaseFencedError):
        store.save_snapshot(run_id, state={}, sequence=1, worker_token="stale")
    store.append_event(run_id=run_id, event_type="step", sequence=1, state_version=1,
                       generation_id="gen", correlation_id="corr", payload={"value": 2}, worker_token=token)
    store.append_audit(run_id, actor_id="actor", action="review", details={})
    with pytest.raises(DBAPIError), get_engine(pg_url).begin() as cx:
        cx.execute(text("UPDATE ai2.durable_audit SET action='tampered' WHERE run_id=:run_id"), {"run_id": run_id})
    assert store.replay(run_id)["events"][0]["sequence"] == 1
    delivered = []
    assert store.publish_outbox(lambda event: delivered.append(event)) >= 1
    assert any(item["run_id"] == run_id for item in delivered)
    assert not (tmp_path / "must-not-exist.sqlite").exists()


def test_sessions_store_blobs_in_postgres(pg_url, monkeypatch, tmp_path):
    from app.tools import persist
    from app.tools.store import InMemorySnapshotStore
    from fixtures.llm_units_snapshot import llm_units_envelope, llm_units_record

    monkeypatch.setenv("AI2_DATABASE_URL", pg_url)
    monkeypatch.setattr(persist, "DATA", tmp_path / "no-local-data")
    sid = uuid4().hex
    payload = dict(record=llm_units_record(), envelope=llm_units_envelope(), filename="test.pdf",
                   source="synthetic", step="extract", blobs={"test.pdf": b"synthetic-bytes"})
    persist.save_session(sid, payload, InMemorySnapshotStore())
    loaded = persist.load_session(sid, InMemorySnapshotStore())
    assert loaded["blobs"] == payload["blobs"]
    assert not persist.DATA.exists()


def test_required_database_fails_closed_without_url(monkeypatch):
    from app.db.engine import validate_database_config

    monkeypatch.delenv("AI2_DATABASE_URL", raising=False)
    monkeypatch.setenv("AI2_REQUIRE_DATABASE", "true")
    with pytest.raises(RuntimeError, match="AI2_DATABASE_URL"):
        validate_database_config()


def test_api_job_poll_and_query_survive_postgres_reopen(pg_url, monkeypatch):
    from fastapi.testclient import TestClient
    from test_a1_query_digest import _body_only_request, _poll, _sha256

    from app.api import main
    from app.db.engine import get_engine
    from app.security.service_envelope import build_service_envelope
    from app.tools.jobs import PostgresJobStore, job_store_from_env
    from app.tools.store import InMemorySnapshotStore

    monkeypatch.setenv("AI2_DATABASE_URL", pg_url)
    monkeypatch.setenv("AI2_REQUIRE_DATABASE", "true")
    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "test-secret")
    monkeypatch.setenv("AI2_QUERY_EGRESS_ALLOWED", "false")
    monkeypatch.setenv("AI2_QUERY_USE_VECTOR", "false")
    monkeypatch.setenv("AI2_QUERY_USE_LLM", "false")
    monkeypatch.setattr(main, "JOB_STORE", job_store_from_env())
    monkeypatch.setattr(main, "STORE", InMemorySnapshotStore())
    monkeypatch.setattr(main, "WIRE_JOBS", {})
    assert isinstance(main.JOB_STORE, PostgresJobStore)
    payload = _body_only_request()
    payload["snapshots"][0]["pages"][0]["lines"] = [{
        "line_id": "pg:value", "raw_text": "Giá trị hợp đồng: 100.000.000 VND.",
        "bbox": [0.1, 0.1, 0.9, 0.2], "bbox_source": "derived", "geometry_status": "derived", "words": [],
    }]
    payload["snapshot_identities"][0]["snapshot_digest"] = _sha256(payload["snapshots"][0])
    payload.pop("service_envelope")
    payload["service_envelope"] = build_service_envelope(
        payload, secret="test-secret", tenant_id="tenant_a", dossier_id=payload["dossier_id"], actor_id="backend",
    )
    with TestClient(main.app) as client:
        accepted = client.post("/jobs/idp", json=payload)
        assert accepted.status_code == 202, accepted.text
        job_id = accepted.json()["job_id"]
        wire = _poll(client, job_id, payload["dossier_id"])
        assert wire["status"] == "SUCCEEDED", wire["errors"]

        def ask():
            query = dict(query="Giá trị hợp đồng là bao nhiêu?", dossier_id=payload["dossier_id"],
                         snapshot_digest=wire["query_snapshot_digest"], snapshot_version="ai1.snapshot.v1")
            query["service_envelope"] = build_service_envelope(
                query, secret="test-secret", tenant_id="tenant_a", dossier_id=payload["dossier_id"],
                actor_id="backend", scopes=["ai2.query"],
            )
            response = client.post("/query", json=query)
            assert response.status_code == 200, response.text
            return response.json()

        before = ask()
        assert before["citations"]
        get_engine(pg_url).dispose()
        main.JOB_STORE = PostgresJobStore(pg_url)
        main.STORE = InMemorySnapshotStore()
        main.WIRE_JOBS.clear()
        assert _poll(client, job_id, payload["dossier_id"])["status"] == "SUCCEEDED"
        after = ask()
        for field in ("answer", "state", "citations", "review_state"):
            assert after.get(field) == before.get(field)


def test_durable_concurrent_lease_and_checkpoint_roundtrip(pg_url, monkeypatch, tmp_path):
    from app.tools.durable import DurableRunStore

    monkeypatch.setenv("AI2_DATABASE_URL", pg_url)
    store = DurableRunStore(tmp_path / "unused.sqlite")
    run_id = uuid4().hex
    store.create_run(run_id=run_id, tenant_id="pg-test", generation_id="gen", state={})
    with ThreadPoolExecutor(max_workers=4) as pool:
        tokens = list(pool.map(lambda i: store.claim_lease(run_id, owner_id=f"worker-{i}"), range(4)))
    assert sum(token is not None for token in tokens) == 1
    token = next(token for token in tokens if token)
    store.save_checkpoint(run_id, checkpoint_id="first", state={"n": 1}, sequence=1, worker_token=token)
    store.save_snapshot(run_id, state={"n": 1}, sequence=1, worker_token=token)
    reopened = DurableRunStore(tmp_path / "unused.sqlite")
    restored = reopened.get_run(run_id, tenant_id="pg-test")
    assert restored["snapshot"] == {"n": 1}
    assert restored["checkpoint"]["state"] == {"n": 1}


def test_pending_outbox_filter_never_returns_another_run(pg_url, monkeypatch, tmp_path):
    from app.tools.durable import DurableRunStore

    monkeypatch.setenv("AI2_DATABASE_URL", pg_url)
    store = DurableRunStore(tmp_path / "unused.sqlite")
    first, second = uuid4().hex, uuid4().hex
    for run_id in (first, second):
        store.create_run(run_id=run_id, tenant_id="pg-test", generation_id="gen", state={})
        store.append_event(run_id=run_id, event_type="step", sequence=1, state_version=1,
                           generation_id="gen", correlation_id="corr", payload={})
    assert {event["run_id"] for event in store.pending_outbox(first)} == {first}


@pytest.fixture
def ai2_role_database(pg_url):
    """A fresh database where AI2 runs as a non-superuser owner of schema ``ai2``.

    Mirrors the Backend #52 deployment: superuser owns the database and the
    ``vector`` extension; the AI2 role owns only schema ``ai2`` and resolves
    ``vector`` through ``search_path = ai2, public``. Skips without pgvector.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    admin_url = make_url(pg_url).set(drivername="postgresql+psycopg")
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as cx:
        if not cx.execute(text("SELECT 1 FROM pg_available_extensions WHERE name='vector'")).scalar():
            admin.dispose()
            pytest.skip("pgvector image required (vector extension not installable)")
    suffix = uuid4().hex[:10]
    database, role, password = f"ai2_vec_{suffix}", f"ai2_role_{suffix}", "ai2-test-password"
    with admin.connect() as cx:
        cx.execute(text(f'CREATE DATABASE "{database}"'))
        cx.execute(text(f"CREATE ROLE \"{role}\" LOGIN NOSUPERUSER PASSWORD '{password}'"))
    db_admin = create_engine(admin_url.set(database=database), isolation_level="AUTOCOMMIT")
    with db_admin.connect() as cx:
        cx.execute(text(f'CREATE SCHEMA ai2 AUTHORIZATION "{role}"'))
        cx.execute(text(f'ALTER ROLE "{role}" IN DATABASE "{database}" SET search_path = ai2, public'))
    role_url = admin_url.set(database=database, username=role, password=password)
    try:
        yield db_admin, role_url.render_as_string(hide_password=False)
    finally:
        from app.db.engine import get_engine

        get_engine(role_url.render_as_string(hide_password=False)).dispose()
        db_admin.dispose()
        with admin.connect() as cx:
            cx.execute(text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
            cx.execute(text(f'DROP ROLE IF EXISTS "{role}"'))
        admin.dispose()


def _public_tables(db_admin) -> set[str]:
    from sqlalchemy import text

    with db_admin.connect() as cx:
        return set(cx.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'")).scalars())


def _ai2_state(db_admin) -> tuple[bool, str, str]:
    """(embedding column present, ai2.alembic_version, script head)."""
    from pathlib import Path

    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import text

    import app.db.migrate as migrate_module

    with db_admin.connect() as cx:
        column = cx.execute(text("""SELECT 1 FROM information_schema.columns WHERE table_schema='ai2'
            AND table_name='vector_segments' AND column_name='embedding'""")).scalar()
        version = cx.execute(text("SELECT version_num FROM ai2.alembic_version")).scalar()
    config = Config()
    config.set_main_option("script_location", str(Path(migrate_module.__file__).parent / "migrations"))
    return bool(column), version, ScriptDirectory.from_config(config).get_current_head()


def test_vector_column_appears_when_extension_arrives_after_first_boot(ai2_role_database):
    """I2: 0002 is one-shot; a later boot must still add the embedding column."""
    from sqlalchemy import text

    from app.db.engine import get_engine
    from app.db.migrate import migrate
    from app.reasoning.vector_recall import PostgresVectorIndex

    db_admin, role_url = ai2_role_database
    engine = get_engine(role_url)
    migrate(engine)  # first boot: extension absent, role cannot create it
    column, version, head = _ai2_state(db_admin)
    assert (column, version) == (False, head)

    with db_admin.connect() as cx:  # DBA installs the extension later (#52)
        cx.execute(text("CREATE EXTENSION vector SCHEMA public"))
    migrate(engine)  # reboot

    column, version, head = _ai2_state(db_admin)
    assert (column, version) == (True, head)
    assert PostgresVectorIndex(role_url).available is True


def test_non_superuser_ai2_role_migrates_with_public_vector_extension(ai2_role_database):
    """#52 layout: vector in public, AI2 role without CREATE on the database."""
    from sqlalchemy import text

    from app.db.engine import get_engine
    from app.db.migrate import migrate
    from app.reasoning.vector_recall import PostgresVectorIndex

    db_admin, role_url = ai2_role_database
    with db_admin.connect() as cx:
        cx.execute(text("CREATE EXTENSION vector SCHEMA public"))
    public_before = _public_tables(db_admin)

    migrate(get_engine(role_url))
    migrate(get_engine(role_url))

    column, version, head = _ai2_state(db_admin)
    assert column is True
    assert version == head
    assert _public_tables(db_admin) == public_before
    assert PostgresVectorIndex(role_url).available is True


def test_vector_in_unusable_schema_degrades_instead_of_failing_boot(ai2_role_database):
    """Vector installed later in a schema the AI2 role cannot use must not crash-loop boot."""
    from sqlalchemy import text

    from app.db.engine import get_engine
    from app.db.migrate import migrate
    from app.reasoning.vector_recall import PostgresVectorIndex

    db_admin, role_url = ai2_role_database
    migrate(get_engine(role_url))
    with db_admin.connect() as cx:
        cx.execute(text("CREATE SCHEMA ext"))
        cx.execute(text("CREATE EXTENSION vector SCHEMA ext"))  # no GRANT USAGE to the AI2 role

    migrate(get_engine(role_url))

    column, version, head = _ai2_state(db_admin)
    assert column is False
    assert version == head
    assert PostgresVectorIndex(role_url).available is False


def test_postgres_sweep_respects_queued_hold_lease(pg_url, monkeypatch):
    """I3 on Postgres: a held QUEUED job survives any replica's sweep until its hold lapses."""
    from app.tools.jobs import PostgresJobStore

    store = PostgresJobStore(pg_url)
    now = [10_000]
    monkeypatch.setattr(store, "_now_ms", lambda: now[0])
    dossier = uuid4().hex

    def queued(hint: str) -> str:
        job, created = store.create_or_get(
            tenant_id="pg-i3", dossier_id=dossier, request_id=hint, idempotency_key=f"{dossier}:{hint}",
            attempt=1, request={}, wire={"status": "QUEUED", "errors": []},
        )
        assert created
        return job["job_id"]

    held, orphan = queued("held"), queued("orphan")
    now[0] += 120_000
    store.hold_queued([held], lease_ms=60_000)

    assert store.sweep_stale({"errors": []}) == [orphan]
    assert store.get(held)["status"] == "QUEUED"
    now[0] += 120_000
    assert store.sweep_stale({"errors": []}) == [held]


@pytest.mark.parametrize(("database_url", "expected"), [
    ("postgresql://ai2:unused@127.0.0.1:1/unused", []),
    (None, ["hydrate"]),
])
def test_startup_hydrates_jobs_only_without_postgres_read_model(monkeypatch, database_url, expected):
    """I4: /query reads ai2.dossier_query_snapshots in PG mode; replaying every job is waste."""
    from fastapi.testclient import TestClient

    from app.api import main

    if database_url:
        monkeypatch.setenv("AI2_DATABASE_URL", database_url)
    else:
        monkeypatch.delenv("AI2_DATABASE_URL", raising=False)
    monkeypatch.delenv("AI2_REQUIRE_DATABASE", raising=False)
    monkeypatch.setattr(main, "ensure_database", lambda _engine: None)
    monkeypatch.setattr(main, "_sweep_stale_jobs", lambda *_args, **_kwargs: [])
    calls: list[str] = []
    monkeypatch.setattr(main, "_hydrate_store_from_jobs", lambda: calls.append("hydrate") or 0)

    with TestClient(main.app):
        pass

    assert calls == expected


def test_job_indexes_back_sweep_and_latest_success_queries(pg_url):
    """I5: sweep (status/lease) and complete_with_snapshot's latest-success lookup are indexed."""
    from sqlalchemy import inspect, text

    from app.db.engine import get_engine
    from app.db.migrate import migrate

    engine = get_engine(pg_url)
    with engine.begin() as cx:
        had_public_version = cx.execute(text("SELECT to_regclass('public.alembic_version')")).scalar() is not None
        if not had_public_version:  # a Backend-owned alembic table sharing the database
            cx.execute(text("CREATE TABLE public.alembic_version (version_num varchar(32) PRIMARY KEY)"))
            cx.execute(text("INSERT INTO public.alembic_version VALUES ('be_sentinel')"))
        public_before = cx.execute(text("SELECT version_num FROM public.alembic_version ORDER BY 1")).scalars().all()
    try:
        migrate(engine)
        migrate(engine)
        indexes = {index["name"]: index for index in inspect(engine).get_indexes("jobs", schema="ai2")}
        with engine.connect() as cx:
            version = cx.execute(text("SELECT version_num FROM ai2.alembic_version")).scalar()
            public_after = cx.execute(text("SELECT version_num FROM public.alembic_version ORDER BY 1")).scalars().all()
            plans = {name: cx.execute(text("SELECT indexdef FROM pg_indexes WHERE schemaname='ai2' AND indexname=:n"),
                                      {"n": name}).scalar() for name in indexes}
    finally:
        if not had_public_version:
            with engine.begin() as cx:
                cx.execute(text("DROP TABLE public.alembic_version"))

    assert version == "0004_ai2_job_indexes"
    assert public_after == public_before
    sweep = indexes["idx_ai2_jobs_active_lease"]
    assert sweep["column_names"] == ["status", "lease_until_ms", "updated_ms"]
    assert "WHERE (status = ANY" in plans["idx_ai2_jobs_active_lease"]
    latest = indexes["idx_ai2_jobs_owner_latest"]
    assert latest["column_names"] == ["tenant_id", "dossier_id", "status", "created_ms", "job_id"]
    assert "created_ms DESC, job_id DESC" in plans["idx_ai2_jobs_owner_latest"]
