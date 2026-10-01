"""A poor scan is caught before any OCR call is paid for."""

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
from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import Context, Experiment, Line, OCRResult
from contract_ocr.domain.enums import GeometryProvenance
from contract_ocr.infrastructure.image.preprocessing import ImagePreprocessor
from contract_ocr.infrastructure.image.renderer import PdfRenderer
from contract_ocr.infrastructure.pdf.pymupdf_extractor import PyMuPDFExtractor


class CountingEngine(OCREngine):
    name, model, runtime_info = "counting-mock", "1.0", {}

    def __init__(self) -> None:
        self.contexts: list[Context] = []

    def recognize_page(self, page_image, context: Context) -> OCRResult:
        self.contexts.append(context)
        return OCRResult(
            lines=[
                Line(
                    line_id=f"{context.document_id}-p{context.page:03d}-l0001",
                    text=f"Điều {context.page}. Phạm vi công việc",
                    bbox=BBox(x1=0.1, y1=0.1, x2=0.9, y2=0.15),
                    geometry_provenance=GeometryProvenance.MEASURED,
                )
            ]
        )


class ScriptedQuality:
    """Reports the given reasons for the n-th page checked (pages are checked in order)."""

    def __init__(self, by_order: dict[int, list[str]]) -> None:
        self.by_order, self.checked = by_order, 0

    def assess(self, image, dpi) -> list[str]:
        self.checked += 1
        return self.by_order.get(self.checked, [])


def _pdf(tmp_path, pages: int) -> str:
    path = tmp_path / "scan.pdf"
    with pymupdf.open() as pdf:
        for number in range(1, pages + 1):
            image = Image.new("RGB", (600, 800), (245, 245, 245))
            # Different text on each sheet: identical sheets share one reading.
            ImageDraw.Draw(image).text(
                (60, 80 + number * 40), f"Dieu {number}. Pham vi", fill=(20, 20, 20)
            )
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            pdf.new_page(width=300, height=400).insert_image(
                pymupdf.Rect(0, 0, 300, 400), stream=buffer.getvalue()
            )
        pdf.save(path)
    return str(path)


def _process(path, tmp_path, engine, quality):
    processor = ProcessDocument(
        PyMuPDFExtractor(), PdfRenderer(), ImagePreprocessor(), PdfPageClassifier(), quality=quality
    )
    return processor.execute(
        path, "doc", Experiment(id="E1", engine="mistral"), engine, tmp_path / "raw", "TEST", 72
    )


def test_a_mostly_poor_scan_is_refused_without_any_ocr_call(tmp_path):
    engine = CountingEngine()
    quality = ScriptedQuality({1: ["blur"], 3: ["speckle", "noise"]})
    with pytest.raises(LowQualityDocument) as refused:
        _process(_pdf(tmp_path, 4), tmp_path, engine, quality)
    assert engine.contexts == []
    assert refused.value.pages == {1: ["blur"], 3: ["speckle", "noise"]}
    assert refused.value.ocr_pages == 4
    assert "rescan" in str(refused.value)


def test_a_few_poor_pages_are_read_once_and_flagged(tmp_path):
    engine = CountingEngine()
    document = _process(_pdf(tmp_path, 4), tmp_path, engine, ScriptedQuality({2: ["blur"]}))
    assert [(c.page, c.low_quality) for c in engine.contexts] == [
        (1, False),
        (2, True),
        (3, False),
        (4, False),
    ]
    poor = document.pages[1]
    assert "low_quality_scan:blur" in poor.warnings
    assert "LOW_QUALITY_SCAN" in poor.evidence.reason_codes
    assert all("low_quality_scan:blur" not in p.warnings for p in document.pages if p is not poor)


def test_without_a_quality_check_every_page_is_read_as_before(tmp_path):
    engine = CountingEngine()
    _process(_pdf(tmp_path, 3), tmp_path, engine, None)
    assert [(c.page, c.low_quality) for c in engine.contexts] == [
        (1, False),
        (2, False),
        (3, False),
    ]
