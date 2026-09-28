from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from app.tools.durable import (
    AuditAppendOnlyError,
    DurableRunStore,
    EventDigestConflict,
    EventGapError,
    LeaseFencedError,
    SnapshotCorruptError,
)


NOW = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)


def make_store(tmp_path):
    return DurableRunStore(tmp_path / "runs.sqlite", now=lambda: NOW)


def test_run_snapshot_checkpoint_and_restart_roundtrip(tmp_path):
    store = make_store(tmp_path)
    store.create_run(
        run_id="run-1",
        tenant_id="tenant-a",
        generation_id="gen-1",
        state={"state": "CREATED", "state_version": 0},
    )
    token = store.claim_lease("run-1", owner_id="worker-a", lease_ms=1000)
    store.save_checkpoint(
        "run-1",
        checkpoint_id="cp-1",
        state={"state": "RUNNING", "state_version": 1},
        sequence=1,
        worker_token=token,
    )
    store.save_snapshot(
        "run-1",
        state={"state": "RUNNING", "state_version": 1},
        sequence=1,
        worker_token=token,
    )

    restarted = DurableRunStore(tmp_path / "runs.sqlite", now=lambda: NOW)
    run = restarted.get_run("run-1", tenant_id="tenant-a")
    assert run["snapshot"]["state"] == "RUNNING"
    assert run["checkpoint"]["checkpoint_id"] == "cp-1"
    assert run["checkpoint"]["sequence"] == 1


def test_append_event_is_monotonic_deduplicated_and_transactional(tmp_path):
    store = make_store(tmp_path)
    store.create_run(run_id="run-1", tenant_id="tenant-a", generation_id="gen-1", state={"n": 0})
    first = store.append_event(
        run_id="run-1",
        event_type="RUN_STARTED",
        sequence=1,
        state_version=1,
        generation_id="gen-1",
        correlation_id="corr-1",
        payload={"n": 1},
    )

    assert store.append_event(
        run_id="run-1",
        event_type="RUN_STARTED",
        sequence=1,
        state_version=1,
        generation_id="gen-1",
        correlation_id="corr-1",
        payload={"n": 1},
        event_id=first["event_id"],
    ) == first
    with pytest.raises(EventDigestConflict):
        store.append_event(
            run_id="run-1",
            event_type="RUN_STARTED",
            sequence=1,
            state_version=1,
            generation_id="gen-1",
            correlation_id="corr-1",
            payload={"n": 999},
        )
    with pytest.raises(EventGapError):
        store.append_event(
            run_id="run-1",
            event_type="RUN_COMPLETED",
            sequence=3,
            state_version=3,
            generation_id="gen-1",
            correlation_id="corr-1",
            payload={"n": 3},
        )

    assert [event["sequence"] for event in store.list_events("run-1")] == [1]
    assert store.pending_outbox("run-1")[0]["event_id"] == first["event_id"]


def test_outbox_publish_failure_keeps_event_pending_and_retry_is_deduplicated(tmp_path):
    store = make_store(tmp_path)
    store.create_run(run_id="run-1", tenant_id="tenant-a", generation_id="gen-1", state={})
    event = store.append_event(
        run_id="run-1",
        event_type="FACTS_READY",
        sequence=1,
        state_version=1,
        generation_id="gen-1",
        correlation_id="corr-1",
        payload={"facts": ["f-1"]},
    )
    calls: list[str] = []

    def fail_once(item):
        calls.append(item["event_id"])
        raise TimeoutError("publisher unavailable")

    assert store.publish_outbox(fail_once) == 0
    assert store.pending_outbox("run-1")[0]["event_id"] == event["event_id"]

    delivered: list[str] = []
    assert store.publish_outbox(lambda item: delivered.append(item["event_id"])) == 1
    assert delivered == [event["event_id"]]
    assert store.publish_outbox(lambda item: delivered.append(item["event_id"])) == 0


def test_replay_uses_snapshot_fallback_and_rejects_gaps_or_corruption(tmp_path):
    store = make_store(tmp_path)
    store.create_run(run_id="run-1", tenant_id="tenant-a", generation_id="gen-1", state={"n": 0})
    token = store.claim_lease("run-1", owner_id="worker-a", lease_ms=1000)
    store.append_event(
        run_id="run-1", event_type="STEP", sequence=1, state_version=1,
        generation_id="gen-1", correlation_id="corr-1", payload={"n": 1},
    )
    store.save_snapshot("run-1", state={"n": 1}, sequence=1, worker_token=token)
    store.append_event(
        run_id="run-1", event_type="STEP", sequence=2, state_version=2,
        generation_id="gen-1", correlation_id="corr-1", payload={"n": 2},
    )
    replay = store.replay("run-1", after_sequence=1)
    assert replay["snapshot"] == {"n": 1}
    assert [event["sequence"] for event in replay["events"]] == [2]
    converged = store.replay_state(
        "run-1",
        after_sequence=1,
        apply_event=lambda state, event: event["payload"],
    )
    assert converged["state"] == {"n": 2}

    store.delete_event_for_test("run-1", sequence=2)
    with pytest.raises(EventGapError):
        store.replay("run-1", after_sequence=1)

    store.corrupt_snapshot_for_test("run-1")
    with pytest.raises(SnapshotCorruptError):
        store.get_run("run-1", tenant_id="tenant-a")


def test_lease_reclaim_fences_old_worker_and_audit_is_append_only(tmp_path):
    times = iter([NOW, NOW, NOW.replace(second=2), NOW.replace(second=2), NOW.replace(second=2)])
    store = DurableRunStore(tmp_path / "runs.sqlite", now=lambda: next(times))
    store.create_run(run_id="run-1", tenant_id="tenant-a", generation_id="gen-1", state={})
    first = store.claim_lease("run-1", owner_id="worker-a", lease_ms=1)
    second = store.claim_lease("run-1", owner_id="worker-b", lease_ms=1)
    assert first != second
    with pytest.raises(LeaseFencedError):
        store.save_snapshot("run-1", state={"old": True}, sequence=1, worker_token=first)
    store.append_audit("run-1", actor_id="worker-b", action="RECOVERED", details={"owner": "worker-b"})
    with pytest.raises(AuditAppendOnlyError):
        store.delete_audit_for_test("run-1")
    with sqlite3.connect(store.path) as cx:
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            cx.execute("DELETE FROM durable_audit WHERE run_id='run-1'")
    assert store.list_audit("run-1")[0]["action"] == "RECOVERED"
