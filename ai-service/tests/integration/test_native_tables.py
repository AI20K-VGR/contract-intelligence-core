"""Section 9/19: a native (text-layer) page's table must be detected and every
cell must trace back to real geometry -- and a page that hasn't been checked
for tables must never look the same as one confirmed to have none."""

from pathlib import Path

import pymupdf
import pytest
from pydantic import ValidationError

from contract_ocr.application.use_cases.build_snapshot import BuildSnapshot
from contract_ocr.application.use_cases.classify_pdf import PdfPageClassifier
from contract_ocr.application.use_cases.process_document import ProcessDocument
from contract_ocr.domain.entities import Experiment, Line, OCRResult
from contract_ocr.domain.snapshot import SnapshotPage
from contract_ocr.infrastructure.image.preprocessing import ImagePreprocessor
from contract_ocr.infrastructure.image.renderer import PdfRenderer
from contract_ocr.infrastructure.pdf.pymupdf_extractor import PyMuPDFExtractor


def _bordered_table_pdf(path: Path) -> None:
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=400, height=300)
        rows_y = [50, 80, 110, 140]
        cols_x = [40, 140, 240, 340]
        shape = page.new_shape()
        for y in rows_y:
            shape.draw_line((cols_x[0], y), (cols_x[-1], y))
        for x in cols_x:
            shape.draw_line((x, rows_y[0]), (x, rows_y[-1]))
        shape.finish()
        shape.commit()
        data = [["STT", "Ten hang", "So luong"], ["1", "Hang A", "10"], ["2", "Hang B", "20"]]
        for r, row in enumerate(data):
            for c, val in enumerate(row):
                page.insert_text((cols_x[c] + 5, rows_y[r] + 20), val, fontsize=10)
        pdf.save(path)


def test_extractor_detects_native_table_with_measured_cell_geometry(tmp_path: Path):
    path = tmp_path / "table.pdf"
    _bordered_table_pdf(path)
    with pymupdf.open(path) as pdf:
        page = PyMuPDFExtractor().extract(pdf[0], "doc-1")

    assert len(page.tables) == 1
    table = page.tables[0]
    assert table.geometry_provenance == "MEASURED"
    assert table.bbox is not None
    assert table.header == ["STT", "Ten hang", "So luong"]
    assert [c.text for c in table.rows[0].cells] == ["1", "Hang A", "10"]
    assert [c.text for c in table.rows[1].cells] == ["2", "Hang B", "20"]
    for row in table.rows:
        for cell in row.cells:
            assert cell.bbox is not None
            assert cell.geometry_provenance == "MEASURED"


def test_snapshot_marks_native_table_detected_with_traceable_cells(tmp_path: Path):
    path = tmp_path / "table.pdf"
    _bordered_table_pdf(path)
    processor = ProcessDocument(
        PyMuPDFExtractor(), PdfRenderer(), ImagePreprocessor(), PdfPageClassifier()
    )
    document = processor.execute(
        str(path),
        "doc-1",
        Experiment(id="E1", engine="pymupdf"),
        None,
        tmp_path / "raw",
        "TEST",
        72,
    )
    snap = BuildSnapshot(PdfRenderer(), image_dpi=72).execute(
        document,
        snapshot_id="run-1",
        dossier_id="dossier-1",
        document_role="contract",
        filename="table.pdf",
        engine_name="pymupdf",
        engine_version="test",
        image_output_dir=tmp_path / "images",
        image_uri_prefix="storage://ocr/run-1",
    )
    page = snap.pages[0]
    assert page.table_status == "DETECTED"
    assert len(page.tables) == 1
    table = page.tables[0]
    assert table.header == ["STT", "Ten hang", "So luong"]
    assert len(table.rows) == 2
    for row in table.rows:
        for cell in row.cells:
            assert cell.bbox_normalized is not None
            assert cell.geometry_provenance == "MEASURED"
            x0, y0, x1, y1 = cell.bbox_normalized
            assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1


def test_text_layer_page_without_a_table_is_not_present_not_uncertain(
    synthetic_pdf: Path, tmp_path: Path
):
    processor = ProcessDocument(
        PyMuPDFExtractor(), PdfRenderer(), ImagePreprocessor(), PdfPageClassifier()
    )
    document = processor.execute(
        str(synthetic_pdf),
        "doc-1",
        Experiment(id="E1", engine="pymupdf"),
        None,
        tmp_path / "raw",
        "TEST",
        72,
    )
    snap = BuildSnapshot(PdfRenderer(), image_dpi=72).execute(
        document,
        snapshot_id="run-1",
        dossier_id="dossier-1",
        document_role="contract",
        filename="synthetic.pdf",
        engine_name="pymupdf",
        engine_version="test",
        image_output_dir=tmp_path / "images",
        image_uri_prefix="storage://ocr/run-1",
    )
    native_page = next(p for p in snap.pages if p.input_type == "TEXT_LAYER")
    assert native_page.table_status == "NOT_PRESENT"
    assert native_page.tables == []


def test_scanned_page_without_ruling_lines_is_not_present_not_failure(
    synthetic_pdf: Path, tmp_path: Path
):
    # A bordered-table detector now runs on every SCANNED_OCR/MIXED page too (see
    # test_scanned_tables.py for a real hit); this page's scanned image has no
    # ruling lines at all, so the honest result is NOT_PRESENT, not NOT_CHECKED.
    class FakeEngine:
        name, model, runtime_info = "MOCK", "MOCK", {}

        def recognize_page(self, page_image, context):
            return OCRResult(lines=[Line(line_id="mock", text="SYNTHETIC scanned page")])

    processor = ProcessDocument(
        PyMuPDFExtractor(), PdfRenderer(), ImagePreprocessor(), PdfPageClassifier()
    )
    document = processor.execute(
        str(synthetic_pdf),
        "doc-1",
        Experiment(id="E1", engine="mistral"),
        FakeEngine(),
        tmp_path / "raw",
        "TEST",
        72,
    )
    snap = BuildSnapshot(PdfRenderer(), image_dpi=72).execute(
        document,
        snapshot_id="run-1",
        dossier_id="dossier-1",
        document_role="contract",
        filename="synthetic.pdf",
        engine_name="pymupdf+MOCK",
        engine_version="test",
        image_output_dir=tmp_path / "images",
        image_uri_prefix="storage://ocr/run-1",
    )
    scanned_page = next(p for p in snap.pages if p.input_type == "SCANNED_OCR")
    assert scanned_page.table_status == "NOT_PRESENT"
    assert scanned_page.tables == []


def test_snapshot_page_rejects_inconsistent_table_status_and_tables():
    kwargs = dict(
        page_number=1,
        status="SUCCESS",
        input_type="TEXT_LAYER",
        source_page_width=1,
        source_page_height=1,
        text="x",
    )
    with pytest.raises(ValidationError):
        SnapshotPage(**kwargs, table_status="DETECTED", tables=[])
    with pytest.raises(ValidationError):
        SnapshotPage(
            **kwargs,
            table_status="NOT_PRESENT",
            tables=[
                {
                    "table_id": "t1",
                    "bbox_normalized": [0.1, 0.1, 0.5, 0.5],
                    "geometry_provenance": "MEASURED",
                    "rows": [],
                }
            ],
        )
