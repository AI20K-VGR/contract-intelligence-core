"""AI2 must not grow with every job it runs (prod: 142 MiB → 1.3 GiB in 20 h)."""

from __future__ import annotations

import threading
import time
from collections import deque

import pytest

from app.tools.bounded import BoundedDict, env_capacity
from app.tools.jobs import SQLiteJobStore
from app.tools.store import InMemorySnapshotStore
from fixtures import mock_record


def test_bounded_dict_drops_the_oldest_entries():
    cache = BoundedDict(2)
    cache["a"] = 1
    cache["b"] = 2
    cache["c"] = 3
    assert list(cache) == ["b", "c"]
    cache["b"] = 20  # a rewrite is the most recent entry
    cache["d"] = 4
    assert list(cache) == ["b", "d"]


def test_bounded_dict_touch_makes_it_an_lru():
    cache = BoundedDict(2)
    cache["a"] = 1
    cache["b"] = 2
    cache.touch("a")
    cache["c"] = 3
    assert list(cache) == ["a", "c"]


def test_unbounded_dict_keeps_everything():
    cache = BoundedDict(None)
    for i in range(1000):
        cache[i] = i
    assert len(cache) == 1000


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("", 8), ("3", 3), ("0", None), ("-1", 8), ("many", 8)],
)
def test_env_capacity(monkeypatch, raw, expected):
    monkeypatch.setenv("AI2_TEST_CAPACITY", raw)
    assert env_capacity("AI2_TEST_CAPACITY", 8) == expected


def test_snapshot_store_keeps_only_the_most_recently_used_records():
    store = InMemorySnapshotStore(max_entries=2)
    records = []
    for name in ("one", "two", "three"):
        record = mock_record()
        record.dossier_id = name
        records.append(record)
    store.put(records[0])
    store.put(records[1])
    assert store.get(records[0].tenant_id, "one") is records[0]  # now most recent
    store.put(records[2])
    assert store.get(records[1].tenant_id, "two") is None
    assert store.get(records[0].tenant_id, "one") is records[0]
    assert store.get(records[2].tenant_id, "three") is records[2]


def test_snapshot_store_without_a_cap_is_unbounded():
    store = InMemorySnapshotStore()
    for i in range(50):
        record = mock_record()
        record.dossier_id = f"d{i}"
        store.put(record)
    assert len(store._dossiers) == 50


def _wire_job(store, payload, suffix):
    job, _ = store.create_or_get(
        tenant_id="tenant_a",
        dossier_id=payload["dossier_id"],
        request_id=f"{payload['request_id']}-{suffix}",
        idempotency_key=f"{payload['idempotency_key']}-{suffix}",
        attempt=1,
        request=payload,
        wire={"status": "QUEUED", "result": None, "errors": []},
    )
    return job["job_id"]


@pytest.fixture
def wire_env(monkeypatch, tmp_path):
    from test_a1_query_digest import _body_only_request

    from app.api import main
    from app.tools import query_store

    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "test-secret")
    monkeypatch.setenv("AI2_PROCESSING_EGRESS_ALLOWED", "false")
    store = SQLiteJobStore(tmp_path / "memory-bounds.sqlite")
    monkeypatch.setattr(main, "JOB_STORE", store)
    monkeypatch.setattr(main, "STORE", InMemorySnapshotStore(max_entries=4))
    monkeypatch.setattr(main, "WIRE_JOBS", BoundedDict(256))
    monkeypatch.setattr(main, "JOBS", BoundedDict(8))
    monkeypatch.setattr(query_store, "save_query_snapshot", lambda *_args: None)
    return main, store, _body_only_request()


def test_a_finished_wire_job_leaves_no_result_in_memory(wire_env):
    main, store, payload = wire_env
    job_id = _wire_job(store, payload, "done")

    main._run_wire_job(job_id, payload)

    assert store.get(job_id)["status"] == "SUCCEEDED"
    assert job_id not in main.WIRE_JOBS  # JOB_STORE holds the result
    assert job_id not in main.JOBS


def test_with_postgres_a_finished_job_keeps_no_dossier_record(wire_env, monkeypatch):
    main, store, payload = wire_env
    stale = mock_record()
    stale.tenant_id, stale.dossier_id = "tenant_a", payload["dossier_id"]
    main.STORE.put(stale)
    monkeypatch.setattr(main, "database_url", lambda: "postgresql+psycopg://ai2@db/ci")
    job_id = _wire_job(store, payload, "pg")

    main._run_wire_job(job_id, payload)

    assert store.get(job_id)["status"] == "SUCCEEDED"
    # /query reloads it from ai2.dossier_query_snapshots; no copy is pinned here.
    assert main.STORE.get("tenant_a", payload["dossier_id"]) is None


def test_polling_a_finished_job_does_not_cache_its_result(wire_env):
    from fastapi.testclient import TestClient

    from app.security.service_envelope import build_service_envelope

    main, store, payload = wire_env
    job_id = _wire_job(store, payload, "poll")
    main._run_wire_job(job_id, payload)
    request = {"operation": "get_job", "job_id": job_id, "dossier_id": payload["dossier_id"]}
    envelope = build_service_envelope(
        request, secret="test-secret", tenant_id="tenant_a",
        dossier_id=payload["dossier_id"], actor_id="backend",
    )
    import json

    response = TestClient(main.app).get(
        f"/jobs/{job_id}", headers={"X-AI2-Service-Envelope": json.dumps(envelope)}
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "SUCCEEDED"
    assert job_id not in main.WIRE_JOBS


def test_jobs_run_one_at_a_time_and_the_next_one_waits(wire_env, monkeypatch):
    main, store, payload = wire_env
    monkeypatch.setattr(main, "_JOB_SLOTS", threading.BoundedSemaphore(1))
    running = 0
    peak = 0
    lock = threading.Lock()
    original_run = main.run_idp

    def slow_run(*args, **kwargs):
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        time.sleep(0.3)
        with lock:
            running -= 1
        return original_run(*args, **kwargs)

    monkeypatch.setattr(main, "run_idp", slow_run)
    first = _wire_job(store, payload, "first")
    second = _wire_job(store, payload, "second")
    threads = [threading.Thread(target=main._run_wire_job, args=(job, payload)) for job in (first, second)]
    for thread in threads:
        thread.start()
    time.sleep(0.1)
    # One runs; the other has not been claimed and stays QUEUED.
    assert sorted(store.get(job)["status"] for job in (first, second)) == ["QUEUED", "RUNNING"]
    for thread in threads:
        thread.join(timeout=30)
    assert peak == 1
    assert {store.get(job)["status"] for job in (first, second)} == {"SUCCEEDED"}


def test_a_failure_after_cache_eviction_keeps_the_stored_wire_fields(wire_env, monkeypatch):
    main, store, payload = wire_env
    job_id = _wire_job(store, payload, "boom")

    def explode(*_args, **_kwargs):
        main.WIRE_JOBS.clear()  # evicted while it ran
        raise RuntimeError("boom")

    monkeypatch.setattr(main, "run_idp", explode)
    main._run_wire_job(job_id, payload)
    stored = store.get(job_id)
    assert stored["status"] == "FAILED"
    assert stored["wire"]["errors"][0]["code"] == "AI2_WORKER_FAILED"
    assert "result" in stored["wire"]


def test_readiness_reuses_one_client_and_one_recent_probe(monkeypatch):
    from app.api import main

    monkeypatch.setenv("AI2_LLM_API_KEY", "sk-test")
    monkeypatch.setenv("AI2_READYZ_PROBE_TTL_SECONDS", "60")
    calls = []

    def probe(client):
        calls.append(client)
        return "ready"

    monkeypatch.setattr(main, "llm_status", probe)
    monkeypatch.setattr(main, "_PROBE_RESULT", None)
    monkeypatch.setattr(main, "_PROBE_CLIENT", None)
    for _ in range(5):
        main._capability_snapshot()
    assert len(calls) == 1

    monkeypatch.setenv("AI2_LLM_API_KEY", "sk-rotated")  # new settings: new client, new probe
    main._capability_snapshot()
    assert len(calls) == 2
    assert calls[0] is not calls[1]


def test_a_failed_probe_is_retried_after_a_short_while(monkeypatch):
    from app.api import main

    monkeypatch.setenv("AI2_LLM_API_KEY", "sk-test")
    monkeypatch.setenv("AI2_READYZ_PROBE_TTL_SECONDS", "60")
    calls = []

    def probe(client):
        calls.append(client)
        return "unreachable"

    clock = [1000.0]
    monkeypatch.setattr(main.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(main, "llm_status", probe)
    monkeypatch.setattr(main, "_PROBE_RESULT", None)
    main._capability_snapshot()
    main._capability_snapshot()
    assert len(calls) == 1
    clock[0] += 11
    main._capability_snapshot()
    assert len(calls) == 2


def test_probe_cache_can_be_turned_off(monkeypatch):
    from app.api import main

    monkeypatch.setenv("AI2_READYZ_PROBE_TTL_SECONDS", "0")
    calls = []
    monkeypatch.setattr(main, "llm_status", lambda client: calls.append(client) or "ready")
    monkeypatch.setattr(main, "_PROBE_RESULT", None)
    main._capability_snapshot()
    main._capability_snapshot()
    assert len(calls) == 2


def test_llm_trace_history_is_bounded():
    from app.llm.client import NineRouterClient

    assert isinstance(NineRouterClient.all_traces, deque)
    assert NineRouterClient.all_traces.maxlen == 1000


def test_release_memory_never_raises():
    from app.ops.memory import release_memory

    assert release_memory() in {True, False}
