"""Several documents at once, selective verification and 429 retries (no paid calls)."""

from __future__ import annotations

import json
import logging
import threading
import time

import httpx
import numpy as np
import pymupdf
import pytest

from contract_ocr.domain.entities import Context
from contract_ocr.infrastructure import backend_ocr_job as jobs
from contract_ocr.infrastructure.ocr import mistral_ocr
from contract_ocr.infrastructure.ocr.verified_mistral_ocr import VerifiedMistralOCREngine
from tests.unit.test_verified_mistral_ocr import (
    CLEAN_VN,
    MONEY,
    MONEY_VN,
    PARA,
    PARA_2,
    FakeArbiter,
    FakeReader,
    _page,
)

# 1. Documents in flight ------------------------------------------------------


def test_documents_in_flight_default_to_two_and_follow_the_environment(monkeypatch):
    monkeypatch.delenv("AI1_MAX_DOCUMENTS_IN_FLIGHT", raising=False)
    assert jobs.max_documents_in_flight() == 2
    monkeypatch.setenv("AI1_MAX_DOCUMENTS_IN_FLIGHT", "3")
    assert jobs.max_documents_in_flight() == 3
    monkeypatch.setenv("AI1_MAX_DOCUMENTS_IN_FLIGHT", "0")
    assert jobs.max_documents_in_flight() == 1


class _WatchingProcessor:
    """Wraps the real processor and records how many documents it reads at once."""

    def __init__(self, real) -> None:
        self.real, self.now, self.peak = real, 0, 0
        self.lock = threading.Lock()

    def execute(self, **kwargs):
        with self.lock:
            self.now += 1
            self.peak = max(self.peak, self.now)
        try:
            time.sleep(0.5)
            return self.real.execute(**kwargs)
        finally:
            with self.lock:
                self.now -= 1


def test_two_documents_are_read_at_once_and_a_third_waits(tmp_path, monkeypatch):
    path = tmp_path / "text.pdf"
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((72, 100), "Trang 1 - Dieu 1", fontsize=11)
        pdf.save(path)
    content = path.read_bytes()
    watching = _WatchingProcessor(jobs._processor)
    monkeypatch.setattr(jobs, "_processor", watching)
    monkeypatch.setattr(jobs, "_process_slots", threading.BoundedSemaphore(2))

    def run(n: int) -> None:
        job_id, _ = jobs.new_backend_job("ocr")
        request = jobs.BackendOcrJobRequest(
            task_id=n,
            attempt_id=1,
            tenant_id="t",
            document_id=f"doc{n}",
            source_blob_get_url="http://unused",
            source_sha256="0" * 64,
            pages_to_process=[1],
            options={"engine": "pymupdf"},
        )
        jobs._run_backend_ocr(job_id, request, [content])
        assert jobs.get_backend_job(job_id)["status"] == "completed"

    threads = [threading.Thread(target=run, args=(n,)) for n in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)

    assert watching.peak == 2


# 3. Selective verification ---------------------------------------------------


def test_verify_all_pages_is_off_unless_asked(monkeypatch):
    monkeypatch.setattr(jobs, "_engine_cache", {})
    monkeypatch.delenv("AI1_VERIFY_ALL_PAGES", raising=False)
    monkeypatch.delenv("AI1_COST_MODE", raising=False)
    assert jobs._get_engine("mistral").verify_all_pages is False

    monkeypatch.setattr(jobs, "_engine_cache", {})
    monkeypatch.setenv("AI1_VERIFY_ALL_PAGES", "true")
    assert jobs._get_engine("mistral").verify_all_pages is True


def _decision(caplog) -> str:
    [line] = [r.getMessage() for r in caplog.records if "ocr.verify_decision" in r.getMessage()]
    return line


def test_a_clean_page_is_not_verified_and_says_so(tmp_path, caplog):
    verifier = FakeReader("unused")
    engine = VerifiedMistralOCREngine(
        FakeReader("\n".join(CLEAN_VN)), verifier, FakeArbiter("unused"), verify_all_pages=False
    )
    with caplog.at_level(logging.INFO):
        engine.recognize_page(
            _page(["DIEU 4. YEU CAU CHAT LUONG VA NGHIEM THU", PARA, PARA_2]),
            Context(document_id="doc", page=1, output_dir=str(tmp_path)),
        )

    assert verifier.calls == 0
    assert "page=1 verified=False reasons=-" in _decision(caplog)


def test_a_page_with_a_critical_field_is_verified_and_says_why(tmp_path, caplog):
    verifier = FakeReader(MONEY)
    engine = VerifiedMistralOCREngine(
        FakeReader(MONEY_VN), verifier, FakeArbiter("unused"), verify_all_pages=False
    )
    with caplog.at_level(logging.INFO):
        engine.recognize_page(
            _page([MONEY]), Context(document_id="doc", page=2, output_dir=str(tmp_path))
        )

    assert verifier.calls == 1
    assert "page=2 verified=True" in _decision(caplog)
    assert "critical" in _decision(caplog)


# 4. 429 retries ----------------------------------------------------------------

_OCR_RESPONSE = {
    "pages": [
        {"index": 0, "markdown": "Điều 1. Phạm vi", "images": [], "dimensions": None},
    ],
    "model": "mistral-ocr-2512",
    "usage_info": {"pages_processed": 1},
}


def _mistral_with(monkeypatch, responses: list[httpx.Response]) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return responses[min(len(seen), len(responses)) - 1]

    from mistralai.client import Mistral

    def build(**kwargs):
        return Mistral(client=httpx.Client(transport=httpx.MockTransport(handler)), **kwargs)

    monkeypatch.setattr("mistralai.client.Mistral", build)
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key-not-real")
    return seen


def test_a_429_is_retried_after_the_server_s_retry_after(monkeypatch, tmp_path):
    limited = httpx.Response(429, headers={"Retry-After": "0"}, json={"message": "rate limited"})
    seen = _mistral_with(
        monkeypatch,
        [limited, limited, httpx.Response(200, json=_OCR_RESPONSE)],
    )
    engine = mistral_ocr.MistralOCREngine(model="mistral-ocr-2512")

    result = engine.recognize_page(
        np.full((40, 40, 3), 255, dtype=np.uint8),
        Context(document_id="doc", page=1, output_dir=str(tmp_path)),
    )

    assert len(seen) == 3
    assert result.raw_markdown == "Điều 1. Phạm vi"


def test_retries_stop_after_the_configured_time(monkeypatch, tmp_path):
    monkeypatch.setenv("AI1_MISTRAL_RETRY_MAX_MS", "1")
    seen = _mistral_with(
        monkeypatch,
        [httpx.Response(429, headers={"Retry-After": "0"}, json={"message": "rate limited"})],
    )
    engine = mistral_ocr.MistralOCREngine(model="mistral-ocr-2512")

    with pytest.raises(Exception) as raised:
        engine.recognize_page(
            np.full((40, 40, 3), 255, dtype=np.uint8),
            Context(document_id="doc", page=1, output_dir=str(tmp_path)),
        )

    assert "429" in str(raised.value) or "rate" in str(raised.value).lower()
    assert 1 <= len(seen) <= 3


def test_backoff_has_jitter_and_a_cap():
    config = mistral_ocr._retry_config()

    assert config.strategy == "backoff"
    assert config.backoff.jitter_ms and config.backoff.jitter_ms > 0
    assert config.backoff.max_interval <= 8_000
    assert config.retry_connection_errors is True
    assert json.dumps(config.backoff.__dict__)  # plain numbers, loggable
