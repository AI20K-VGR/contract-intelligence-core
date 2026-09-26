"""Blank, near-empty and duplicated pages are routed before any OCR call is paid."""

from io import BytesIO

import numpy as np
import pymupdf
from PIL import Image, ImageDraw

from contract_ocr.application.ports.ocr_engine import OCREngine
from contract_ocr.application.use_cases.build_snapshot import BuildSnapshot
from contract_ocr.application.use_cases.classify_pdf import PdfPageClassifier
from contract_ocr.application.use_cases.process_document import ProcessDocument
from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import Context, Experiment, Line, OCRResult
from contract_ocr.domain.enums import GeometryProvenance, InputType, Status
from contract_ocr.infrastructure.image.preprocessing import ImagePreprocessor
from contract_ocr.infrastructure.image.renderer import PdfRenderer
from contract_ocr.infrastructure.pdf.pymupdf_extractor import PyMuPDFExtractor

READING = [
    "Điều 2. Giá trị hợp đồng và phương thức thanh toán",
    "Tổng giá trị hợp đồng là 1.286.400.000 đồng, đã bao gồm thuế giá trị gia tăng.",
    "Bên A thanh toán cho Bên B bằng chuyển khoản trong vòng 15 ngày làm việc.",
]


class CountingEngine(OCREngine):
    name, model, runtime_info = "counting-mock", "1.0", {}

    def __init__(self, lines: list[str] = READING) -> None:
        self.lines, self.pages = lines, []

    def recognize_page(self, page_image, context: Context) -> OCRResult:
        self.pages.append(context.page)
        return OCRResult(
            lines=[
                Line(
                    line_id=f"{context.document_id}-p{context.page:03d}-l{i:04d}",
                    text=text,
                    bbox=BBox(x1=0.1, y1=0.1 * i, x2=0.9, y2=0.1 * i + 0.05),
                    geometry_provenance=GeometryProvenance.MEASURED,
                )
                for i, text in enumerate(self.lines, 1)
            ],
            warnings=[f"needs_review:critical:{context.document_id}-p{context.page:03d}-l0002"],
        )


def _scan(page: pymupdf.Page, draw=None) -> None:
    image = Image.new("RGB", (600, 800), (245, 245, 245))
    if draw:
        draw(ImageDraw.Draw(image))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    page.insert_image(page.rect, stream=buffer.getvalue())


def _pdf(tmp_path, build) -> str:
    path = tmp_path / "routing.pdf"
    with pymupdf.open() as pdf:
        build(pdf)
        pdf.save(path)
    return str(path)


def _process(path: str, tmp_path, engine: OCREngine | None):
    processor = ProcessDocument(
        PyMuPDFExtractor(), PdfRenderer(), ImagePreprocessor(), PdfPageClassifier()
    )
    return processor.execute(
        path, "doc", Experiment(id="E1", engine="mistral"), engine, tmp_path / "raw", "TEST", 72
    )


def _snapshot(document, tmp_path):
    return BuildSnapshot(PdfRenderer(), image_dpi=72).execute(
        document,
        snapshot_id="run-1",
        dossier_id="dossier-1",
        document_role="contract",
        filename="routing.pdf",
        engine_name="mock",
        engine_version="1.0",
        image_output_dir=tmp_path / "images",
        image_uri_prefix="storage://ocr/run-1",
    )


def test_blank_pages_are_success_without_an_ocr_call(tmp_path):
    def build(pdf):
        pdf.new_page(width=300, height=400)  # empty PDF page

        def specks(draw):
            for x, y in ((100, 200), (400, 600), (250, 90)):
                draw.point((x, y), fill=(40, 40, 40))

        _scan(pdf.new_page(width=300, height=400), specks)  # scanned blank sheet

    engine = CountingEngine()
    document = _process(_pdf(tmp_path, build), tmp_path, engine)
    assert engine.pages == []
    assert [(p.status, p.warnings) for p in document.pages] == [
        (Status.SUCCESS, ["blank_page"]),
        (Status.SUCCESS, ["blank_page"]),
    ]
    snapshot = _snapshot(document, tmp_path)
    assert [(p.status, p.warnings) for p in snapshot.pages] == [
        ("SUCCESS", ["blank_page"]),
        ("SUCCESS", ["blank_page"]),
    ]


def test_short_native_text_covering_all_ink_is_read_natively(tmp_path):
    def build(pdf):
        pdf.new_page(width=300, height=400).insert_text((100, 200), "PHU LUC 01", fontsize=14)

    engine = CountingEngine()
    document = _process(_pdf(tmp_path, build), tmp_path, engine)
    page = document.pages[0]
    assert engine.pages == []
    assert page.input_type is InputType.TEXT_LAYER
    assert [line.text for line in page.lines] == ["PHU LUC 01"]
    assert "SHORT_TEXT_COVERS_ALL_INK" in page.evidence.reason_codes


def test_short_native_text_with_uncovered_ink_is_still_ocred(tmp_path):
    def build(pdf):
        page = pdf.new_page(width=300, height=400)
        page.insert_text((100, 60), "PHU LUC 01", fontsize=14)
        # Body "text" drawn as vector shapes: ink the text layer knows nothing of.
        for y in (150, 170, 190):
            for x in range(40, 250, 14):
                page.draw_rect(pymupdf.Rect(x, y, x + 9, y + 9), color=(0, 0, 0), fill=(0, 0, 0))

    engine = CountingEngine()
    document = _process(_pdf(tmp_path, build), tmp_path, engine)
    assert engine.pages == [1]
    assert document.pages[0].input_type is InputType.SCANNED


def test_identical_scanned_sheet_is_read_once_and_marked_duplicate(tmp_path):
    def text(draw):
        draw.text((40, 60), "SYNTHETIC scanned page", fill=(0, 0, 0))

    def build(pdf):
        _scan(pdf.new_page(width=300, height=400), text)
        _scan(pdf.new_page(width=300, height=400), text)

    engine = CountingEngine()
    document = _process(_pdf(tmp_path, build), tmp_path, engine)
    first, second = document.pages
    assert engine.pages == [1]
    assert [line.text for line in second.lines] == READING
    assert all("-p002-" in line.line_id for line in second.lines)
    assert "needs_review:critical:doc-p002-l0002" in second.warnings
    assert "ocr:reused_reading_of_p1" in second.warnings
    assert (first.duplicate_of, second.duplicate_of) == (None, 1)

    snapshot = _snapshot(document, tmp_path)
    assert "duplicate_of:p1" in snapshot.pages[1].warnings
    assert any(w.startswith("needs_review:critical:doc:s") for w in snapshot.pages[1].warnings)
    assert [node.page_start for node in snapshot.nodes] == [1]


def test_inked_page_without_readable_text_is_partial_not_failed(tmp_path):
    def build(pdf):
        _scan(
            pdf.new_page(width=300, height=400),
            lambda draw: draw.ellipse((200, 500, 400, 700), outline=(0, 0, 0), width=6),
        )

    document = _process(_pdf(tmp_path, build), tmp_path, CountingEngine(lines=[]))
    page = document.pages[0]
    assert page.status is Status.SUCCESS and "no_text_found" in page.warnings
    snapshot_page = _snapshot(document, tmp_path).pages[0]
    assert (snapshot_page.status, snapshot_page.warnings) == ("PARTIAL", ["no_text_found"])


def test_blank_detection_needs_no_engine(tmp_path):
    document = _process(_pdf(tmp_path, lambda pdf: pdf.new_page()), tmp_path, None)
    assert document.pages[0].status is Status.SUCCESS
    assert np.isclose(document.pages[0].width, 595)
