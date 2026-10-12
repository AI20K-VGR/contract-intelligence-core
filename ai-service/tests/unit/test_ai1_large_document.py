"""A 200-page document gets through the AI1 Kafka path.

Download, OCR and result delivery run for real against a local HTTP server
standing in for the backend's presigned MinIO URLs. The engine is ``pymupdf``
(text layer only), so no paid model is called.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError

import pymupdf
import pytest

from contract_ocr.infrastructure import backend_ocr_job as jobs
from contract_ocr.infrastructure import kafka_worker as kw
from tests.fixtures.make_t200 import make_t200


class _Storage:
    """Serves one source PDF and accepts result PUTs, counting both."""

    def __init__(self, source: bytes) -> None:
        self.source = source
        self.downloads = 0
        self.uploads: list[bytes] = []
        storage = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - http.server API
                storage.downloads += 1
                self.send_response(200)
                self.send_header("Content-Length", str(len(storage.source)))
                self.end_headers()
                self.wfile.write(storage.source)

            def do_PUT(self) -> None:  # noqa: N802 - http.server API
                body = self.rfile.read(int(self.headers["Content-Length"]))
                storage.uploads.append(body)
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture(scope="module")
def t200(tmp_path_factory) -> bytes:
    return make_t200(tmp_path_factory.mktemp("t200") / "t200.pdf").read_bytes()


@pytest.fixture
def storage(t200):
    served = _Storage(t200)
    yield served
    served.close()


@pytest.fixture(autouse=True)
def _fresh_tables(monkeypatch):
    monkeypatch.setattr(kw, "_processed", type(kw._processed)())
    monkeypatch.setattr(jobs, "_backend_jobs", type(jobs._backend_jobs)())


def _command(storage: _Storage, *, event_id: str = "evt_t200") -> dict:
    return {
        "schema_version": kw.SCHEMA_VERSION,
        "event_id": event_id,
        "event_type": kw.EVENT_COMMAND,
        "tenant_id": "tenant_a",
        "correlation": {"run_id": "run_1", "document_id": "doc_t200"},
        "payload": {
            "task_id": 1,
            "attempt_id": 1,
            "tenant_id": "tenant_a",
            "document_id": "doc_t200",
            "source_blob_get_url": f"{storage.url}/source.pdf",
            "source_sha256": hashlib.sha256(storage.source).hexdigest(),
            "pages_to_process": [1],
            "render_target": {},
            "options": {
                "engine": "pymupdf",
                "result_target": {
                    "put_url": f"{storage.url}/result.json",
                    "uri": "s3://ci-render/doc_t200/ai1-result/run_1.json",
                    "content_type": "application/json",
                },
            },
        },
    }


# 1. Size cap and download timeout -------------------------------------------


def _pdf_of(size: int) -> bytes:
    return b"%PDF-1.7\n" + b"0" * (size - 9)


def test_a_60_mb_scan_is_not_refused_at_the_door():
    content = _pdf_of(60 * 1024 * 1024)
    served = _Storage(content)
    try:
        downloaded = jobs.read_source_blob(
            f"{served.url}/big.pdf", hashlib.sha256(content).hexdigest()
        )
    finally:
        served.close()
    assert len(downloaded) == len(content)


def test_the_size_cap_follows_ai1_max_upload_mb(monkeypatch):
    monkeypatch.setenv("AI1_MAX_UPLOAD_MB", "1")
    content = _pdf_of(2 * 1024 * 1024)
    served = _Storage(content)
    try:
        with pytest.raises(RuntimeError, match="1 MB"):
            jobs.read_source_blob(f"{served.url}/big.pdf", hashlib.sha256(content).hexdigest())
    finally:
        served.close()


class _Trickle:
    """A response that hands out ``chunk`` bytes per read, ``total`` in all."""

    def __init__(self, chunk: bytes, total: int, delay: float = 0.0) -> None:
        self.chunk, self.left, self.delay = chunk, total, delay

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, size):
        if self.left <= 0:
            return b""
        time.sleep(self.delay)
        part = self.chunk[: min(size, self.left)]
        self.left -= len(part)
        return part


def test_a_silent_connection_times_out_after_30_seconds(monkeypatch):
    timeouts = []
    body = b"%PDF-1.7 minimal"

    def fake_urlopen(url, timeout):
        timeouts.append(timeout)
        return _Trickle(body, len(body))

    monkeypatch.setattr(jobs, "urlopen", fake_urlopen)
    assert jobs.read_source_blob("http://minio/x.pdf", hashlib.sha256(body).hexdigest()) == body
    # Per socket operation; the whole transfer has its own deadline (next test).
    assert timeouts == [30]


def test_a_trickling_download_stops_at_the_total_deadline(monkeypatch):
    monkeypatch.setenv("AI1_SOURCE_DOWNLOAD_TIMEOUT_SECONDS", "1")
    monkeypatch.setattr(
        jobs, "urlopen", lambda url, timeout: _Trickle(b"%PDF-" + b"0" * 1000, 10**9, delay=0.2)
    )

    with pytest.raises(RuntimeError, match="AI1_SOURCE_DOWNLOAD_TIMEOUT_SECONDS"):
        jobs.read_source_blob("http://minio/x.pdf", "0" * 64)


@pytest.mark.parametrize("value", ["", "abc", "200MB", "0", "-5"])
def test_a_bad_size_cap_falls_back_to_200_mb(monkeypatch, value):
    monkeypatch.setenv("AI1_MAX_UPLOAD_MB", value)
    assert jobs.max_upload_bytes() == 200 * 1024 * 1024


# 2. One download per command -------------------------------------------------


def test_a_200_page_document_is_downloaded_once_and_read_whole(storage):
    envelope = kw._handle_command(_command(storage))

    assert envelope["event_type"] == kw.EVENT_COMPLETED, envelope["payload"]["error"]
    assert storage.downloads == 1
    [body] = storage.uploads
    snapshot = json.loads(body)["snapshot"]
    assert snapshot["page_count"] == 200
    # The fixture's base-14 font has no Vietnamese glyphs, so only "Trang N" is checked.
    first_words = {
        " ".join(line["text"].split()[:2]) for page in snapshot["pages"] for line in page["lines"]
    }
    assert {f"Trang {n}" for n in range(1, 201)} <= first_words


# 3. Kafka keeps the consumer through a long document --------------------------


class _StopWorker(Exception):
    pass


def _consumer_settings(monkeypatch) -> dict:
    captured: dict = {}

    class Consumer:
        def __init__(self, *topics, **kwargs):
            captured.update(kwargs)

        async def start(self):
            raise _StopWorker

        async def stop(self):
            pass

    class Producer:
        def __init__(self, **kwargs):
            pass

        async def stop(self):
            pass

    monkeypatch.setattr(kw, "AIOKafkaConsumer", Consumer)
    monkeypatch.setattr(kw, "AIOKafkaProducer", Producer)
    monkeypatch.setattr(kw, "start_metrics_server", lambda: None)
    with pytest.raises(_StopWorker):
        asyncio.run(kw.run_worker())
    return captured


def test_the_consumer_may_spend_an_hour_on_one_command(monkeypatch):
    monkeypatch.delenv("KAFKA_MAX_POLL_INTERVAL_MS", raising=False)
    settings = _consumer_settings(monkeypatch)
    assert settings["max_poll_interval_ms"] == 3_600_000


def test_the_poll_interval_follows_the_environment(monkeypatch):
    monkeypatch.setenv("KAFKA_MAX_POLL_INTERVAL_MS", "7200000")
    assert _consumer_settings(monkeypatch)["max_poll_interval_ms"] == 7_200_000


# 4. Finished jobs do not pile up in memory -----------------------------------


def test_a_delivered_result_is_not_kept_in_the_job_table(storage):
    envelope = kw._handle_command(_command(storage))

    assert envelope["payload"]["result_ref"]["bytes"] == len(storage.uploads[0])
    job = jobs.get_backend_job(envelope["payload"]["job_id"])
    assert job is not None and job["status"] == "completed"
    assert job["result"] is None


def test_remembered_events_are_capped(monkeypatch):
    monkeypatch.setattr(
        kw,
        "_process_command",
        lambda message: (
            {"payload": {"status": "completed"}, "event_id": message["event_id"]},
            None,
        ),
    )
    for n in range(501):
        kw._handle_command({"event_id": f"evt_{n}", "payload": {}})

    assert len(kw._processed) == 500
    assert "evt_0" not in kw._processed
    assert "evt_500" in kw._processed


def test_the_job_table_is_capped():
    # Finished jobs are what the cap drops (running ones are kept, see
    # test_ai1_review_fixes.py).
    ids = []
    for _ in range(501):
        job_id = jobs.new_backend_job("ocr")[0]
        jobs.update_backend_job(job_id, status="completed")
        ids.append(job_id)
    jobs.new_backend_job("ocr")

    assert len(jobs._backend_jobs) == 500
    assert jobs.get_backend_job(ids[0]) is None
    assert jobs.get_backend_job(ids[-1]) is not None


# 5. A failed result upload is retried ----------------------------------------


@pytest.fixture
def sleeps(monkeypatch):
    waited: list[float] = []
    monkeypatch.setattr(kw.time, "sleep", waited.append)
    return waited


def _flaky_put(monkeypatch, failures: int) -> list[bytes]:
    attempts: list[bytes] = []

    def put(url, body, content_type):
        attempts.append(body)
        if len(attempts) <= failures:
            raise URLError("connection reset")

    monkeypatch.setattr(kw, "_put_result", put)
    return attempts


def test_a_result_upload_is_retried_until_it_succeeds(monkeypatch, sleeps):
    attempts = _flaky_put(monkeypatch, failures=2)
    target = {"put_url": "http://minio/r.json", "uri": "s3://r.json"}

    inline, ref, error = kw._deliver_result({"snapshot": {}}, target)

    assert (inline, error) == (None, None)
    assert ref is not None and len(attempts) == 3
    assert len(sleeps) == 2
    assert 0.8 <= sleeps[0] <= 1.2 and 3.2 <= sleeps[1] <= 4.8


def test_a_result_too_big_for_kafka_fails_only_after_every_retry(monkeypatch, sleeps):
    attempts = _flaky_put(monkeypatch, failures=99)
    monkeypatch.setattr(kw, "MAX_MESSAGE_BYTES", 100)
    target = {"put_url": "http://minio/r.json", "uri": "s3://r.json"}

    inline, ref, error = kw._deliver_result({"snapshot": {"text": "x" * 500}}, target)

    assert (inline, ref) == (None, None)
    assert error is not None and error["code"] == "AI1_RESULT_UPLOAD_FAILED"
    assert len(attempts) == 4
    assert len(sleeps) == 3 and 12.8 <= sleeps[2] <= 19.2


def test_the_fixture_pages_all_differ(t200):
    with pymupdf.open(stream=t200, filetype="pdf") as document:
        texts = [page.get_text().strip() for page in document]
    assert len(texts) == 200
    assert len(set(texts)) == 200
