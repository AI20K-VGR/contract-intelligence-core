"""ai1.ocr.progress and AI1_NO_READABLE_PAGE on the Kafka worker (issue #115, DOC-05d)."""

import json

import pytest

from contract_ocr.infrastructure import backend_ocr_job as jobs
from contract_ocr.infrastructure import kafka_worker as kw


def _command(event_id="evt_cmd_1"):
    return {
        "schema_version": kw.SCHEMA_VERSION,
        "event_id": event_id,
        "event_type": kw.EVENT_COMMAND,
        "tenant_id": "tenant_a",
        "correlation": {"run_id": "run_1", "dossier_id": "dos_1", "document_id": "doc_1"},
        "payload": {
            "task_id": 1,
            "attempt_id": 1,
            "tenant_id": "tenant_a",
            "document_id": "doc_1",
            "source_blob_get_url": "http://minio:9000/dossiers/doc_1.pdf",
            "source_sha256": "a" * 64,
            "pages_to_process": [1, 2, 3],
            "render_target": {},
            "options": {"engine": "mistral"},
        },
    }


@pytest.fixture
def sent(monkeypatch):
    """Capture what the worker hands the producer for progress reports."""
    captured = []
    monkeypatch.setattr(
        kw, "_progress_sink", lambda value, key: captured.append((json.loads(value), key))
    )
    return captured


def test_reports_carry_the_command_correlation_and_their_own_event_id(sent):
    report = kw._progress_reporter(_command(), "ai1_job_1")

    report(1, 3)

    [(envelope, key)] = sent
    assert envelope["event_type"] == "ai1.ocr.progress"
    assert envelope["correlation"] == {
        "run_id": "run_1",
        "dossier_id": "dos_1",
        "document_id": "doc_1",
    }
    assert envelope["tenant_id"] == "tenant_a"
    assert envelope["payload"] == {
        "job_id": "ai1_job_1",
        "kind": "ocr",
        "status": "processing",
        "progress": {"done": 1, "total": 3, "unit": "page"},
    }
    # The backend dedupes the results topic by event_id, and the result itself
    # carries the command's: a report reusing it would get the result dropped.
    assert envelope["event_id"] != "evt_cmd_1"
    assert key == b"doc_1"  # same partition as the result: reports stay before it


def test_at_most_one_report_a_second_and_always_the_last_page(sent):
    now = [100.0]
    report = kw._progress_reporter(_command(), "ai1_job_1", clock=lambda: now[0])

    report(1, 10)
    report(2, 10)  # same second: dropped
    now[0] += 0.5
    report(3, 10)  # still within the second: dropped
    now[0] += 0.6
    report(4, 10)
    report(4, 10)  # no progress: dropped
    report(10, 10)  # the last page always goes

    done = [envelope["payload"]["progress"]["done"] for envelope, _ in sent]
    assert done == [1, 4, 10]
    assert len({envelope["event_id"] for envelope, _ in sent}) == 3


def test_no_reports_without_a_producer(monkeypatch):
    monkeypatch.setattr(kw, "_progress_sink", None)
    assert kw._progress_reporter(_command(), "ai1_job_1") is None


@pytest.fixture
def worker(monkeypatch):
    """The real job registry and worker, with the OCR itself stubbed."""
    monkeypatch.setattr(jobs, "_backend_jobs", {})
    monkeypatch.setattr(kw, "_processed", {})
    monkeypatch.setattr(kw, "align_pages_to_pdf", lambda request: request)
    state = {"pages": [{"status": "SUCCESS"}, {"status": "SUCCESS"}, {"status": "FAILED"}]}

    def run(job_id, request, *, on_progress=None, **_kwargs):
        for done in (1, 2, 3):
            if on_progress is not None:
                on_progress(done, 3)
        result = {"schema_version": "ai1.snapshot.v1", "snapshot": {"pages": state["pages"]}}
        jobs.update_backend_job(job_id, status="completed", result=result, finished_at="now")

    monkeypatch.setattr(kw, "run_backend_ocr", run)
    return state


def test_a_document_reports_progress_then_its_result_keeps_the_command_event_id(worker, sent):
    envelope = kw._handle_command(_command())

    assert [e["payload"]["progress"]["done"] for e, _ in sent] == [1, 3]
    assert envelope["event_type"] == kw.EVENT_COMPLETED
    assert envelope["event_id"] == "evt_cmd_1"
    assert envelope["event_id"] not in {e["event_id"] for e, _ in sent}


def test_a_document_with_no_readable_page_fails_with_the_first_page_error(
    worker, sent, monkeypatch
):
    long_error = "SKIPPED: OpenAI vision unavailable — " + "x" * 300
    worker["pages"] = [
        {"status": "FAILED", "error": long_error},
        {"status": "FAILED", "error": "TimeoutError: mistral-ocr-2512"},
    ]
    uploads = []
    monkeypatch.setattr(kw, "_put_result", lambda *args: uploads.append(args))
    command = _command()
    command["payload"]["options"]["result_target"] = {
        "put_url": "http://minio:9000/ci-render/doc_1/ai1-result/run_1.json?X-Amz-Signature=x",
        "uri": "s3://ci-render/doc_1/ai1-result/run_1.json",
    }

    envelope = kw._handle_command(command)

    assert envelope["event_type"] == kw.EVENT_FAILED
    payload = envelope["payload"]
    assert payload["status"] == "failed"
    assert payload["error"]["code"] == "AI1_NO_READABLE_PAGE"
    # The backend's wording: page count, then the first page error cut to 200 characters.
    assert payload["error"]["message"] == (
        f"AI1 không đọc được trang nào (2/2 trang lỗi): {long_error[:200]}"
    )
    assert payload["result"] is None
    assert "result_ref" not in payload
    assert uploads == []  # the empty snapshot is never uploaded


def test_a_page_without_a_status_keeps_the_document_completed(worker, sent):
    # The backend does not judge such a snapshot (#117): AI1 must not fail it either.
    worker["pages"] = [{"status": "FAILED", "error": "TimeoutError"}, {}]

    envelope = kw._handle_command(_command())

    assert envelope["event_type"] == kw.EVENT_COMPLETED
    assert envelope["payload"]["error"] is None


@pytest.mark.parametrize(
    ("pages", "message"),
    [
        ([{"status": "FAILED"}, {"status": "PARTIAL"}], None),
        ([{"status": "FAILED"}, {"status": "SUCCESS"}], None),
        (
            [{"status": "FAILED", "error": "boom"}],
            "AI1 không đọc được trang nào (1/1 trang lỗi): boom",
        ),
        (
            [{"status": "FAILED"}, {"status": "FAILED"}],
            "AI1 không đọc được trang nào (2/2 trang lỗi)",
        ),
        ([{"status": "FAILED", "error": "boom"}, {}], None),  # mixed: one page not judged
        ([{"status": "FAILED"}, {"status": ""}], None),
        ([{}, {}], None),  # pages without a status are not judged, as on the backend
        ([], None),
    ],
)
def test_no_readable_page_matches_the_backend_rule(pages, message):
    assert kw._no_readable_page({"snapshot": {"pages": pages}}) == message


def test_no_readable_page_ignores_a_result_without_a_snapshot():
    assert kw._no_readable_page(None) is None
    assert kw._no_readable_page({"schema_version": "ai1.snapshot.v1"}) is None


def test_ocr_progress_moves_the_job_percentage(monkeypatch):
    monkeypatch.setattr(jobs, "_backend_jobs", {})
    job_id, _ = jobs.new_backend_job("ocr")
    seen = []

    class Processor:
        def execute(self, **kwargs):
            for done in (1, 2, 4):
                kwargs["on_page_done"](done, 4)
                seen.append(jobs.get_backend_job(job_id)["progress_pct"])
            raise RuntimeError("stop after the OCR stage")

    monkeypatch.setattr(jobs, "_processor", Processor())
    monkeypatch.setattr(jobs, "read_source_blob", lambda url, sha: b"%PDF-1.7")
    reported = []
    payload = _command()["payload"]
    payload["options"] = {"engine": "pymupdf"}  # no engine client, no API call
    request = jobs.BackendOcrJobRequest.model_validate(payload)
    monkeypatch.setattr(jobs.pymupdf, "open", lambda *_a, **_k: _ThreePagePdf())

    jobs._run_backend_ocr(job_id, request, lambda done, total: reported.append((done, total)))

    assert seen == [31, 47, 80]  # 15 % + 65 % x done/total
    assert reported == [(1, 4), (2, 4), (4, 4)]


class _ThreePagePdf:
    page_count = 3

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_the_sink_sends_from_the_ocr_thread_on_the_worker_loop():
    import asyncio
    import threading

    class Producer:
        def __init__(self):
            self.sent = []
            self.loop_thread = None

        async def send(self, topic, value, key=None):
            self.loop_thread = threading.get_ident()
            self.sent.append((topic, value, key))

    async def main():
        producer = Producer()
        sink = kw._make_progress_sink(producer, "ci.ai1.ocr.results", asyncio.get_running_loop())
        ocr = threading.Thread(target=sink, args=(b"{}", b"doc_1"))
        ocr.start()
        await asyncio.to_thread(ocr.join)
        for _ in range(50):
            if producer.sent:
                break
            await asyncio.sleep(0.01)
        return producer, threading.get_ident(), ocr.ident

    producer, loop_thread, ocr_thread = asyncio.run(main())
    assert producer.sent == [("ci.ai1.ocr.results", b"{}", b"doc_1")]
    assert producer.loop_thread == loop_thread != ocr_thread
