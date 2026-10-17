"""ProcessDocument reports each finished page (issue #115), in order, from any thread."""

import random
import threading
import time
from io import BytesIO

import pymupdf
from PIL import Image, ImageDraw

from contract_ocr.application.ports.ocr_engine import OCREngine
from contract_ocr.application.use_cases.classify_pdf import PdfPageClassifier
from contract_ocr.application.use_cases.process_document import ProcessDocument
from contract_ocr.domain.entities import Experiment, Line, OCRResult
from contract_ocr.infrastructure.image.preprocessing import ImagePreprocessor
from contract_ocr.infrastructure.image.renderer import PdfRenderer
from contract_ocr.infrastructure.pdf.pymupdf_extractor import PyMuPDFExtractor


class SlowFakeEngine(OCREngine):
    """Finishes pages out of order, like 8 paid calls in flight would."""

    name = "MOCK"
    model = "MOCK"
    runtime_info = {}

    def recognize_page(self, page_image, context):
        time.sleep(random.uniform(0, 0.02))
        return OCRResult(lines=[Line(line_id=f"l{context.page}", text=f"page {context.page}")])


def _scan(text: str) -> bytes:
    image = Image.new("RGB", (300, 400), "white")
    ImageDraw.Draw(image).text((20, 30), text, fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _pdf(tmp_path, scanned: int):
    """One text-layer page, `scanned` distinct scans, then a copy of the first scan."""
    path = tmp_path / "progress.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=300, height=400)
        page.insert_text((25, 50), "SYNTHETIC contract with a text layer.")
        for n in range(scanned):
            pdf.new_page(width=300, height=400).insert_image(
                pymupdf.Rect(0, 0, 300, 400), stream=_scan(f"SYNTHETIC scanned page {n}")
            )
        pdf.new_page(width=300, height=400).insert_image(
            pymupdf.Rect(0, 0, 300, 400), stream=_scan("SYNTHETIC scanned page 0")
        )
        pdf.save(path)
    return path, scanned + 2


def _run(tmp_path, max_workers, on_page_done):
    path, total = _pdf(tmp_path, scanned=12)
    processor = ProcessDocument(
        PyMuPDFExtractor(), PdfRenderer(), ImagePreprocessor(), PdfPageClassifier(), quality=None
    )
    result = processor.execute(
        str(path),
        "SYNTHETIC",
        Experiment(id="E1", engine="mistral"),
        SlowFakeEngine(),
        tmp_path / "raw",
        "TEST",
        72,
        max_workers=max_workers,
        on_page_done=on_page_done,
    )
    return result, total


def test_every_page_is_reported_once_in_order_while_pages_run_in_parallel(tmp_path):
    reports = []
    threads = set()

    def on_page_done(done, total):
        reports.append((done, total))
        threads.add(threading.get_ident())

    result, total = _run(tmp_path, max_workers=4, on_page_done=on_page_done)

    assert len(result.pages) == total
    # text-layer page, 12 OCR'd pages, the duplicate copied from its twin
    assert [done for done, _ in reports] == list(range(1, total + 1))
    assert {t for _, t in reports} == {total}
    assert len(threads) > 1  # reports came from the OCR worker threads too


def test_progress_is_optional_and_a_failing_callback_never_fails_a_page(tmp_path):
    result, total = _run(tmp_path, max_workers=1, on_page_done=None)
    assert all(page.status == "SUCCESS" for page in result.pages)

    def broken(done, total):
        raise RuntimeError("progress sink down")

    again = tmp_path / "again"
    again.mkdir()
    result, total = _run(again, max_workers=4, on_page_done=broken)
    assert len(result.pages) == total
    assert all(page.status == "SUCCESS" for page in result.pages)
