"""Issue #131: actual PostgreSQL erasure, shared ownership and concurrent writers."""

from __future__ import annotations

import copy
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_contract_graph_postgres_store import fresh_url as fresh_url

from app.db.engine import ensure_database, get_engine
from app.security.service_envelope import build_service_envelope
from app.tools.dossier_deletion import DossierDeletedError, is_dossier_deleted, purge_dossier
from app.tools.jobs import PostgresJobStore
from app.tools.persist import save_session
from app.tools.query_store import load_query_snapshot, save_query_snapshot
from app.tools.store import InMemorySnapshotStore


@pytest.fixture
def db(fresh_url, monkeypatch):
    monkeypatch.setenv("AI2_DATABASE_URL", fresh_url)
    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "purge-test")
    get_engine.cache_clear()
    engine = get_engine()
    ensure_database(engine)
    yield engine


def record(dossier=None, tenant="purge-tenant", digest="a" * 64):
    from fixtures.llm_units_snapshot import llm_units_envelope, llm_units_record

    rec, env = llm_units_record(), llm_units_envelope()
    rec.tenant_id = env.auth.tenant_id = tenant
    rec.dossier_id = env.auth.dossier_id = dossier or uuid4().hex
    rec.pins.source_snapshot_digest = env.pins.source_snapshot_digest = digest
    return rec, env


def session(rec, env):
    return dict(record=rec, envelope=env, filename="contract.pdf", source="test",
                step="extract", blobs={"contract.pdf": b"confidential"})


def vector(engine, digest, *, tenant=None, dossier=None):
    with engine.begin() as cx:
        if tenant:
            cx.execute(text("SELECT set_config('ai2.vector_tenant',:t,true),"
                            "set_config('ai2.vector_dossier',:d,true)"), {"t": tenant, "d": dossier})
        cx.execute(text("""INSERT INTO ai2.vector_segments
            (segment_id,snapshot_digest,node_id,page_revision_id,char_start,char_end,text_digest,
             text,embedding_version,embedding_model,dimensions,vector_json)
            VALUES (:id,:digest,'n','p',0,5,'digest','secret','v1','test',2,'[1,0]')"""),
            {"id": uuid4().hex, "digest": digest})


def count(engine, table):
    with engine.connect() as cx:
        return cx.execute(text(f"SELECT count(*) FROM ai2.{table}")).scalar_one()


def test_purge_all_stores_and_retry(db, tmp_path):
    from app.tools.durable import DurableRunStore

    rec, env = record()
    store = PostgresJobStore()
    job, _ = store.create_or_get(tenant_id=rec.tenant_id, dossier_id=rec.dossier_id,
        request_id="req", idempotency_key="idem", attempt=1, request={}, wire={})
    token = store.claim(job["job_id"], tenant_id=rec.tenant_id, dossier_id=rec.dossier_id)
    assert store.complete_with_snapshot(job["job_id"], tenant_id=rec.tenant_id,
        dossier_id=rec.dossier_id, worker_token=token, status="SUCCEEDED", wire={}, record=rec, envelope=env)
    save_session("session-test", session(rec, env), InMemorySnapshotStore())
    path = tmp_path / "blobs" / "session-test"
    path.mkdir(parents=True)
    (path / "legacy.pdf").write_bytes(b"secret")
    durable = DurableRunStore(tmp_path / "unused.sqlite")
    durable.create_run(run_id="run", tenant_id=rec.tenant_id, generation_id="gen",
                       state={"dossier_id": rec.dossier_id, "text": "secret"})
    durable.save_checkpoint("run", checkpoint_id="cp", sequence=0, state={"text": "secret"})
    durable.append_event(run_id="run", event_type="step", sequence=1, state_version=1,
                         generation_id="gen", correlation_id="corr", payload={"text": "secret"})
    durable.append_audit("run", actor_id="test", action="test", details={"text": "secret"})
    vector(db, rec.pins.source_snapshot_digest)
    result = purge_dossier(rec.tenant_id, rec.dossier_id, data_dir=tmp_path)
    for table in ("jobs", "dossier_query_snapshots", "sessions", "session_blobs", "durable_runs",
                  "durable_checkpoints", "durable_events", "durable_outbox", "durable_audit",
                  "vector_segments", "contract_graph_write_receipts"):
        assert result["deleted"][table] >= 1, table
        assert count(db, table) == 0, table
    assert not path.exists()
    assert not (tmp_path / "unused.sqlite").exists()
    assert is_dossier_deleted(rec.tenant_id, rec.dossier_id)
    again = purge_dossier(rec.tenant_id, rec.dossier_id, data_dir=tmp_path)
    assert not any(again["deleted"].values())
    assert again["evidence"] == result["evidence"]


@pytest.mark.parametrize("other_tenant", ["purge-tenant", "another-tenant"])
def test_shared_digest_and_historical_digest(db, tmp_path, other_tenant):
    rec, env = record()
    other, other_env = record(tenant=other_tenant)
    save_query_snapshot(rec, env)
    save_query_snapshot(other, other_env)
    vector(db, rec.pins.source_snapshot_digest)
    rec.pins.source_snapshot_digest = env.pins.source_snapshot_digest = "b" * 64
    save_query_snapshot(rec, env)
    vector(db, "b" * 64)
    assert purge_dossier(rec.tenant_id, rec.dossier_id, data_dir=tmp_path)["deleted"]["vector_segments"] == 1
    assert count(db, "vector_segments") == 1
    assert load_query_snapshot(other.dossier_id, tenant_id=other.tenant_id)
    # A late writer from the deleted owner cannot write even the shared digest.
    with pytest.raises(DBAPIError, match="AI2_DOSSIER_DELETED"):
        vector(db, "a" * 64, tenant=rec.tenant_id, dossier=rec.dossier_id)
    assert purge_dossier(other.tenant_id, other.dossier_id, data_dir=tmp_path)["deleted"]["vector_segments"] == 1
    with pytest.raises(DBAPIError, match="AI2_DOSSIER_DELETED"):
        vector(db, "a" * 64)


def test_late_writers_and_tenant_isolation(db, tmp_path):
    from app.tools.durable import DurableRunStore

    rec, env = record()
    save_query_snapshot(rec, env)
    purge_dossier("wrong-tenant", rec.dossier_id, data_dir=tmp_path)
    assert load_query_snapshot(rec.dossier_id, tenant_id=rec.tenant_id)
    purge_dossier(rec.tenant_id, rec.dossier_id, data_dir=tmp_path)
    with pytest.raises(DBAPIError, match="AI2_DOSSIER_DELETED"):
        save_query_snapshot(rec, env)
    with pytest.raises(DBAPIError, match="AI2_DOSSIER_DELETED"):
        save_session("late", session(rec, env), InMemorySnapshotStore())
    with pytest.raises(DossierDeletedError):
        PostgresJobStore().create_or_get(tenant_id=rec.tenant_id, dossier_id=rec.dossier_id,
            request_id="late", idempotency_key="late", attempt=1, request={}, wire={})
    with pytest.raises(DBAPIError, match="AI2_DOSSIER_DELETED"):
        DurableRunStore(tmp_path / "unused").create_run(run_id="late", tenant_id=rec.tenant_id,
            generation_id="gen", state={"record": {"dossier_id": rec.dossier_id}})
    with pytest.raises(DBAPIError, match="AI2_RESOURCE_PARENT_MISSING"), db.begin() as cx:
        cx.execute(text("INSERT INTO ai2.session_blobs VALUES ('late','file',:data)"), {"data": b"secret"})


def test_writer_waiting_on_purge_cannot_resurrect(db, tmp_path):
    rec, env = record()
    save_query_snapshot(rec, env)
    entered = threading.Event()

    def late_write():
        entered.set()
        with pytest.raises(DBAPIError, match="AI2_DOSSIER_DELETED"):
            save_query_snapshot(rec, env)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with db.begin() as cx:
            cx.execute(text("SELECT pg_advisory_xact_lock(131, 2)"))
            future = pool.submit(late_write)
            assert entered.wait(5)
            cx.execute(text("""INSERT INTO ai2.dossier_tombstones VALUES
                (:t,:d,0,'pending','{}')"""), {"t": rec.tenant_id, "d": rec.dossier_id})
            cx.execute(text("DELETE FROM ai2.dossier_query_snapshots"))
        future.result(timeout=10)
    assert count(db, "dossier_query_snapshots") == 0


def test_five_writers_overlap_while_another_writer_is_uncommitted(db):
    rec, env = record()
    # A real INSERT holds the statement/row gate until commit. Five distinct
    # resources must still persist, rather than waiting on a global writer lock.
    with db.begin() as cx, ThreadPoolExecutor(max_workers=5) as pool:
        cx.execute(text("SELECT ai2.register_dossier_resource('jobs', CAST(:row AS jsonb))"),
                   {"row": json.dumps({"tenant_id": rec.tenant_id, "dossier_id": rec.dossier_id,
                                       "job_id": "held-writer", "wire_json": "{}"})})
        futures = []
        for _ in range(5):
            other, other_env = record()
            futures.append(pool.submit(save_query_snapshot, other, other_env))
        for future in futures:
            future.result(timeout=10)
    assert count(db, "dossier_query_snapshots") == 5


def test_purge_waits_for_writer_commit(db, tmp_path):
    import time

    rec, env = record()
    entered = threading.Event()

    def erase():
        entered.set()
        return purge_dossier(rec.tenant_id, rec.dossier_id, data_dir=tmp_path)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with db.begin() as cx:
            cx.execute(text("SELECT ai2.register_dossier_resource('jobs', CAST(:row AS jsonb))"),
                       {"row": json.dumps({"tenant_id": rec.tenant_id, "dossier_id": rec.dossier_id,
                                           "job_id": "held-writer", "wire_json": "{}"})})
            save_query_snapshot(rec, env)
            future = pool.submit(erase)
            assert entered.wait(5)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with db.connect() as observer:
                    waiting = observer.execute(text("""SELECT count(*) FROM pg_locks
                        WHERE locktype='advisory' AND classid=131 AND objid=2 AND NOT granted
                          AND database=(SELECT oid FROM pg_database WHERE datname=current_database())""")).scalar_one()
                if waiting:
                    break
                time.sleep(0.01)
            assert waiting, "Purge must wait for the uncommitted writer gate"
            assert not future.done()
        assert future.result(timeout=10)["deleted"]["dossier_query_snapshots"] == 1
    assert count(db, "dossier_query_snapshots") == 0


def test_concurrent_resource_owners_cannot_cross_dossiers(db):
    first, _ = record()
    other, _ = record(tenant="other-tenant")
    entered = threading.Event()

    def register(cx, rec):
        cx.execute(text("SELECT ai2.register_dossier_resource('jobs', CAST(:row AS jsonb))"),
                   {"row": json.dumps({"tenant_id": rec.tenant_id, "dossier_id": rec.dossier_id,
                                       "job_id": "same-resource", "wire_json": "{}"})})

    def competing():
        entered.set()
        with pytest.raises(DBAPIError, match="AI2_RESOURCE_OWNER_IMMUTABLE"), db.begin() as cx:
            register(cx, other)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with db.begin() as cx:
            register(cx, first)
            future = pool.submit(competing)
            assert entered.wait(5)
        future.result(timeout=10)
    with db.connect() as cx:
        assert cx.execute(text("SELECT DISTINCT tenant_id FROM ai2.dossier_resource_refs")).scalars().all() == [first.tenant_id]


def test_job_progress_does_not_decode_unchanged_wire_but_updates_keep_digest_refs(db):
    rec, _ = record()
    store = PostgresJobStore()
    job, _ = store.create_or_get(tenant_id=rec.tenant_id, dossier_id=rec.dossier_id,
        request_id="large", idempotency_key="large", attempt=1, request={},
        wire={"text": "x" * (6 * 1024 * 1024)})
    with db.begin() as cx:
        # Instrument the registration boundary, not timing-sensitive wall time.
        cx.execute(text("""ALTER FUNCTION ai2.register_dossier_resource(text,jsonb)
            RENAME TO original_register_dossier_resource;
            CREATE FUNCTION ai2.register_dossier_resource(kind text, row_data jsonb)
            RETURNS void LANGUAGE plpgsql AS $$ BEGIN
                IF kind='jobs' AND length(row_data->>'wire_json') > 1024 THEN
                    RAISE EXCEPTION 'unchanged wire was parsed again';
                END IF;
                PERFORM ai2.original_register_dossier_resource(kind,row_data);
            END $$;"""))
    assert store.claim(job["job_id"], tenant_id=rec.tenant_id, dossier_id=rec.dossier_id)
    digest = "c" * 64
    with db.begin() as cx:
        cx.execute(text("UPDATE ai2.jobs SET wire_json=:wire WHERE job_id=:job"),
                   {"job": job["job_id"], "wire": json.dumps({"source_snapshot_digest": digest})})
        assert cx.execute(text("SELECT count(*) FROM ai2.dossier_resource_refs WHERE snapshot_digest=:digest"),
                          {"digest": digest}).scalar_one() == 1


def test_file_failure_retries_after_db_rows_removed(db, tmp_path, monkeypatch):
    import app.tools.dossier_deletion as deletion

    rec, env = record()
    save_session("retry", session(rec, env), InMemorySnapshotStore())
    folder = tmp_path / "blobs" / "retry"
    folder.mkdir(parents=True)
    (folder / "contract").write_bytes(b"secret")
    remove = deletion.shutil.rmtree
    monkeypatch.setattr(deletion.shutil, "rmtree", lambda *_: (_ for _ in ()).throw(PermissionError()))
    with pytest.raises(PermissionError):
        purge_dossier(rec.tenant_id, rec.dossier_id, data_dir=tmp_path)
    assert count(db, "sessions") == 0
    with db.connect() as cx:
        assert cx.execute(text("SELECT status FROM ai2.dossier_tombstones")).scalar_one() == "pending"
    monkeypatch.setattr(deletion.shutil, "rmtree", remove)
    assert purge_dossier(rec.tenant_id, rec.dossier_id, data_dir=tmp_path)["status"] == "completed"
    assert not folder.exists()


def signed(rec, **updates):
    payload = {"tenant_id": rec.tenant_id, "dossier_id": rec.dossier_id, **updates}
    payload["service_envelope"] = build_service_envelope(payload, secret="purge-test",
        tenant_id=rec.tenant_id, dossier_id=rec.dossier_id, scopes=["ai2.dossier.delete"])
    return payload


def test_api_auth_binding_idempotency_and_stale_session(db, tmp_path, monkeypatch):
    from app.api import dossier_deletion_router as deletion_api
    from app.api import main

    monkeypatch.setattr(deletion_api, "DATA", tmp_path)
    rec, env = record()
    save_query_snapshot(rec, env)
    save_session("cached", session(rec, env), InMemorySnapshotStore())
    monkeypatch.setattr(main, "SESSIONS", {"cached": session(rec, env)})
    client = TestClient(main.app)
    url = f"/api/v1/dossiers/{rec.dossier_id}"
    payload = signed(rec)
    assert client.request("DELETE", url, json={"dossier_id": rec.dossier_id}).status_code == 401
    bad = copy.deepcopy(payload)
    bad["service_envelope"]["signature"] = "0" * 64
    assert client.request("DELETE", url, json=bad).status_code == 401
    assert client.request("DELETE", url + "different", json=payload).status_code == 422
    assert client.request("DELETE", url, json=payload).status_code == 200
    assert client.request("DELETE", url, json=payload).json()["status"] == "completed"
    assert client.get("/api/workspace/cached").status_code == 404
    query = {"dossier_id": rec.dossier_id, "query": "secret?", "tenant_id": rec.tenant_id}
    query["service_envelope"] = build_service_envelope(query, secret="purge-test",
        tenant_id=rec.tenant_id, dossier_id=rec.dossier_id, scopes=["ai2.query"])
    assert client.post("/query", json=query).status_code == 410


def test_append_only_audit_for_other_run_still_enforced(db, tmp_path):
    from app.tools.durable import DurableRunStore

    rec, _ = record()
    store = DurableRunStore(tmp_path / "unused")
    store.create_run(run_id="protected", tenant_id=rec.tenant_id, generation_id="g",
                     state={"dossier_id": rec.dossier_id})
    store.append_audit("protected", actor_id="a", action="a", details={})
    with pytest.raises(DBAPIError, match="append-only"), db.begin() as cx:
        cx.execute(text("DELETE FROM ai2.durable_audit"))


def test_running_job_completion_and_trace_cannot_write_after_purge(db, tmp_path, monkeypatch):
    from test_contract_graph_postgres_store import _finish, _start, _store_and_owner

    from app.tools.processing_trace_store import LeaseFencedTraceWrite, ProcessingTraceStore

    store, rec, env, edges = _store_and_owner(db.url.render_as_string(hide_password=False))
    previous = _start(store, rec, "previous", 100, monkeypatch)
    assert _finish(store, rec, env, *previous, edges=edges)
    job, _ = store.create_or_get(tenant_id=rec.tenant_id, dossier_id=rec.dossier_id,
        request_id="running", idempotency_key="running", attempt=1, request={}, wire={})
    job_id = job["job_id"]
    token = store.claim(job_id, tenant_id=rec.tenant_id, dossier_id=rec.dossier_id, execution_id="execution")
    running = job_id, token
    args = dict(tenant_id=rec.tenant_id, dossier_id=rec.dossier_id, job_id=job_id,
        snapshot_digest=rec.pins.source_snapshot_digest, stage_id="contract_graph_operation",
        status="STARTED", worker_token=token,
        execution_id=store.get(job_id)["current_execution_id"])
    trace = ProcessingTraceStore(store)
    trace.append(**args)
    deleted = purge_dossier(rec.tenant_id, rec.dossier_id, data_dir=tmp_path)["deleted"]
    assert deleted["contract_edges"] == len(edges)
    assert deleted["ai2_processing_trace_events"] == 1
    assert not _finish(store, rec, env, *running, edges=edges)
    with pytest.raises(LeaseFencedTraceWrite):
        trace.append(**args)
    assert count(db, "contract_edges") == count(db, "dossier_query_snapshots") == 0


def test_migration_backfills_existing_structured_ownership(fresh_url, monkeypatch, tmp_path):
    from alembic import command

    from app.db.migrate import _config, migrate
    from app.tools.persist import record_to_dict

    monkeypatch.setenv("AI2_DATABASE_URL", fresh_url)
    engine = get_engine()
    config = _config()
    with engine.begin() as cx:
        cx.execute(text("CREATE SCHEMA ai2"))
        config.attributes["connection"] = cx
        command.upgrade(config, "0008_ai2_processing_trace")
        rec, env = record()
        payload = json.dumps({"record": record_to_dict(rec), "envelope": env.model_dump()})
        cx.execute(text("INSERT INTO ai2.sessions VALUES ('old-session',:payload,0)"), {"payload": payload})
        cx.execute(text("""INSERT INTO ai2.dossier_query_snapshots VALUES (:t,:d,:digest,:payload,0)"""),
            {"t": rec.tenant_id, "d": rec.dossier_id, "digest": rec.pins.source_snapshot_digest, "payload": payload})
        cx.execute(text("""INSERT INTO ai2.durable_runs
            (run_id,tenant_id,generation_id,snapshot_json,snapshot_digest,snapshot_sequence,state_version,created_ms,updated_ms)
            VALUES ('old-run',:t,'gen',:state,'run-state-digest',0,0,0,0)"""),
            {"t": rec.tenant_id, "state": json.dumps({"record": {"dossier_id": rec.dossier_id}, "secret": "text"})})
    migrate(engine)
    result = purge_dossier(rec.tenant_id, rec.dossier_id, data_dir=tmp_path)
    assert result["deleted"]["sessions"] == 1
    assert result["deleted"]["durable_runs"] == 1
    assert result["deleted"]["dossier_query_snapshots"] == 1
    with pytest.raises(RuntimeError, match="Cannot downgrade"):
        from app.db.migrate import downgrade

        downgrade(engine, "0008_ai2_processing_trace")


def test_durable_child_discovers_owner_and_late_child_is_fenced(db, tmp_path):
    from app.tools.durable import DurableRunStore

    rec, _ = record()
    store = DurableRunStore(tmp_path / "unused")
    store.create_run(run_id="child-owned", tenant_id=rec.tenant_id, generation_id="g", state={})
    store.save_checkpoint("child-owned", checkpoint_id="cp", sequence=0,
        state={"dossier_id": rec.dossier_id, "text": "secret"})
    purge_dossier(rec.tenant_id, rec.dossier_id, data_dir=tmp_path)
    assert count(db, "durable_runs") == count(db, "durable_checkpoints") == 0


def test_pending_sweeper_recovers_cleanup(db, tmp_path, monkeypatch):
    from app.tools.dossier_deletion import retry_pending_purges

    rec, env = record()
    save_session("recover", session(rec, env), InMemorySnapshotStore())
    with db.begin() as cx:
        cx.execute(text("INSERT INTO ai2.dossier_tombstones VALUES (:t,:d,0,'pending','{}')"),
                   {"t": rec.tenant_id, "d": rec.dossier_id})
    retry_pending_purges(data_dir=tmp_path)
    assert count(db, "sessions") == 0
    with db.connect() as cx:
        assert cx.execute(text("SELECT status FROM ai2.dossier_tombstones")).scalar_one() == "completed"


def test_kafka_dedupe_cannot_return_deleted_result(db, tmp_path, monkeypatch):
    from app.transport import kafka_idp_worker as worker

    rec, _ = record()
    event_id = uuid4().hex
    monkeypatch.setattr(worker, "_processed", {event_id: {"payload": {"secret": "result"}}})
    purge_dossier(rec.tenant_id, rec.dossier_id, data_dir=tmp_path)
    result = worker._handle_command({"event_id": event_id, "tenant_id": rec.tenant_id,
        "payload": {"dossier_id": rec.dossier_id}})
    assert result["event_type"] == worker.EVENT_FAILED
    assert result["payload"]["result"] is None
    assert result["payload"]["errors"][0]["code"] == "AI2_DOSSIER_DELETED"
    assert event_id not in worker._processed


def test_postgres_vector_adapter_binds_deleted_owner(db, tmp_path):
    from app.reasoning.vector_recall import EvidenceSegment, PostgresVectorIndex

    rec, env = record()
    save_query_snapshot(rec, env)
    segment = EvidenceSegment(segment_id="segment", snapshot_digest=rec.pins.source_snapshot_digest,
        node_id="n", source_file_id=None, source_role=None, page_revision_id="p", char_start=0,
        char_end=5, text="secret", text_digest="digest")
    index = PostgresVectorIndex()
    if not index.available:
        pytest.skip("pgvector extension not installed in this PostgreSQL")
    index.upsert([segment], [[1.0, 0.0]], model="test", dimensions=2,
                 tenant_id=rec.tenant_id, dossier_id=rec.dossier_id)
    assert purge_dossier(rec.tenant_id, rec.dossier_id, data_dir=tmp_path)["deleted"]["vector_segments"] == 1
    with pytest.raises(DBAPIError, match="AI2_DOSSIER_DELETED"):
        index.upsert([segment], [[1.0, 0.0]], model="test", dimensions=2,
                     tenant_id=rec.tenant_id, dossier_id=rec.dossier_id)


def test_cooperative_cancellation_is_not_swallowed_as_extraction_failure():
    from app.pipeline.idp import run_idp
    from app.pipeline.runtime import ProcessingRuntime
    from fixtures import envelope, mock_record

    calls = []

    def cancelled():
        calls.append(1)
        if len(calls) > 1:
            raise DossierDeletedError("AI2_DOSSIER_DELETED")

    with pytest.raises(DossierDeletedError):
        run_idp(mock_record(), envelope(), runtime=ProcessingRuntime(check_cancelled=cancelled))
    assert len(calls) == 2


def test_delete_auth_scope_tenant_and_retryable_failure(db, tmp_path, monkeypatch):
    from app.api import dossier_deletion_router as api
    from app.api import main

    monkeypatch.setattr(api, "DATA", tmp_path)
    rec, env = record()
    save_query_snapshot(rec, env)
    client = TestClient(main.app)
    url = f"/api/v1/dossiers/{rec.dossier_id}"
    payload = signed(rec)
    payload["service_envelope"] = build_service_envelope(payload, secret="purge-test",
        tenant_id=rec.tenant_id, dossier_id=rec.dossier_id, scopes=["ai2.query"])
    assert client.request("DELETE", url, json=payload).status_code == 401
    payload["tenant_id"] = "another-tenant"
    payload["service_envelope"] = build_service_envelope(payload, secret="purge-test",
        tenant_id=rec.tenant_id, dossier_id=rec.dossier_id, scopes=["ai2.dossier.delete"])
    assert client.request("DELETE", url, json=payload).status_code == 403
    assert load_query_snapshot(rec.dossier_id, tenant_id=rec.tenant_id)
    monkeypatch.setattr(api, "purge_dossier", lambda *_args, **_kw: (_ for _ in ()).throw(PermissionError("secret-path")))
    response = client.request("DELETE", url, json=signed(rec))
    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "AI2_PURGE_INCOMPLETE", "retryable": True}}


def test_claimed_outbox_payload_cannot_publish_after_purge(db, tmp_path, monkeypatch):
    from app.tools.durable import DurableRunStore

    rec, _ = record()
    store = DurableRunStore(tmp_path / "unused")
    store.create_run(run_id="outbox-run", tenant_id=rec.tenant_id, generation_id="g",
                     state={"dossier_id": rec.dossier_id})
    store.append_event(run_id="outbox-run", event_type="step", sequence=1, state_version=1,
                       generation_id="g", correlation_id="c", payload={"text": "secret"})
    decode = store._decode_outbox

    def purge_after_claim(row):
        item = decode(row)
        purge_dossier(rec.tenant_id, rec.dossier_id, data_dir=tmp_path)
        return item

    monkeypatch.setattr(store, "_decode_outbox", purge_after_claim)
    emitted = []
    assert store.publish_outbox(emitted.append) == 0
    assert not emitted
