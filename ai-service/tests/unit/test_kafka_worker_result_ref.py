import hashlib
import json
from urllib.error import URLError

import pytest

from contract_ocr.infrastructure import kafka_worker as kw

TARGET = {
    "put_url": "http://minio:9000/ci-render/doc_1/ai1-result/run_1.json?X-Amz-Signature=x",
    "uri": "s3://ci-render/doc_1/ai1-result/run_1.json",
    "content_type": "application/json",
}
RESULT = {
    "schema_version": "ai1.snapshot.v1",
    "snapshot": {"document_id": "doc_1", "pages": [{"text": "Điều 1. Hợp đồng"}]},
}


def _command(result_target=None):
    options = {"engine": "mistral"}
    if result_target is not None:
        options["result_target"] = result_target
    return {
        "schema_version": kw.SCHEMA_VERSION,
        "event_id": "evt_1",
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
            "options": options,
        },
    }


@pytest.fixture
def ocr(monkeypatch):
    """Stub the OCR run; tests set the finished job in ``ocr.job``."""
    state = type("OcrStub", (), {})()
    state.job = {"job_id": "ai1_1", "status": "completed", "result": RESULT, "error": None}
    state.uploads = []
    monkeypatch.setattr(kw, "_processed", {})
    monkeypatch.setattr(kw, "align_pages_to_pdf", lambda request: request)
    monkeypatch.setattr(kw, "new_backend_job", lambda kind: ("ai1_1", {}))
    monkeypatch.setattr(kw, "run_backend_ocr", lambda *args, **kwargs: None)
    monkeypatch.setattr(kw, "get_backend_job", lambda job_id: state.job)
    monkeypatch.setattr(
        kw,
        "_put_result",
        lambda url, body, content_type: state.uploads.append((url, body, content_type)),
    )
    return state


def test_a_result_with_a_target_is_uploaded_and_sent_by_reference(ocr):
    envelope = kw._handle_command(_command(TARGET))

    payload = envelope["payload"]
    [(url, body, content_type)] = ocr.uploads
    assert (url, content_type) == (TARGET["put_url"], "application/json")
    assert json.loads(body) == RESULT
    assert "Điều 1" in body.decode("utf-8")
    assert envelope["event_type"] == kw.EVENT_COMPLETED
    assert payload["result"] is None
    assert payload["result_ref"] == {
        "uri": TARGET["uri"],
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
    }


def test_a_command_without_a_target_keeps_the_result_inline(ocr):
    envelope = kw._handle_command(_command())

    assert ocr.uploads == []
    assert envelope["payload"]["result"] == RESULT
    assert "result_ref" not in envelope["payload"]


def test_a_failed_upload_of_a_small_result_falls_back_to_inline(ocr, monkeypatch):
    def refuse(url, body, content_type):
        raise URLError("connection refused")

    monkeypatch.setattr(kw, "_put_result", refuse)

    envelope = kw._handle_command(_command(TARGET))

    assert envelope["event_type"] == kw.EVENT_COMPLETED
    assert envelope["payload"]["result"] == RESULT
    assert "result_ref" not in envelope["payload"]


def test_a_failed_upload_of_a_result_too_big_for_kafka_fails_the_job(ocr, monkeypatch):
    def refuse(url, body, content_type):
        raise URLError("connection refused")

    monkeypatch.setattr(kw, "_put_result", refuse)
    monkeypatch.setattr(kw, "MAX_MESSAGE_BYTES", 100)

    envelope = kw._handle_command(_command(TARGET))

    payload = envelope["payload"]
    assert envelope["event_type"] == kw.EVENT_FAILED
    assert payload["status"] == "failed"
    assert payload["result"] is None
    assert payload["error"]["code"] == "AI1_RESULT_UPLOAD_FAILED"


def test_a_failed_ocr_job_uploads_nothing(ocr):
    ocr.job = {
        "job_id": "ai1_1",
        "status": "failed",
        "result": None,
        "error": {"code": "AI1_OCR_FAILED", "message": "boom"},
    }

    envelope = kw._handle_command(_command(TARGET))

    assert ocr.uploads == []
    assert envelope["event_type"] == kw.EVENT_FAILED
    assert envelope["payload"]["error"]["code"] == "AI1_OCR_FAILED"
