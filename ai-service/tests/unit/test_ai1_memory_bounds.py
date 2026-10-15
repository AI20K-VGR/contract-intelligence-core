"""AI1 must not keep every document's OCR snapshot (prod: 97 → 494 MiB after one dossier)."""

import pytest

from contract_ocr.infrastructure import backend_ocr_job as jobs
from contract_ocr.infrastructure import kafka_worker as kw
from contract_ocr.infrastructure.memory import release_memory

RESULT = {"schema_version": "ai1.snapshot.v1", "snapshot": {"pages": [{"text": "Điều 1"}]}}


@pytest.fixture
def registry(monkeypatch):
    monkeypatch.setattr(jobs, "_backend_jobs", {})
    return jobs._backend_jobs


def _command(event_id):
    return {
        "schema_version": kw.SCHEMA_VERSION,
        "event_id": event_id,
        "event_type": kw.EVENT_COMMAND,
        "tenant_id": "tenant_a",
        "correlation": {"run_id": "run_1", "document_id": "doc_1"},
        "payload": {
            "task_id": 1,
            "attempt_id": 1,
            "tenant_id": "tenant_a",
            "document_id": "doc_1",
            "source_blob_get_url": "http://minio:9000/dossiers/doc_1.pdf",
            "source_sha256": "a" * 64,
            "pages_to_process": [1],
            "render_target": {},
            "options": {"engine": "mistral"},
        },
    }


@pytest.fixture
def worker(monkeypatch, registry):
    """Run the real job registry with the OCR itself stubbed out."""

    def run(job_id, request, **_kwargs):
        jobs.update_backend_job(job_id, status="completed", result=RESULT, finished_at="now")

    monkeypatch.setattr(kw, "_processed", {})
    monkeypatch.setattr(kw, "align_pages_to_pdf", lambda request: request)
    monkeypatch.setattr(kw, "run_backend_ocr", run)
    return registry


def test_the_kafka_worker_drops_a_job_once_it_has_its_result(worker):
    envelope = kw._handle_command(_command("evt_1"))

    assert envelope["payload"]["result"] == RESULT
    assert worker == {}


def test_processed_events_are_bounded(worker, monkeypatch):
    monkeypatch.setenv("AI1_PROCESSED_EVENTS_KEPT", "3")
    for i in range(10):
        kw._handle_command(_command(f"evt_{i}"))

    assert list(kw._processed) == ["evt_7", "evt_8", "evt_9"]


def test_a_redelivered_event_is_still_answered_from_the_cache(worker, monkeypatch):
    first = kw._handle_command(_command("evt_dup"))
    monkeypatch.setattr(kw, "run_backend_ocr", lambda *_a, **_k: pytest.fail("ran OCR twice"))

    assert kw._handle_command(_command("evt_dup")) is first


def test_the_http_registry_keeps_only_recent_finished_jobs(registry, monkeypatch):
    monkeypatch.setenv("AI1_FINISHED_JOBS_KEPT", "2")
    running, _ = jobs.new_backend_job("ocr")
    finished = []
    for _ in range(4):
        job_id, _ = jobs.new_backend_job("ocr")
        jobs.update_backend_job(job_id, status="completed", result=RESULT)
        finished.append(job_id)

    assert running in registry  # unfinished jobs are never dropped
    assert [job for job in finished if job in registry] == finished[-2:]


def test_pop_backend_job(registry):
    job_id, _ = jobs.new_backend_job("ocr")

    assert jobs.pop_backend_job(job_id)["job_id"] == job_id
    assert jobs.pop_backend_job(job_id) is None


def test_release_memory_never_raises():
    assert release_memory() in {True, False}
