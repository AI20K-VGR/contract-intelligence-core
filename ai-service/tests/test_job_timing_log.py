"""P1: job lifecycle timing lands in coverage.job_timing and one ai2.job_timing line per scope."""

from __future__ import annotations

import logging
import re

import pytest
from test_a1_query_digest import _body_only_request

from app.api import main
from app.tools import query_store
from app.tools.jobs import SQLiteJobStore
from app.tools.store import InMemorySnapshotStore


@pytest.fixture
def worker(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "test-secret")
    monkeypatch.setenv("AI2_PROCESSING_EGRESS_ALLOWED", "false")
    monkeypatch.setattr(main, "JOB_ISOLATION", "thread")
    store = SQLiteJobStore(tmp_path / "timing.sqlite")
    monkeypatch.setattr(main, "JOB_STORE", store)
    monkeypatch.setattr(main, "STORE", InMemorySnapshotStore())
    monkeypatch.setattr(main, "WIRE_JOBS", {})
    monkeypatch.setattr(query_store, "save_query_snapshot", lambda *_args: None)
    payload = _body_only_request()
    job, _ = store.create_or_get(
        tenant_id="tenant_a",
        dossier_id=payload["dossier_id"],
        request_id=payload["request_id"],
        idempotency_key=payload["idempotency_key"],
        attempt=1,
        request=payload,
        wire={"status": "QUEUED", "result": None, "errors": []},
    )
    return store, job["job_id"], payload


def _timing_lines(caplog: pytest.LogCaptureFixture, scope: str) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.name == "ai2.timing" and f"scope={scope}" in r.getMessage()
    ]


def _field(line: str, name: str) -> str:
    match = re.search(rf"\b{name}=(\S+)", line)
    assert match, f"{name} missing from {line!r}"
    return match.group(1)


def test_worker_attaches_job_timing_before_persist(worker, monkeypatch) -> None:
    store, job_id, payload = worker
    captured: dict = {}
    original = store.complete_with_snapshot

    def capture(job_id, **kwargs):
        captured.update(kwargs)
        return original(job_id, **kwargs)

    monkeypatch.setattr(store, "complete_with_snapshot", capture)
    main._run_wire_job(job_id, payload)

    timing = captured["result"]["contribution"]["coverage"]["job_timing"]
    assert set(timing) == {"snapshot_load_ms", "claim_ms", "pipeline_ms"}
    assert all(isinstance(v, int) and v >= 0 for v in timing.values())
    wire_coverage = captured["wire"]["result"]["index_contribution"]["coverage"]
    assert wire_coverage["job_timing"] == timing


def test_worker_logs_job_timing_line(worker, caplog) -> None:
    store, job_id, payload = worker
    with caplog.at_level(logging.INFO, logger="ai2.timing"):
        main._run_wire_job(job_id, payload)

    (line,) = _timing_lines(caplog, "worker")
    assert _field(line, "job_id") == job_id
    for name in ("snapshot_load_ms", "claim_ms", "pipeline_ms", "persist_ms"):
        assert _field(line, name).isdigit()
    assert _field(line, "status") == "SUCCEEDED"
    assert _field(line, "accepted") == "True"
    assert payload["snapshots"][0]["snapshot_id"] not in line


def test_failed_job_still_logs_timing(worker, monkeypatch, caplog) -> None:
    store, job_id, payload = worker

    def explode(*_args, **_kwargs):
        raise RuntimeError("pipeline crashed")

    monkeypatch.setattr(main, "run_idp", explode)
    with caplog.at_level(logging.INFO, logger="ai2.timing"):
        main._run_wire_job(job_id, payload)

    (line,) = _timing_lines(caplog, "worker")
    assert _field(line, "snapshot_load_ms").isdigit()
    assert _field(line, "claim_ms").isdigit()
    assert _field(line, "pipeline_ms") == "None"
    assert _field(line, "persist_ms") == "None"
    assert _field(line, "status") == "FAILED"
    assert "pipeline crashed" not in line
    assert store.get(job_id)["status"] == "FAILED"


def test_dispatch_logs_slot_wait(monkeypatch, caplog) -> None:
    monkeypatch.setattr(main, "JOB_ISOLATION", "thread")
    monkeypatch.setattr(main, "_execute_wire_job", lambda *_args: None)
    with caplog.at_level(logging.INFO, logger="ai2.timing"):
        main._run_wire_job("job_dispatch_1", {"dossier_id": "d"})

    (line,) = _timing_lines(caplog, "dispatch")
    assert _field(line, "job_id") == "job_dispatch_1"
    assert _field(line, "isolation") == "thread"
    assert _field(line, "slot_wait_ms").isdigit()
    assert _field(line, "run_ms").isdigit()


def test_timing_logger_has_info_stderr_handler() -> None:
    timing = logging.getLogger("ai2.timing")
    assert timing.propagate is True
    handlers = [
        h
        for h in timing.handlers
        # pytest swaps sys.stderr per test; the handler type and level are the contract.
        if type(h) is logging.StreamHandler
    ]
    assert handlers and handlers[0].level <= logging.INFO
    assert timing.getEffectiveLevel() <= logging.INFO
