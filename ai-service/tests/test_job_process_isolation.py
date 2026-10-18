import os

import pytest

from app.api import main


def _crash_after_claim(job_id, payload, conn):
    conn.send(("token-1", "tenant-a", "dossier-a"))
    os._exit(137)  # what the kernel OOM-killer leaves behind


def _finish(job_id, payload, conn):
    conn.send(("token-1", "tenant-a", "dossier-a"))


def _slow_start_then_finish(job_id, payload, conn):
    import time

    time.sleep(1.0)  # adapt of a large snapshot, on top of the ~2 s spawn + import
    conn.send(("token-1", "tenant-a", "dossier-a"))
    time.sleep(4.5)  # the pipeline, inside its 6 s budget but past spawn + 6 s


def _hang_after_claim(job_id, payload, conn):
    import time

    conn.send(("token-1", "tenant-a", "dossier-a"))
    time.sleep(60)


def _hang(job_id, payload, conn):
    import time

    time.sleep(60)


class _Store:
    def __init__(self):
        self.failed = []

    def set_wire(self, job_id, **kwargs):
        self.failed.append((job_id, kwargs))

    def fail_unclaimed(self, job_id, update):
        self.failed.append((job_id, update))

    def get(self, job_id, **_kw):
        return {"tenant_id": "tenant-a", "dossier_id": "dossier-a", "wire": {"job_id": job_id}}


@pytest.fixture
def store(monkeypatch):
    fake = _Store()
    monkeypatch.setattr(main, "JOB_STORE", fake)
    monkeypatch.setattr(main.ProcessingTraceStore, "finalize_stale_job", lambda self, job_id: 0)
    monkeypatch.setattr(main, "_refresh_query_store", lambda job_id: None)
    return fake


def _budget(seconds):
    return {"policy_flags": {"budget_limits": {"max_processing_seconds": seconds}}}


def test_a_killed_job_process_fails_only_that_job(store):
    main._run_isolated_job("job-1", _budget(30), target=_crash_after_claim)
    ((job_id, update),) = store.failed
    assert job_id == "job-1" and update["worker_token"] == "token-1"
    assert update["wire"]["errors"][0]["code"] == "AI2_WORKER_CRASHED"


def test_a_finished_job_process_leaves_the_result_to_the_child(store):
    main._run_isolated_job("job-2", _budget(30), target=_finish)
    assert store.failed == []


def test_a_job_process_past_its_budget_is_killed(store, monkeypatch):
    monkeypatch.setattr(main, "_JOB_KILL_GRACE_SECONDS", 0)
    main._run_isolated_job("job-3", _budget(1), target=_hang)
    ((job_id, update),) = store.failed
    assert job_id == "job-3" and update["errors"][0]["code"] == "PROCESSING_TIMEOUT"


# PR #125 review round 2 (Chuongpham2004): the kill deadline counts from the claim (when the
# child's budget starts), not from spawn; a slow start must not eat the job budget.
def test_slow_child_start_does_not_eat_the_job_budget(store, monkeypatch):
    monkeypatch.setattr(main, "_JOB_KILL_GRACE_SECONDS", 0)
    main._run_isolated_job("job-4", _budget(6), target=_slow_start_then_finish)
    assert store.failed == []


def test_a_job_hung_after_its_claim_is_still_killed(store, monkeypatch):
    monkeypatch.setattr(main, "_JOB_KILL_GRACE_SECONDS", 0)
    main._run_isolated_job("job-5", _budget(5), target=_hang_after_claim)
    ((job_id, update),) = store.failed
    assert job_id == "job-5" and update["worker_token"] == "token-1"
    assert update["wire"]["errors"][0]["code"] == "PROCESSING_TIMEOUT"
