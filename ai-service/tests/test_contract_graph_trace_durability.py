from __future__ import annotations

import json
import subprocess
import sys
import time

import pytest
from fastapi.testclient import TestClient

from app.api import main as api_main
from app.api import processing_trace_router
from app.pipeline import idp
from app.pipeline.contract_graph import builder, pair_builder
from app.security.service_envelope import build_service_envelope
from app.tools.jobs import PostgresJobStore, SQLiteJobStore
from app.tools.processing_trace_store import (
    LeaseFencedTraceWrite,
    ProcessingTraceStore,
    ProcessingTraceWriter,
    project_processing_trace,
)


def _claimed_job(path, *, execution_id="execution-a"):
    jobs = SQLiteJobStore(path)
    job, _ = jobs.create_or_get(
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        request_id="request-a",
        idempotency_key="idem-a",
        attempt=1,
        request={"source_snapshot_digest": "sha256:abc"},
        wire={"status": "QUEUED"},
    )
    token = jobs.claim(
        job["job_id"],
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        lease_ms=60_000,
        execution_id=execution_id,
    )
    assert token
    return jobs, job["job_id"], token


def test_start_is_durable_before_work_and_survives_store_restart(tmp_path):
    path = tmp_path / "jobs.sqlite"
    jobs, job_id, token = _claimed_job(path)
    store = ProcessingTraceStore(jobs)
    writer = ProcessingTraceWriter(
        store,
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id=job_id,
        snapshot_digest="sha256:abc",
        execution_id="execution-a",
        worker_token=token,
    )

    writer.start("contract_graph_operation")
    restarted = ProcessingTraceStore(SQLiteJobStore(path))
    events = restarted.read_events(
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id=job_id,
        snapshot_digest="sha256:abc",
    )
    assert [(event.stage_id, event.status) for event in events] == [
        ("contract_graph_operation", "STARTED")
    ]


def test_terminal_event_follows_start_with_count_and_safe_reason(tmp_path):
    jobs, job_id, token = _claimed_job(tmp_path / "jobs.sqlite")
    writer = ProcessingTraceWriter(
        ProcessingTraceStore(jobs),
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id=job_id,
        snapshot_digest="sha256:abc",
        execution_id="execution-a",
        worker_token=token,
    )
    writer.start("contract_graph_pairs")
    writer.finish("contract_graph_pairs", "SKIPPED", item_count=0, reason_code="CONSENT_DENIED")

    events = ProcessingTraceStore(jobs).read_events(
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id=job_id,
        snapshot_digest="sha256:abc",
    )
    assert [event.status for event in events] == ["STARTED", "SKIPPED"]
    assert events[1].sequence > events[0].sequence
    assert events[1].item_count == 0
    assert events[1].reason_code == "CONSENT_DENIED"


def test_failed_stage_is_not_aggregated_as_complete(tmp_path):
    jobs, job_id, token = _claimed_job(tmp_path / "jobs.sqlite")
    writer = ProcessingTraceWriter(
        ProcessingTraceStore(jobs),
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id=job_id,
        snapshot_digest="sha256:abc",
        execution_id="execution-a",
        worker_token=token,
    )
    writer.start("contract_graph_operation")
    writer.finish(
        "contract_graph_operation", "FAILED", item_count=0, reason_code="GRAPH_BUILD_FAILED"
    )
    projection = project_processing_trace(
        ProcessingTraceStore(jobs).read_events(
            tenant_id="tenant-a",
            dossier_id="dossier-a",
            job_id=job_id,
            snapshot_digest="sha256:abc",
        ),
        terminal_job=True,
    )
    assert projection["status"] == "COMPLETE"
    assert projection["stages"][0]["status"] == "FAILED"


@pytest.mark.parametrize("job_status", ["FAILED", "CANCELLED"])
def test_trace_route_surfaces_terminal_job_outcome_after_completed_stages(
    tmp_path, monkeypatch, job_status
):
    jobs, job_id, token = _claimed_job(tmp_path / f"{job_status}.sqlite")
    store = ProcessingTraceStore(jobs)
    writer = ProcessingTraceWriter(
        store,
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id=job_id,
        snapshot_digest="sha256:abc",
        execution_id="execution-a",
        worker_token=token,
    )
    writer.start("contract_graph_operation")
    writer.finish("contract_graph_operation", "COMPLETED", item_count=0)
    jobs.set_wire(
        job_id,
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        worker_token=token,
        status=job_status,
        wire={"status": job_status},
    )
    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "fixture-hmac-material-trace-01")
    monkeypatch.setattr(processing_trace_router, "job_store_from_env", lambda: jobs)
    params = {"job_id": job_id, "dossier_id": "dossier-a", "snapshot_digest": "sha256:abc"}
    signed = build_service_envelope(
        params,
        secret="fixture-hmac-material-trace-01",
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        scopes=["ai2.trace.read"],
    )
    response = TestClient(api_main.app).get(
        f"/internal/processing-trace/{job_id}",
        params=params,
        headers={"x-ai2-service-envelope": json.dumps(signed)},
    )

    assert response.status_code == 200
    assert response.json()["job_status"] == job_status
    assert response.json()["status"] == "COMPLETE"
    assert response.json()["stages"][0]["status"] == "COMPLETED"


def test_explicit_skip_is_readable_even_without_a_stage_start(tmp_path):
    jobs, job_id, token = _claimed_job(tmp_path / "jobs.sqlite")
    store = ProcessingTraceStore(jobs)
    writer = ProcessingTraceWriter(
        store,
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id=job_id,
        snapshot_digest="sha256:abc",
        execution_id="execution-a",
        worker_token=token,
    )
    writer.skip("contract_graph_pairs", "FEATURE_DISABLED")

    events = store.read_latest_execution(
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id=job_id,
        snapshot_digest="sha256:abc",
    )
    projection = project_processing_trace(events)
    assert projection["status"] == "COMPLETE"
    assert projection["stages"][0]["status"] == "SKIPPED"


def test_old_worker_token_cannot_write_after_reclaim(tmp_path):
    jobs, job_id, old_token = _claimed_job(tmp_path / "jobs.sqlite", execution_id="execution-old")
    store = ProcessingTraceStore(jobs)
    old_writer = ProcessingTraceWriter(
        store,
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id=job_id,
        snapshot_digest="sha256:abc",
        execution_id="execution-old",
        worker_token=old_token,
    )
    old_writer.start("contract_graph_operation")
    cx = jobs._connect()
    cx.execute("UPDATE jobs SET lease_until_ms=0 WHERE job_id=?", (job_id,))
    cx.commit()
    cx.close()
    new_token = jobs.claim(
        job_id,
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        lease_ms=60_000,
        execution_id="execution-new",
    )
    assert new_token and new_token != old_token

    with pytest.raises(LeaseFencedTraceWrite):
        store.append(
            tenant_id="tenant-a",
            dossier_id="dossier-a",
            job_id=job_id,
            snapshot_digest="sha256:abc",
            execution_id="execution-old",
            stage_id="contract_graph_operation",
            status="COMPLETED",
            worker_token=old_token,
        )
    old_writer.finish("contract_graph_operation", "COMPLETED", item_count=0)
    assert old_writer.trace_status == "FENCED"
    assert [
        event.status
        for event in store.read_events(
            tenant_id="tenant-a",
            dossier_id="dossier-a",
            job_id=job_id,
            snapshot_digest="sha256:abc",
        )
    ] == ["STARTED"]


def test_sweep_marks_open_stage_interrupted_and_dangling_start_is_unknown(tmp_path):
    jobs, job_id, token = _claimed_job(tmp_path / "jobs.sqlite")
    trace_store = ProcessingTraceStore(jobs)
    writer = ProcessingTraceWriter(
        trace_store,
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id=job_id,
        snapshot_digest="sha256:abc",
        execution_id="execution-a",
        worker_token=token,
    )
    writer.start("contract_graph_operation")
    jobs._now_ms = lambda: int(time.time() * 1000) + 100_000  # noqa: SLF001
    cx = jobs._connect()
    cx.execute("UPDATE jobs SET lease_until_ms=0 WHERE job_id=?", (job_id,))
    cx.commit()
    cx.close()
    swept = jobs.sweep_stale({"errors": []})
    assert swept == [job_id]

    trace_store.finalize_stale_job(job_id)
    projection = project_processing_trace(
        trace_store.read_events(
            tenant_id="tenant-a",
            dossier_id="dossier-a",
            job_id=job_id,
            snapshot_digest="sha256:abc",
        )
    )
    assert projection["status"] == "INTERRUPTED_UNKNOWN"
    assert projection["stages"][0]["status"] == "INTERRUPTED_UNKNOWN"


def test_dangling_start_after_finalizer_failure_is_incomplete_unknown(tmp_path):
    jobs, job_id, token = _claimed_job(tmp_path / "jobs.sqlite")
    store = ProcessingTraceStore(jobs)
    writer = ProcessingTraceWriter(
        store,
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id=job_id,
        snapshot_digest="sha256:abc",
        execution_id="execution-a",
        worker_token=token,
    )
    writer.start("contract_graph_operation")
    jobs.set_wire(
        job_id,
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        worker_token=token,
        status="FAILED",
        wire={"status": "FAILED"},
    )
    projection = project_processing_trace(
        store.read_events(
            tenant_id="tenant-a",
            dossier_id="dossier-a",
            job_id=job_id,
            snapshot_digest="sha256:abc",
        ),
        terminal_job=True,
    )
    assert projection["status"] == "INCOMPLETE_UNKNOWN"
    assert projection["stages"][0]["status"] == "INCOMPLETE_UNKNOWN"


def test_worker_process_exit_then_restart_and_sweep_keeps_interrupted_marker(tmp_path):
    path = tmp_path / "process-restart.sqlite"
    first_process = """
import sys
from app.tools.jobs import SQLiteJobStore
from app.tools.processing_trace_store import ProcessingTraceStore, ProcessingTraceWriter
jobs = SQLiteJobStore(sys.argv[1])
job, _ = jobs.create_or_get(tenant_id='tenant-p', dossier_id='dossier-p', request_id='request-p',
    idempotency_key='idem-p', attempt=1, request={}, wire={'status':'QUEUED'})
token = jobs.claim(job['job_id'], tenant_id='tenant-p', dossier_id='dossier-p', lease_ms=1,
    execution_id='execution-p')
writer = ProcessingTraceWriter(ProcessingTraceStore(jobs), tenant_id='tenant-p', dossier_id='dossier-p',
    job_id=job['job_id'], snapshot_digest='sha256:process', execution_id='execution-p', worker_token=token)
writer.start('contract_graph_operation')
print(job['job_id'])
"""
    created = subprocess.run(
        [sys.executable, "-c", first_process, str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    job_id = created.stdout.strip()
    time.sleep(0.02)
    restarted_process = """
import sys
from app.tools.jobs import SQLiteJobStore
from app.tools.processing_trace_store import ProcessingTraceStore, project_processing_trace
jobs = SQLiteJobStore(sys.argv[1])
store = ProcessingTraceStore(jobs)
swept = jobs.sweep_stale({'errors': []})
store.finalize_stale_job(sys.argv[2])
events = store.read_latest_execution(tenant_id='tenant-p', dossier_id='dossier-p', job_id=sys.argv[2],
    snapshot_digest='sha256:process')
print(project_processing_trace(events, terminal_job=jobs.get(sys.argv[2])['status'] == 'FAILED')['status'])
"""
    restarted = subprocess.run(
        [sys.executable, "-c", restarted_process, str(path), job_id],
        check=True,
        capture_output=True,
        text=True,
    )
    assert restarted.stdout.strip() == "INTERRUPTED_UNKNOWN"


def test_retry_execution_projection_does_not_join_old_attempt_stages(tmp_path):
    jobs, job_id, old_token = _claimed_job(tmp_path / "jobs.sqlite", execution_id="execution-old")
    store = ProcessingTraceStore(jobs)
    old = ProcessingTraceWriter(
        store,
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id=job_id,
        snapshot_digest="sha256:abc",
        execution_id="execution-old",
        worker_token=old_token,
    )
    old.start("contract_graph_operation")
    cx = jobs._connect()
    cx.execute("UPDATE jobs SET lease_until_ms=0 WHERE job_id=?", (job_id,))
    cx.commit()
    cx.close()
    new_token = jobs.claim(
        job_id,
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        lease_ms=60_000,
        execution_id="execution-new",
    )
    assert new_token
    new = ProcessingTraceWriter(
        store,
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id=job_id,
        snapshot_digest="sha256:abc",
        execution_id="execution-new",
        worker_token=new_token,
    )
    new.start("contract_graph_pairs")

    latest = store.read_latest_execution(
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id=job_id,
        snapshot_digest="sha256:abc",
    )
    assert {event.execution_id for event in latest} == {"execution-new"}
    assert [event.stage_id for event in latest] == ["contract_graph_pairs"]


def test_reclaimed_execution_is_current_before_first_stage_event(tmp_path):
    jobs, job_id, old_token = _claimed_job(tmp_path / "jobs.sqlite", execution_id="execution-old")
    store = ProcessingTraceStore(jobs)
    previous = ProcessingTraceWriter(
        store,
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id=job_id,
        snapshot_digest="sha256:abc",
        execution_id="execution-old",
        worker_token=old_token,
    )
    previous.start("contract_graph_operation")
    previous.finish("contract_graph_operation", "COMPLETED", item_count=2)
    cx = jobs._connect()
    cx.execute("UPDATE jobs SET lease_until_ms=0 WHERE job_id=?", (job_id,))
    cx.commit()
    cx.close()

    new_token = jobs.claim(
        job_id,
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        lease_ms=60_000,
        execution_id="execution-new",
    )
    assert new_token
    current = store.read_latest_execution(
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id=job_id,
        snapshot_digest="sha256:abc",
    )
    assert current == []


def test_trace_store_outage_disables_writer_without_raising_to_pipeline(tmp_path, monkeypatch):
    jobs, job_id, token = _claimed_job(tmp_path / "jobs.sqlite")
    store = ProcessingTraceStore(jobs)
    monkeypatch.setattr(
        store, "append", lambda **_kwargs: (_ for _ in ()).throw(OSError("db offline"))
    )
    writer = ProcessingTraceWriter(
        store,
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id=job_id,
        snapshot_digest="sha256:abc",
        execution_id="execution-a",
        worker_token=token,
    )

    writer.start("contract_graph_operation")
    writer.finish("contract_graph_operation", "COMPLETED", item_count=0)

    assert writer.trace_status == "UNAVAILABLE"
    assert jobs.get(job_id)["status"] == "RUNNING"
    assert jobs.get(job_id)["trace_status"] == "UNAVAILABLE"
    result_wire = {"status": "SUCCEEDED", "result": {"finding_count": 3}}
    assert jobs.set_wire(
        job_id,
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        worker_token=token,
        status="SUCCEEDED",
        wire=result_wire,
    )
    stored = jobs.get(job_id)
    assert stored["status"] == "SUCCEEDED"
    assert stored["wire"] == result_wire
    assert stored["trace_status"] == "UNAVAILABLE"


def test_run_idp_persists_stage_start_before_operation_and_pairs(monkeypatch, tmp_path):
    from fixtures import envelope
    from fixtures.contract_graph_pair_records import pair_record

    jobs, job_id, token = _claimed_job(tmp_path / "jobs.sqlite")
    store = ProcessingTraceStore(jobs)
    writer = ProcessingTraceWriter(
        store,
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id=job_id,
        snapshot_digest="sha256:abc",
        execution_id="execution-a",
        worker_token=token,
    )
    monkeypatch.setenv("AI2_CONTRACT_GRAPH_ENABLED", "1")
    monkeypatch.setenv("AI2_CONTRACT_GRAPH_PAIRS_ENABLED", "1")
    monkeypatch.delenv("AI2_CONTRACT_GRAPH_PAIRS_API_KEY", raising=False)
    monkeypatch.delenv("AI2_CONTRACT_GRAPH_PAIRS_BASE_URL", raising=False)
    seen = []
    original_graph = builder.build_contract_graph
    original_pairs = pair_builder.build_pair_relations

    def graph_spy(*args, **kwargs):
        events = store.read_latest_execution(
            tenant_id="tenant-a",
            dossier_id="dossier-a",
            job_id=job_id,
            snapshot_digest="sha256:abc",
        )
        seen.append(("operation", [(event.stage_id, event.status) for event in events]))
        return original_graph(*args, **kwargs)

    def pair_spy(*args, **kwargs):
        events = store.read_latest_execution(
            tenant_id="tenant-a",
            dossier_id="dossier-a",
            job_id=job_id,
            snapshot_digest="sha256:abc",
        )
        seen.append(("pairs", [(event.stage_id, event.status) for event in events]))
        return original_pairs(*args, **kwargs)

    monkeypatch.setattr(builder, "build_contract_graph", graph_spy)
    monkeypatch.setattr(pair_builder, "build_pair_relations", pair_spy)
    record = pair_record()
    idp.run_idp(record, envelope(), llm=None, job_id=job_id, trace_writer=writer)

    assert seen[0] == (
        "operation",
        [
            ("extraction", "STARTED"),
            ("extraction", "COMPLETED"),
            ("contract_graph_operation", "STARTED"),
        ],
    )
    assert seen[1][0] == "pairs"
    assert seen[1][1][-1] == ("contract_graph_pairs", "STARTED")
    events = store.read_latest_execution(
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id=job_id,
        snapshot_digest="sha256:abc",
    )
    assert [(event.stage_id, event.status) for event in events] == [
        ("extraction", "STARTED"),
        ("extraction", "COMPLETED"),
        ("contract_graph_operation", "STARTED"),
        ("contract_graph_operation", "COMPLETED"),
        ("contract_graph_pairs", "STARTED"),
        ("contract_graph_pairs", "COMPLETED"),
    ]


def test_pair_builder_failure_is_kept_on_record_for_receipt(monkeypatch):
    from fixtures import envelope
    from fixtures.contract_graph_pair_records import pair_record

    monkeypatch.setenv("AI2_CONTRACT_GRAPH_ENABLED", "1")
    monkeypatch.setenv("AI2_CONTRACT_GRAPH_PAIRS_ENABLED", "1")
    monkeypatch.delenv("AI2_CONTRACT_GRAPH_PAIRS_API_KEY", raising=False)
    monkeypatch.delenv("AI2_CONTRACT_GRAPH_PAIRS_BASE_URL", raising=False)
    monkeypatch.setattr(
        pair_builder,
        "build_pair_relations",
        lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError()),
    )
    record = pair_record()

    result = idp.run_idp(record, envelope(), llm=None, job_id="pair-builder-failure")

    assert result.status == "SUCCEEDED"
    assert record.pair_relations_stage_status == "FAILED"


def test_signed_trace_read_is_scoped_and_store_failure_is_unavailable(tmp_path, monkeypatch):
    path = tmp_path / "jobs.sqlite"
    jobs, job_id, token = _claimed_job(path)
    store = ProcessingTraceStore(jobs)
    writer = ProcessingTraceWriter(
        store,
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id=job_id,
        snapshot_digest="sha256:abc",
        execution_id="execution-a",
        worker_token=token,
    )
    writer.start("contract_graph_operation")
    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "fixture-hmac-material-test-01")
    monkeypatch.setattr(processing_trace_router, "job_store_from_env", lambda: jobs)
    client = TestClient(api_main.app)
    payload = {"job_id": job_id, "dossier_id": "dossier-a", "snapshot_digest": "sha256:abc"}
    signed = build_service_envelope(
        payload,
        secret="fixture-hmac-material-test-01",
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        scopes=["ai2.trace.read"],
    )
    response = client.get(
        f"/internal/processing-trace/{job_id}",
        params=payload,
        headers={"x-ai2-service-envelope": json.dumps(signed)},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROGRESS"
    assert response.json()["stages"][0]["status"] == "RUNNING"

    monkeypatch.setattr(
        store, "append", lambda **_kwargs: (_ for _ in ()).throw(OSError("trace disk full"))
    )
    writer.finish("contract_graph_operation", "COMPLETED", item_count=0)
    assert jobs.get(job_id)["trace_status"] == "UNAVAILABLE"
    failed_write = client.get(
        f"/internal/processing-trace/{job_id}",
        params=payload,
        headers={"x-ai2-service-envelope": json.dumps(signed)},
    )
    assert failed_write.json()["status"] == "TRACE_UNAVAILABLE"
    assert failed_write.json()["trace_status"] == "UNAVAILABLE"
    assert failed_write.json()["job_status"] == "RUNNING"

    wrong_scope = build_service_envelope(
        payload,
        secret="fixture-hmac-material-test-01",
        tenant_id="tenant-b",
        dossier_id="dossier-a",
        scopes=["ai2.trace.read"],
    )
    denied = client.get(
        f"/internal/processing-trace/{job_id}",
        params=payload,
        headers={"x-ai2-service-envelope": json.dumps(wrong_scope)},
    )
    assert denied.status_code == 404

    monkeypatch.setattr(
        processing_trace_router, "job_store_from_env", lambda: (_ for _ in ()).throw(OSError())
    )
    unavailable = client.get(
        f"/internal/processing-trace/{job_id}",
        params=payload,
        headers={"x-ai2-service-envelope": json.dumps(signed)},
    )
    assert unavailable.status_code == 200
    assert unavailable.json()["status"] == "TRACE_UNAVAILABLE"
    assert unavailable.json()["trace_status"] == "UNAVAILABLE"


def test_trace_read_failure_preserves_known_job_status(tmp_path, monkeypatch):
    path = tmp_path / "jobs.sqlite"
    jobs, job_id, _token = _claimed_job(path)
    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "fixture-hmac-material-test-01")
    monkeypatch.setattr(processing_trace_router, "job_store_from_env", lambda: jobs)
    monkeypatch.setattr(
        ProcessingTraceStore,
        "read_latest_execution",
        lambda *_a, **_kw: (_ for _ in ()).throw(OSError("trace read failed")),
    )
    payload = {"job_id": job_id, "dossier_id": "dossier-a", "snapshot_digest": "sha256:abc"}
    signed = build_service_envelope(
        payload,
        secret="fixture-hmac-material-test-01",
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        scopes=["ai2.trace.read"],
    )

    response = TestClient(api_main.app).get(
        f"/internal/processing-trace/{job_id}",
        params=payload,
        headers={"x-ai2-service-envelope": json.dumps(signed)},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "TRACE_UNAVAILABLE"
    assert response.json()["job_status"] == "RUNNING"


def test_postgres_adapter_migrates_and_persists_trace_across_store_instances(pg_url):
    from uuid import uuid4

    from sqlalchemy import update

    from app.db.tables import jobs as job_table

    suffix = uuid4().hex
    jobs = PostgresJobStore(pg_url)
    job, _ = jobs.create_or_get(
        tenant_id=f"tenant-{suffix}",
        dossier_id=f"dossier-{suffix}",
        request_id=f"request-{suffix}",
        idempotency_key=f"idem-{suffix}",
        attempt=1,
        request={"source_snapshot_digest": "sha256:pg"},
        wire={"status": "QUEUED"},
    )
    token = jobs.claim(
        job["job_id"],
        tenant_id=job["tenant_id"],
        dossier_id=job["dossier_id"],
        execution_id="pg-execution",
    )
    assert token
    trace = ProcessingTraceStore(jobs)
    writer = ProcessingTraceWriter(
        trace,
        tenant_id=job["tenant_id"],
        dossier_id=job["dossier_id"],
        job_id=job["job_id"],
        snapshot_digest="sha256:pg",
        execution_id="pg-execution",
        worker_token=token,
    )
    writer.start("contract_graph_operation")

    reopened = ProcessingTraceStore(PostgresJobStore(pg_url))
    events = reopened.read_events(
        tenant_id=job["tenant_id"],
        dossier_id=job["dossier_id"],
        job_id=job["job_id"],
        snapshot_digest="sha256:pg",
    )
    assert [(event.stage_id, event.status) for event in events] == [
        ("contract_graph_operation", "STARTED")
    ]
    with jobs.engine.begin() as cx:
        cx.execute(
            update(job_table).where(job_table.c.job_id == job["job_id"]).values(lease_until_ms=0)
        )
    reclaimed = jobs.claim(
        job["job_id"],
        tenant_id=job["tenant_id"],
        dossier_id=job["dossier_id"],
        execution_id="pg-execution-next",
    )
    assert reclaimed
    assert (
        reopened.read_latest_execution(
            tenant_id=job["tenant_id"],
            dossier_id=job["dossier_id"],
            job_id=job["job_id"],
            snapshot_digest="sha256:pg",
        )
        == []
    )


def test_pairs_llm_stop_is_visible_on_completed_stage(monkeypatch, tmp_path):
    # Every classifier call failing used to finish COMPLETED with no reason, so the
    # timeline showed "Đã hoàn tất · 0 mục" for a run that classified nothing.
    from app.contracts.contract_graph import PairResult
    from fixtures import envelope
    from fixtures.contract_graph_pair_records import pair_record

    jobs, job_id, token = _claimed_job(tmp_path / "jobs.sqlite")
    store = ProcessingTraceStore(jobs)
    writer = ProcessingTraceWriter(
        store,
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id=job_id,
        snapshot_digest="sha256:abc",
        execution_id="execution-a",
        worker_token=token,
    )
    monkeypatch.setenv("AI2_CONTRACT_GRAPH_ENABLED", "1")
    monkeypatch.setenv("AI2_CONTRACT_GRAPH_PAIRS_ENABLED", "1")
    monkeypatch.setattr(
        pair_builder,
        "build_pair_relations",
        lambda *_a, **_kw: PairResult(
            mode="llm", prompt_version="test", stats={"stopped_reason": "LLM_FALLBACK"}
        ),
    )

    idp.run_idp(pair_record(), envelope(), llm=None, job_id=job_id, trace_writer=writer)

    pairs = [
        event
        for event in store.read_latest_execution(
            tenant_id="tenant-a",
            dossier_id="dossier-a",
            job_id=job_id,
            snapshot_digest="sha256:abc",
        )
        if event.stage_id == "contract_graph_pairs" and event.status != "STARTED"
    ]
    assert [(e.status, e.item_count, e.reason_code) for e in pairs] == [
        ("COMPLETED", 0, "PARTIAL_LLM_FALLBACK")
    ]
