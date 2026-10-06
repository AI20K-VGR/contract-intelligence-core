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
from contract_ocr.domain.enums import GeometryProvenance, Status
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
    quality = ScriptedQuality({1: ["blur"], 3: ["speckle", "noise"], 5: ["low_contrast"]})
    with pytest.raises(LowQualityDocument) as refused:
        _process(_pdf(tmp_path, 6), tmp_path, engine, quality)
    assert engine.contexts == []
    assert refused.value.pages == {1: ["blur"], 3: ["speckle", "noise"], 5: ["low_contrast"]}
    assert refused.value.ocr_pages == 6
    assert "rescan" in str(refused.value)


def test_a_text_layer_contract_with_one_poor_scanned_page_is_still_read(tmp_path):
    # The common case: a born-digital contract whose only scan is the signed page.
    path = tmp_path / "contract.pdf"
    with pymupdf.open() as pdf:
        for number in range(1, 6):
            pdf.new_page(width=300, height=400).insert_text(
                (30, 60), f"Dieu {number}. Ben A va Ben B thoa thuan pham vi cong viec", fontsize=8
            )
        signed = Image.new("RGB", (600, 800), (245, 245, 245))
        ImageDraw.Draw(signed).text((60, 600), "DAI DIEN BEN A", fill=(20, 20, 20))
        buffer = BytesIO()
        signed.save(buffer, format="PNG")
        pdf.new_page(width=300, height=400).insert_image(
            pymupdf.Rect(0, 0, 300, 400), stream=buffer.getvalue()
        )
        pdf.save(path)
    engine = CountingEngine()
    document = _process(str(path), tmp_path, engine, ScriptedQuality({1: ["speckle"]}))
    assert [(c.page, c.low_quality) for c in engine.contexts] == [(6, True)]
    assert "low_quality_scan:speckle" in document.pages[5].warnings
    assert all(p.status == Status.SUCCESS for p in document.pages[:5])


def test_a_short_scan_is_read_even_when_every_page_is_poor(tmp_path):
    # 2 of 2 is 100%, but under the minimum number of poor pages.
    engine = CountingEngine()
    quality = ScriptedQuality({1: ["blur"], 2: ["blur"]})
    document = _process(_pdf(tmp_path, 2), tmp_path, engine, quality)
    assert [(c.page, c.low_quality) for c in engine.contexts] == [(1, True), (2, True)]
    assert all("low_quality_scan:blur" in p.warnings for p in document.pages)


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


class DiskWatchingEngine(CountingEngine):
    """Records how many page images are still waiting on disk at each OCR call."""

    def __init__(self, root) -> None:
        super().__init__()
        self.root, self.waiting, self.shapes = root, [], []

    def recognize_page(self, page_image, context: Context) -> OCRResult:
        self.waiting.append(len(list(self.root.rglob("*.npy"))))
        self.shapes.append(page_image.shape)
        return super().recognize_page(page_image, context)


def test_page_images_wait_on_disk_and_are_removed_once_read(tmp_path):
    engine = DiskWatchingEngine(tmp_path / "raw")
    document = _process(_pdf(tmp_path, 3), tmp_path, engine, None)

    # All three pages are rendered before the first OCR call; each image leaves
    # the disk as its page is read, so none is held in memory meanwhile.
    assert engine.waiting == [2, 1, 0]
    assert engine.shapes == [(400, 300, 3)] * 3
    assert [page.status for page in document.pages] == [Status.SUCCESS] * 3
    assert not list((tmp_path / "raw").rglob("*.npy"))
    assert not list((tmp_path / "raw").glob("page_images_*"))


def test_page_images_are_removed_when_the_document_is_refused(tmp_path):
    engine = CountingEngine()
    poor = ["blurred"]
    with pytest.raises(LowQualityDocument):
        _process(_pdf(tmp_path, 3), tmp_path, engine, ScriptedQuality({1: poor, 2: poor, 3: poor}))

    assert engine.contexts == []
    assert not list((tmp_path / "raw").rglob("*.npy"))
