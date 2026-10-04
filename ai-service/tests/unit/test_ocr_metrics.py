from prometheus_client import REGISTRY, generate_latest

from contract_ocr.infrastructure import kafka_worker as kw
from contract_ocr.infrastructure import prometheus_metrics
from contract_ocr.infrastructure.observability import observation, reset_langfuse_for_tests
from contract_ocr.infrastructure.prometheus_metrics import record_model_call, record_ocr_job


def _value(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


SNAPSHOT_RESULT = {
    "schema_version": "ai1.snapshot.v1",
    "snapshot": {
        "document_id": "doc_secret_name",
        "pages": [
            {"status": "SUCCESS", "warnings": [], "text": "Điều 1. Hợp đồng"},
            {
                "status": "PARTIAL",
                "warnings": ["ocr:text_reader_fallback:RateLimitError", "needs_review:x:l1"],
            },
            {"status": "PARTIAL", "warnings": ["possible_duplicate_of:p1"]},
        ],
    },
}


def test_finished_job_counts_pages_fallback_and_review():
    before = {
        "requests": _value("ai1_ocr_requests_total", engine="mistral", status="completed"),
        "success": _value("ai1_ocr_pages_processed_total", engine="mistral", page_status="SUCCESS"),
        "partial": _value("ai1_ocr_pages_processed_total", engine="mistral", page_status="PARTIAL"),
        "fallback": _value("ai1_ocr_fallback_pages_total", engine="mistral"),
        "review": _value("ai1_ocr_review_pages_total", engine="mistral"),
        "duration": _value("ai1_ocr_request_duration_seconds_count", engine="mistral"),
    }

    record_ocr_job(
        engine="mistral", status="completed", duration_seconds=12.5, result=SNAPSHOT_RESULT
    )

    assert _value("ai1_ocr_requests_total", engine="mistral", status="completed") == (
        before["requests"] + 1
    )
    assert _value(
        "ai1_ocr_pages_processed_total", engine="mistral", page_status="SUCCESS"
    ) == (before["success"] + 1)
    assert _value(
        "ai1_ocr_pages_processed_total", engine="mistral", page_status="PARTIAL"
    ) == (before["partial"] + 2)
    assert _value("ai1_ocr_fallback_pages_total", engine="mistral") == before["fallback"] + 1
    assert _value("ai1_ocr_review_pages_total", engine="mistral") == before["review"] + 2
    assert _value("ai1_ocr_request_duration_seconds_count", engine="mistral") == (
        before["duration"] + 1
    )


def test_labels_never_carry_request_values():
    record_ocr_job(
        engine="mistral; drop table",
        status="failed",
        error={"code": "contract of ACME.pdf", "message": "secret text"},
    )
    exposition = generate_latest(REGISTRY)
    assert _value("ai1_ocr_failures_total", engine="other", error_code="OTHER") >= 1
    for leaked in (b"drop table", b"ACME", b"secret text", b"doc_secret_name", "Điều".encode()):
        assert leaked not in exposition


def test_model_cost_is_summed_per_model():
    before = _value("ai1_ocr_cost_usd_total", model="mistral-ocr-2512")
    calls = _value("ai1_ocr_model_calls_total", model="mistral-ocr-2512")
    record_model_call("mistral-ocr-2512", {"total": 0.002})
    record_model_call("mistral-ocr-2512", None)
    assert _value("ai1_ocr_cost_usd_total", model="mistral-ocr-2512") == before + 0.002
    assert _value("ai1_ocr_model_calls_total", model="mistral-ocr-2512") == calls + 2


def test_generation_is_metered_without_langfuse_when_metrics_are_on(monkeypatch):
    for name in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AI1_METRICS_PORT", "9108")
    reset_langfuse_for_tests()
    before = _value("ai1_ocr_cost_usd_total", model="gpt-test")

    with observation("transcribe-page", as_type="generation", model="gpt-test") as generation:
        assert generation is not None
        generation.update(output={"character_count": 3}, cost_details={"total": 0.01})
    with observation("plain-span") as span:
        assert span is None

    assert _value("ai1_ocr_cost_usd_total", model="gpt-test") == before + 0.01
    reset_langfuse_for_tests()


def test_generation_stays_none_when_metrics_are_off(monkeypatch):
    for name in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("AI1_METRICS_PORT", raising=False)
    reset_langfuse_for_tests()
    with observation("transcribe-page", as_type="generation", model="gpt-test") as generation:
        assert generation is None
    reset_langfuse_for_tests()


def test_worker_records_each_command_once(monkeypatch):
    job = {"job_id": "ai1_1", "status": "completed", "result": SNAPSHOT_RESULT, "error": None}
    monkeypatch.setattr(kw, "_processed", {})
    monkeypatch.setattr(kw, "align_pages_to_pdf", lambda request: request)
    monkeypatch.setattr(kw, "new_backend_job", lambda kind: ("ai1_1", {}))
    monkeypatch.setattr(kw, "run_backend_ocr", lambda *args, **kwargs: None)
    monkeypatch.setattr(kw, "get_backend_job", lambda job_id: job)
    command = {
        "schema_version": kw.SCHEMA_VERSION,
        "event_id": "evt_metrics_1",
        "event_type": kw.EVENT_COMMAND,
        "payload": {
            "task_id": 1,
            "attempt_id": 1,
            "tenant_id": "tenant_a",
            "document_id": "doc_1",
            "source_blob_get_url": "http://minio:9000/dossiers/doc_1.pdf",
            "source_sha256": "a" * 64,
            "pages_to_process": [1],
            "options": {"engine": "mistral"},
        },
    }
    before = _value("ai1_ocr_requests_total", engine="mistral", status="completed")

    first = kw._handle_command(command)
    again = kw._handle_command(command)  # Kafka redelivery

    assert again is first
    assert first["payload"]["result"] == SNAPSHOT_RESULT
    assert _value("ai1_ocr_requests_total", engine="mistral", status="completed") == before + 1
    assert _value("ai1_ocr_in_progress") == 0


def test_metrics_server_exposes_ocr_series_at_zero_before_the_first_ocr(monkeypatch):
    """increase() would miss the first OCR after a restart if its series started at 1."""
    monkeypatch.setenv("AI1_METRICS_PORT", "9108")
    monkeypatch.setattr(prometheus_metrics, "start_http_server", lambda port: None)

    prometheus_metrics.start_metrics_server()

    for name, labels in (
        ("ai1_ocr_requests_total", {"engine": "pymupdf", "status": "completed"}),
        ("ai1_ocr_requests_total", {"engine": "pymupdf", "status": "failed"}),
        ("ai1_ocr_request_duration_seconds_count", {"engine": "pymupdf"}),
        ("ai1_ocr_pages_processed_total", {"engine": "pymupdf", "page_status": "FAILED"}),
        ("ai1_ocr_fallback_pages_total", {"engine": "pymupdf"}),
        ("ai1_ocr_review_pages_total", {"engine": "pymupdf"}),
    ):
        assert REGISTRY.get_sample_value(name, labels) == 0.0, name
