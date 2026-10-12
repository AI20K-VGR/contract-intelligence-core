"""Pages are streamed to OCR: memory stays bounded whatever the document length."""

from __future__ import annotations

import threading
from io import BytesIO

import pymupdf
import pytest
from PIL import Image, ImageDraw

from contract_ocr.application.ports.ocr_engine import OCREngine
from contract_ocr.application.use_cases.classify_pdf import PdfPageClassifier
from contract_ocr.application.use_cases.process_document import (
    LowQualityDocument,
    ProcessDocument,
)
from contract_ocr.domain.entities import Context, Experiment, Line, OCRResult
from contract_ocr.domain.enums import Status
from contract_ocr.infrastructure import backend_ocr_job as jobs
from contract_ocr.infrastructure.image.preprocessing import ImagePreprocessor
from contract_ocr.infrastructure.image.renderer import PdfRenderer
from contract_ocr.infrastructure.pdf.pymupdf_extractor import PyMuPDFExtractor

WAIT = 20  # seconds; a deadlock fails the test instead of hanging the run


def _sheet(text: str) -> bytes:
    image = Image.new("RGB", (600, 800), (245, 245, 245))
    ImageDraw.Draw(image).text((60, 120), text, fill=(20, 20, 20))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _scan(tmp_path, sheets: list[str]) -> str:
    """An image-only PDF; equal strings give pixel-identical pages."""
    path = tmp_path / "scan.pdf"
    with pymupdf.open() as pdf:
        for text in sheets:
            pdf.new_page(width=300, height=400).insert_image(
                pymupdf.Rect(0, 0, 300, 400), stream=_sheet(text)
            )
        pdf.save(path)
    return str(path)


class CountingRenderer(PdfRenderer):
    def __init__(self) -> None:
        self.calls = 0
        self.lock = threading.Lock()

    def render(self, page, dpi=300):
        with self.lock:
            self.calls += 1
        return super().render(page, dpi)


class GatedEngine(OCREngine):
    """Blocks every call until `release` is set; records the pages it read."""

    name, model, runtime_info = "gated-mock", "1.0", {}

    def __init__(self) -> None:
        self.release = threading.Event()
        self.started = threading.Semaphore(0)
        self.pages: list[int] = []
        self.lock = threading.Lock()

    def recognize_page(self, page_image, context: Context) -> OCRResult:
        with self.lock:
            self.pages.append(context.page)
        self.started.release()
        assert self.release.wait(WAIT), "engine was never released"
        return OCRResult(
            lines=[
                Line(
                    line_id=f"{context.document_id}-p{context.page:03d}-l0001",
                    text=f"Điều {context.page}. Nội dung",
                )
            ]
        )


def _processor(renderer, quality=None) -> ProcessDocument:
    return ProcessDocument(
        PyMuPDFExtractor(), renderer, ImagePreprocessor(), PdfPageClassifier(), quality=quality
    )


def _run_in_thread(target):
    outcome: dict = {}

    def run():
        try:
            outcome["result"] = target()
        except BaseException as exc:  # noqa: BLE001 - surfaced to the test thread
            outcome["error"] = exc

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, outcome


def _execute(processor, path, engine, tmp_path, max_workers, **kwargs):
    return processor.execute(
        path,
        "doc",
        Experiment(id="E1", engine="mistral"),
        engine,
        tmp_path / "raw",
        "TEST",
        72,
        max_workers=max_workers,
        **kwargs,
    )


def test_at_most_max_workers_pages_are_rendered_for_ocr_at_once(tmp_path):
    pages = 10
    renderer, engine = CountingRenderer(), GatedEngine()
    path = _scan(tmp_path, [f"Dieu {n}. Pham vi" for n in range(pages)])
    thread, outcome = _run_in_thread(
        lambda: _execute(_processor(renderer), path, engine, tmp_path, max_workers=3)
    )

    for _ in range(3):
        assert engine.started.acquire(timeout=WAIT)
    # Every slot is taken by a page stuck in OCR: the survey rendered each page
    # once, and only 3 more renders were let through for OCR.
    assert not engine.started.acquire(timeout=0.5)
    assert renderer.calls == pages + 3

    engine.release.set()
    thread.join(WAIT)
    assert not thread.is_alive() and "error" not in outcome
    document = outcome["result"]
    assert renderer.calls == 2 * pages
    assert sorted(engine.pages) == list(range(1, pages + 1))
    assert [page.status for page in document.pages] == [Status.SUCCESS] * pages


def test_duplicates_wait_for_their_source_without_holding_a_slot(tmp_path):
    # Two sheets, each repeated: 6 pages, 2 OCR calls, and fewer slots than pages.
    sheets = ["Dieu 1. A", "Dieu 2. B", "Dieu 1. A", "Dieu 2. B", "Dieu 1. A", "Dieu 2. B"]
    engine = GatedEngine()
    engine.release.set()
    path = _scan(tmp_path, sheets)
    thread, outcome = _run_in_thread(
        lambda: _execute(_processor(CountingRenderer()), path, engine, tmp_path, max_workers=2)
    )

    thread.join(WAIT)
    assert not thread.is_alive(), "deadlock between a duplicate and its source page"
    assert "error" not in outcome
    document = outcome["result"]
    assert sorted(engine.pages) == [1, 2]
    for page in document.pages[2:]:
        source = 1 if page.page_number % 2 else 2
        assert f"ocr:reused_reading_of_p{source}" in page.warnings
        assert page.lines[0].text == f"Điều {source}. Nội dung"


class PoorEverywhere:
    def assess(self, image, dpi) -> list[str]:
        return ["blurred"]


def test_a_poor_scan_is_refused_before_any_page_is_rendered_for_ocr(tmp_path):
    renderer, engine = CountingRenderer(), GatedEngine()
    path = _scan(tmp_path, [f"Dieu {n}. Pham vi" for n in range(4)])

    with pytest.raises(LowQualityDocument):
        _execute(_processor(renderer, PoorEverywhere()), path, engine, tmp_path, max_workers=3)

    assert engine.pages == []
    assert renderer.calls == 4  # the survey only


def test_progress_rises_one_page_at_a_time(tmp_path):
    engine = GatedEngine()
    engine.release.set()
    calls: list[tuple[int, int]] = []
    path = _scan(tmp_path, [f"Dieu {n}. Pham vi" for n in range(6)])

    _execute(
        _processor(CountingRenderer()),
        path,
        engine,
        tmp_path,
        max_workers=3,
        on_page_done=lambda done, total: calls.append((done, total)),
    )

    assert calls == [(n, 6) for n in range(1, 7)]


def test_the_backend_job_reports_progress_page_by_page(tmp_path, monkeypatch):
    path = tmp_path / "text.pdf"
    with pymupdf.open() as pdf:
        for n in range(1, 6):
            pdf.new_page().insert_text((72, 100), f"Trang {n} - Dieu {n}", fontsize=11)
        pdf.save(path)
    content = path.read_bytes()
    progress: list[int] = []
    real_update = jobs.update_backend_job

    def record(job_id, **changes):
        if "progress_pct" in changes:
            progress.append(changes["progress_pct"])
        real_update(job_id, **changes)

    monkeypatch.setattr(jobs, "update_backend_job", record)
    monkeypatch.setattr(jobs, "read_source_blob", lambda url, sha256: content)
    job_id, _ = jobs.new_backend_job("ocr")
    request = jobs.BackendOcrJobRequest(
        task_id=1,
        attempt_id=1,
        tenant_id="t",
        document_id="doc",
        source_blob_get_url="http://unused",
        source_sha256="0" * 64,
        pages_to_process=[1, 2, 3, 4, 5],
        options={"engine": "pymupdf"},
    )

    jobs._run_backend_ocr(job_id, request)

    assert jobs.get_backend_job(job_id)["status"] == "completed"
    assert progress == [5, 15, 28, 41, 54, 67, 80, 80, 100]
