from __future__ import annotations

import pytest

from app.tools.jobs import JobNonceReplayConflict, JobOwnershipConflict, JobPayloadConflict, SQLiteJobStore


def _wire(job_id: str = "pending") -> dict:
    return {
        "schema_version": "ai2.be.processing.result.v1",
        "request_id": "req-1",
        "idempotency_key": "idem-1",
        "attempt": 1,
        "job_id": job_id,
        "status": "QUEUED",
        "review_state": None,
        "input_snapshots": [],
        "result": None,
        "errors": [],
    }


def test_sqlite_job_store_scopes_idempotency_by_tenant_and_attempt(tmp_path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite")
    first, created = store.create_or_get(
        tenant_id="tenant-a",
        dossier_id="dossier-1",
        request_id="req-1",
        idempotency_key="idem-1",
        attempt=1,
        request={"request_id": "req-1"},
        wire=_wire(),
    )
    assert created is True

    duplicate, duplicate_created = store.create_or_get(
        tenant_id="tenant-a",
        dossier_id="dossier-1",
        request_id="req-1-retry",
        idempotency_key="idem-1",
        attempt=1,
        request={"request_id": "req-1-retry"},
        wire=_wire(),
    )
    assert duplicate_created is False
    assert duplicate["job_id"] == first["job_id"]

    other_tenant, other_created = store.create_or_get(
        tenant_id="tenant-b",
        dossier_id="dossier-1",
        request_id="req-1",
        idempotency_key="idem-1",
        attempt=1,
        request={"request_id": "req-1"},
        wire=_wire(),
    )
    assert other_created is True
    assert other_tenant["job_id"] != first["job_id"]


def test_sqlite_job_store_claims_and_persists_terminal_wire_state(tmp_path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite")
    job, _ = store.create_or_get(
        tenant_id="tenant-a",
        dossier_id="dossier-1",
        request_id="req-1",
        idempotency_key="idem-1",
        attempt=1,
        request={"request_id": "req-1"},
        wire=_wire(),
    )
    token = store.claim(job["job_id"], tenant_id="tenant-a", dossier_id="dossier-1")
    assert token
    assert store.claim(job["job_id"], tenant_id="tenant-a", dossier_id="dossier-1") is None

    completed = _wire(job["job_id"])
    completed["status"] = "SUCCEEDED"
    assert store.set_wire(
        job["job_id"],
        tenant_id="tenant-a",
        dossier_id="dossier-1",
        worker_token=token,
        status="SUCCEEDED",
        wire=completed,
        result={"ok": True},
    )
    stored = store.get(job["job_id"], tenant_id="tenant-a", dossier_id="dossier-1")
    assert stored is not None
    assert stored["status"] == "SUCCEEDED"
    assert stored["wire"]["status"] == "SUCCEEDED"
    assert stored["result"] == {"ok": True}
    assert store.get(job["job_id"], tenant_id="tenant-b", dossier_id="dossier-1") is None


def test_sqlite_job_store_lists_successful_jobs_in_update_order(tmp_path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite")
    first, _ = store.create_or_get(
        tenant_id="tenant-a",
        dossier_id="dossier-1",
        request_id="req-1",
        idempotency_key="idem-1",
        attempt=1,
        request={"request_id": "req-1"},
        wire=_wire("job-1"),
    )
    token = store.claim(first["job_id"], tenant_id="tenant-a", dossier_id="dossier-1")
    completed = _wire(first["job_id"])
    completed["status"] = "SUCCEEDED"
    assert store.set_wire(
        first["job_id"],
        tenant_id="tenant-a",
        dossier_id="dossier-1",
        worker_token=token,
        status="SUCCEEDED",
        wire=completed,
        result={"ok": True},
    )

    jobs = store.list_succeeded()
    assert [job["job_id"] for job in jobs] == [first["job_id"]]


def test_sqlite_job_store_rejects_same_tenant_key_for_another_dossier(tmp_path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite")
    store.create_or_get(
        tenant_id="tenant-a",
        dossier_id="dossier-1",
        request_id="req-1",
        idempotency_key="idem-1",
        attempt=1,
        request={"request_id": "req-1"},
        wire=_wire(),
    )
    with pytest.raises(JobOwnershipConflict):
        store.create_or_get(
            tenant_id="tenant-a",
            dossier_id="dossier-2",
            request_id="req-2",
            idempotency_key="idem-1",
            attempt=1,
            request={"request_id": "req-2"},
            wire=_wire(),
        )


def test_sqlite_job_store_rejects_same_scope_key_for_different_payload(tmp_path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite")
    store.create_or_get(
        tenant_id="tenant-a",
        dossier_id="dossier-1",
        request_id="req-1",
        idempotency_key="idem-1",
        attempt=1,
        request={"request_id": "req-1"},
        wire=_wire(),
        request_fingerprint="a" * 64,
    )

    with pytest.raises(JobPayloadConflict, match="payload"):
        store.create_or_get(
            tenant_id="tenant-a",
            dossier_id="dossier-1",
            request_id="req-2",
            idempotency_key="idem-1",
            attempt=1,
            request={"request_id": "req-2"},
            wire=_wire(),
            request_fingerprint="b" * 64,
        )


def test_sqlite_job_store_rejects_nonce_replay_with_different_payload(tmp_path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite")
    store.create_or_get(
        tenant_id="tenant-a",
        dossier_id="dossier-1",
        request_id="req-1",
        idempotency_key="idem-1",
        attempt=1,
        request={"request_id": "req-1"},
        wire=_wire(),
        nonce="nonce-000000000001",
        request_fingerprint="a" * 64,
    )
    with pytest.raises(JobNonceReplayConflict, match="nonce"):
        store.create_or_get(
            tenant_id="tenant-a",
            dossier_id="dossier-2",
            request_id="req-2",
            idempotency_key="idem-2",
            attempt=1,
            request={"request_id": "req-2"},
            wire=_wire(),
            nonce="nonce-000000000001",
            request_fingerprint="b" * 64,
        )
