import json
from io import BytesIO

import numpy as np
import pymupdf
from PIL import Image, ImageDraw

from contract_ocr.application.ports.ocr_engine import OCREngine
from contract_ocr.application.use_cases.classify_pdf import PdfPageClassifier
from contract_ocr.application.use_cases.process_document import ProcessDocument
from contract_ocr.cli.main import main
from contract_ocr.domain.entities import Experiment, Line, OCRResult
from contract_ocr.infrastructure.image.preprocessing import ImagePreprocessor
from contract_ocr.infrastructure.image.renderer import PdfRenderer
from contract_ocr.infrastructure.pdf.pymupdf_extractor import PyMuPDFExtractor


class FakeEngine(OCREngine):
    name = "MOCK"
    model = "MOCK"
    runtime_info = {}

    def recognize_page(self, page_image, context):
        return OCRResult(lines=[Line(line_id="mock", text="SYNTHETIC scanned page")])


def test_native_routing_and_ocr(synthetic_pdf, tmp_path):
    processor = ProcessDocument(
        PyMuPDFExtractor(), PdfRenderer(), ImagePreprocessor(), PdfPageClassifier()
    )
    result = processor.execute(
        str(synthetic_pdf),
        "SYNTHETIC",
        Experiment(id="E1", engine="mistral"),
        FakeEngine(),
        tmp_path / "raw",
        "TEST",
        72,
    )
    assert [p.engine for p in result.pages] == ["pymupdf", "MOCK"]
    assert all(p.status == "SUCCESS" for p in result.pages)
    assert result.pages[0].lines[0].words[0].bbox is not None
    assert not result.pages[1].geometry_available


def _mixed_page_pdf(tmp_path):
    """One page with a usable native text layer *and* a full-page image on top of
    it — the section-3 case a native-only reader must not silently collapse to."""
    path = tmp_path / "mixed.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=300, height=400)
        page.insert_text((25, 50), "SYNTHETIC contract for OCR testing only.")
        page.insert_text((25, 75), "Amount 100000000. Date 15/09/2026.")
        image = Image.new("RGB", (300, 400), "white")
        ImageDraw.Draw(image).text((20, 200), "stamp overlay", fill="black")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        page.insert_image(page.rect, stream=buffer.getvalue())
        pdf.save(path)
    return path


def test_mixed_page_is_ocred_not_silently_read_native_only(tmp_path):
    processor = ProcessDocument(
        PyMuPDFExtractor(), PdfRenderer(), ImagePreprocessor(), PdfPageClassifier()
    )
    result = processor.execute(
        str(_mixed_page_pdf(tmp_path)),
        "MIXED_DOC",
        Experiment(id="E1", engine="mistral"),
        FakeEngine(),
        tmp_path / "raw",
        "TEST",
        72,
    )
    page = result.pages[0]
    assert page.evidence.input_type == "MIXED"
    assert page.evidence.requires_ocr_regions is True
    # Must have gone through the OCR engine, not the pymupdf native-only fast path.
    assert page.engine == "MOCK"
    assert page.lines[0].text == "SYNTHETIC scanned page"


def test_mixed_page_without_an_engine_is_skipped_with_a_distinct_reason(tmp_path):
    processor = ProcessDocument(
        PyMuPDFExtractor(), PdfRenderer(), ImagePreprocessor(), PdfPageClassifier()
    )
    result = processor.execute(
        str(_mixed_page_pdf(tmp_path)),
        "MIXED_DOC",
        Experiment(id="E1", engine="pymupdf"),
        None,
        tmp_path / "raw",
        "TEST",
        72,
    )
    page = result.pages[0]
    assert page.status == "SKIPPED"
    assert page.evidence is not None and page.evidence.input_type == "MIXED"
    assert "heavy image overlay" in page.error
    assert page.error != "No usable native text layer"


def test_rotated_native_geometry(synthetic_pdf):
    extractor = PyMuPDFExtractor()
    with extractor.open(str(synthetic_pdf)) as pdf:
        page = pdf[0]
        page.set_rotation(90)
        result = extractor.extract(page, "TEST")
        word = page.get_text("words", sort=True)[0]
        expected = pymupdf.Rect(word[:4]) * page.rotation_matrix
        actual = result.lines[0].words[0].bbox
        assert np.isclose(actual.x1, expected.x0 / page.rect.width)
        assert result.rotation == 90 and result.width == 400


def test_benchmark_cli_reports_and_skips(manifest, tmp_path):
    output = tmp_path / "report"
    code = main(
        [
            "benchmark",
            "--manifest",
            str(manifest),
            "--engines",
            "pymupdf",
            "--output",
            str(output),
        ]
    )
    assert code == 0
    for name in [
        "config.json",
        "environment.json",
        "metrics_by_sample.csv",
        "metrics_summary.csv",
        "failures.csv",
        "summary.md",
        "failure_analysis.md",
    ]:
        assert (output / name).exists()
    data = json.loads((output / "predictions/SYNTHETIC/E0/output.json").read_text())
    assert data["pages"][0]["status"] == "SUCCESS"
    assert data["pages"][1]["status"] == "SKIPPED"
    assert "n=" in (output / "summary.md").read_text()
    assert (
        main(
            [
                "visualize",
                "--prediction",
                str(output / "predictions/SYNTHETIC/E0/output.json"),
                "--output",
                str(tmp_path / "overlay.png"),
            ]
        )
        == 0
    )


def test_page_exception_continues(synthetic_pdf, tmp_path):
    class BrokenRenderer(PdfRenderer):
        def render(self, page, dpi):
            raise RuntimeError("synthetic render failure")

    processor = ProcessDocument(
        PyMuPDFExtractor(), BrokenRenderer(), ImagePreprocessor(), PdfPageClassifier()
    )
    with pymupdf.open(synthetic_pdf) as pdf:
        pdf.new_page().insert_text((30, 50), "Another synthetic native text page with enough words")
        path = tmp_path / "three.pdf"
        pdf.save(path)
    result = processor.execute(
        str(path),
        "TEST",
        Experiment(id="E1", engine="mistral"),
        FakeEngine(),
        tmp_path / "raw",
        "TEST",
        72,
    )
    assert [p.status for p in result.pages] == ["SUCCESS", "FAILED", "SUCCESS"]


def test_generator(synthetic_pdf, tmp_path):
    output = tmp_path / "data/generated"
    assert (
        main(
            [
                "generate-degraded",
                "--file",
                str(synthetic_pdf),
                "--root",
                str(tmp_path),
                "--output",
                str(output),
                "--variants",
                "dpi150,rotation+2",
            ]
        )
        == 0
    )
    generated = list(output.rglob("*.pdf"))
    assert len(generated) == 4
    with pymupdf.open(generated[0]) as pdf:
        assert not pdf[0].get_text().strip()
    assert next(output.rglob("generation.json")).exists()
