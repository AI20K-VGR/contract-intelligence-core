"""Review follow-ups on the large-document fixes (#79). No paid model is called."""

from __future__ import annotations

import asyncio
import io
from urllib.error import HTTPError, URLError

import pytest
from fastapi.testclient import TestClient

from contract_ocr.infrastructure import backend_ocr_job as jobs
from contract_ocr.infrastructure import kafka_worker as kw

TARGET = {"put_url": "http://minio/r.json", "uri": "s3://r.json"}


@pytest.fixture(autouse=True)
def _fresh_tables(monkeypatch):
    monkeypatch.setattr(kw, "_processed", type(kw._processed)())
    monkeypatch.setattr(jobs, "_backend_jobs", type(jobs._backend_jobs)())
    monkeypatch.setattr(kw.time, "sleep", lambda seconds: None)


def _failing_put(monkeypatch, error) -> list[int]:
    attempts: list[int] = []

    def put(url, body, content_type):
        attempts.append(1)
        raise error

    monkeypatch.setattr(kw, "_put_result", put)
    return attempts


# Result upload: only failures a retry can fix are retried ----------------------


@pytest.mark.parametrize("code", [400, 403, 404, 413])
def test_a_client_error_is_not_retried(monkeypatch, code):
    attempts = _failing_put(monkeypatch, HTTPError("http://minio", code, "no", {}, io.BytesIO()))
    monkeypatch.setattr(kw, "MAX_MESSAGE_BYTES", 100)

    _inline, _ref, error = kw._deliver_result({"snapshot": {"text": "x" * 500}}, TARGET)

    assert len(attempts) == 1
    assert error is not None and error["code"] == "AI1_RESULT_UPLOAD_FAILED"


@pytest.mark.parametrize(
    "error",
    [
        HTTPError("http://minio", 503, "busy", {}, io.BytesIO()),
        HTTPError("http://minio", 429, "slow down", {}, io.BytesIO()),
        HTTPError("http://minio", 408, "timeout", {}, io.BytesIO()),
        URLError("connection reset"),
        TimeoutError("timed out"),
    ],
)
def test_server_errors_timeouts_and_dropped_connections_are_retried(monkeypatch, error):
    attempts = _failing_put(monkeypatch, error)
    monkeypatch.setattr(kw, "MAX_MESSAGE_BYTES", 100)

    kw._deliver_result({"snapshot": {"text": "x" * 500}}, TARGET)

    assert len(attempts) == 4


# Idempotency cache keeps no inline result ------------------------------------


def _envelope_with(result):
    def process(message):
        payload = {"status": "completed", "result": result}
        return {"event_id": message["event_id"], "payload": payload}, None

    return process


def test_an_envelope_with_an_inline_result_is_not_cached(monkeypatch):
    monkeypatch.setattr(kw, "_process_command", _envelope_with({"snapshot": {"pages": []}}))

    kw._handle_command({"event_id": "evt_inline", "payload": {}})

    assert "evt_inline" not in kw._processed


def test_an_envelope_sent_by_reference_is_cached_for_redelivery(monkeypatch):
    monkeypatch.setattr(kw, "_process_command", _envelope_with(None))

    first = kw._handle_command({"event_id": "evt_ref", "payload": {}})

    assert kw._processed["evt_ref"] is first


# Job table never drops a job that is still running ---------------------------


def test_running_jobs_are_never_dropped_from_the_job_table(monkeypatch):
    monkeypatch.setattr(jobs, "MAX_REMEMBERED_JOBS", 3)
    running = [jobs.new_backend_job("ocr")[0] for _ in range(3)]
    finished = jobs.new_backend_job("ocr")[0]
    jobs.update_backend_job(finished, status="completed")

    newest = jobs.new_backend_job("ocr")[0]

    assert all(jobs.get_backend_job(job_id) for job_id in running)
    assert jobs.get_backend_job(finished) is None
    assert jobs.get_backend_job(newest) is not None


# A rejected commit does not report a successful document as failed -----------


class _Record:
    def __init__(self, value):
        self.value = value


class _Consumer:
    def __init__(self, *topics, **kwargs):
        self.records = [_Record({"event_id": "evt_1", "event_type": kw.EVENT_COMMAND})]
        self.commits = 0

    async def start(self):
        pass

    async def stop(self):
        pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.records:
            raise StopAsyncIteration
        return self.records.pop()

    async def commit(self):
        self.commits += 1
        raise RuntimeError("CommitFailedError: group rebalanced")


class _Producer:
    sent: list[bytes] = []

    def __init__(self, **kwargs):
        _Producer.sent = []

    async def start(self):
        pass

    async def stop(self):
        pass

    async def send_and_wait(self, topic, value, key=None):
        _Producer.sent.append(value)


def test_a_failed_commit_publishes_no_extra_failure(monkeypatch):
    monkeypatch.setattr(kw, "AIOKafkaConsumer", _Consumer)
    monkeypatch.setattr(kw, "AIOKafkaProducer", _Producer)
    monkeypatch.setattr(kw, "start_metrics_server", lambda: None)
    monkeypatch.setattr(
        kw,
        "_handle_command",
        lambda message: {"event_type": kw.EVENT_COMPLETED, "payload": {"job_id": "j"}},
    )

    asyncio.run(kw.run_worker())

    assert len(_Producer.sent) == 1
    assert kw.EVENT_COMPLETED.encode() in _Producer.sent[0]
    assert kw.EVENT_FAILED.encode() not in _Producer.sent[0]


# Web API -----------------------------------------------------------------------


@pytest.fixture
def web(monkeypatch):
    monkeypatch.delenv("AI_SERVICE_API_KEY", raising=False)
    from contract_ocr.web import app as web_app

    return TestClient(web_app.app)


def test_a_finished_job_hands_its_result_over_once(web):
    job_id, _ = jobs.new_backend_job("ocr")
    jobs.update_backend_job(job_id, status="completed", result={"snapshot": {"pages": []}})

    first = web.get(f"/api/v1/jobs/{job_id}").json()
    second = web.get(f"/api/v1/jobs/{job_id}").json()

    assert first["result"] == {"snapshot": {"pages": []}}
    assert second["status"] == "completed" and second["result"] is None


def test_a_running_job_keeps_nothing_to_hand_over_yet(web):
    job_id, _ = jobs.new_backend_job("ocr")
    jobs.update_backend_job(job_id, status="processing")

    assert web.get(f"/api/v1/jobs/{job_id}").json()["status"] == "processing"
    assert jobs.get_backend_job(job_id)["status"] == "processing"


def test_the_upload_limit_message_follows_the_setting(web, monkeypatch):
    monkeypatch.setenv("AI1_MAX_UPLOAD_MB", "1")
    body = b"%PDF-1.7\n" + b"0" * (2 * 1024 * 1024)

    response = web.post(
        "/api/ocr",
        files={"file": ("big.pdf", body, "application/pdf")},
        data={"engine": "pymupdf"},
    )

    assert response.status_code == 413
    assert "1MB" in response.json()["detail"]
