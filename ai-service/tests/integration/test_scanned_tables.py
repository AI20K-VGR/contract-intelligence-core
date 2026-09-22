"""Section 9/17: a scanned page's bordered table must be detected from pixels alone
and its cells filled from the OCR text the page's own engine already recognized --
without issuing any extra OCR calls per cell (see extract_scanned_tables.py)."""

from io import BytesIO
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw

from contract_ocr.application.use_cases.build_snapshot import BuildSnapshot
from contract_ocr.application.use_cases.classify_pdf import PdfPageClassifier
from contract_ocr.application.use_cases.process_document import ProcessDocument
from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import Context, Experiment, Line, OCRResult
from contract_ocr.infrastructure.image.preprocessing import ImagePreprocessor
from contract_ocr.infrastructure.image.renderer import PdfRenderer
from contract_ocr.infrastructure.pdf.pymupdf_extractor import PyMuPDFExtractor

ROWS_Y = [100, 200, 300, 400]
COLS_X = [80, 320, 560, 720]
CELL_TEXT = [
    ["STT", "Ten hang", "So luong"],
    ["1", "Hang A", "10"],
    ["2", "Hang B", "20"],
]


def _scanned_table_pdf(path: Path) -> None:
    """A raster (image-only) page -- no PDF vector ops, no native text layer --
    the same shape a real photographed/scanned page has."""
    canvas = Image.new("RGB", (800, 600), "white")
    draw = ImageDraw.Draw(canvas)
    for y in ROWS_Y:
        draw.line([(COLS_X[0], y), (COLS_X[-1], y)], fill="black", width=3)
    for x in COLS_X:
        draw.line([(x, ROWS_Y[0]), (x, ROWS_Y[-1])], fill="black", width=3)
    buffer = BytesIO()
    canvas.save(buffer, format="PNG")
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=canvas.width, height=canvas.height)
        page.insert_image(page.rect, stream=buffer.getvalue())
        pdf.save(path)


class _GridAwareEngine:
    """A stand-in OCR engine that "recognizes" one line per real cell of
    `CELL_TEXT`, each with the cell's own true bbox -- mirrors what a real
    line-granularity engine (Paddle) would report for single-line cell content,
    without needing PaddleOCR installed in this test environment."""

    name, model, runtime_info = "MOCK", "MOCK", {}

    def recognize_page(self, page_image, context: Context) -> OCRResult:
        lines = []
        for r, row in enumerate(CELL_TEXT):
            for c, text in enumerate(row):
                x0 = COLS_X[c]
                y0 = ROWS_Y[r]
                # A bit smaller than the full cell, like real single-line text
                # sitting inside a cell rather than touching its ruling lines.
                bbox = BBox.normalize(
                    [x0 + 10, y0 + 10, x0 + 60, y0 + 30], page_image.shape[1], page_image.shape[0]
                )
                lines.append(
                    Line(
                        line_id=f"l{r}{c}",
                        text=text,
                        bbox=bbox,
                        geometry_provenance="MEASURED",
                    )
                )
        return OCRResult(lines=lines)


def test_scanned_bordered_table_is_detected_with_cells_from_ocr_lines(tmp_path: Path):
    path = tmp_path / "scanned_table.pdf"
    _scanned_table_pdf(path)
    processor = ProcessDocument(
        PyMuPDFExtractor(), PdfRenderer(), ImagePreprocessor(), PdfPageClassifier()
    )
    document = processor.execute(
        str(path),
        "doc-1",
        Experiment(id="E1", engine="paddle"),
        _GridAwareEngine(),
        tmp_path / "raw",
        "TEST",
        72,
    )
    page = document.pages[0]
    assert len(page.tables) == 1
    table = page.tables[0]
    assert table.geometry_provenance == "MEASURED"
    assert table.header == CELL_TEXT[0]
    assert [c.text for c in table.rows[0].cells] == CELL_TEXT[1]
    assert [c.text for c in table.rows[1].cells] == CELL_TEXT[2]
    for row in table.rows:
        for cell in row.cells:
            assert cell.bbox is not None
            assert cell.geometry_provenance == "MEASURED"

    snap = BuildSnapshot(PdfRenderer(), image_dpi=72).execute(
        document,
        snapshot_id="run-1",
        dossier_id="dossier-1",
        document_role="contract",
        filename="scanned_table.pdf",
        engine_name="pymupdf+MOCK",
        engine_version="test",
        image_output_dir=tmp_path / "images",
        image_uri_prefix="storage://ocr/run-1",
    )
    snap_page = snap.pages[0]
    assert snap_page.table_status == "DETECTED"
    assert snap_page.tables[0].header == CELL_TEXT[0]
    for row in snap_page.tables[0].rows:
        for cell in row.cells:
            assert cell.bbox_normalized is not None
            assert cell.geometry_provenance == "MEASURED"


def test_empty_cell_gets_empty_text_not_a_crash(tmp_path: Path):
    # A cell with no OCR line landing inside it (a genuinely blank cell) must
    # come back as an empty string, not raise or silently drop the whole table.
    path = tmp_path / "scanned_table.pdf"
    _scanned_table_pdf(path)

    class SparseEngine:
        name, model, runtime_info = "MOCK", "MOCK", {}

        def recognize_page(self, page_image, context: Context) -> OCRResult:
            bbox = BBox.normalize(
                [COLS_X[0] + 10, ROWS_Y[0] + 10, COLS_X[0] + 60, ROWS_Y[0] + 30],
                page_image.shape[1],
                page_image.shape[0],
            )
            return OCRResult(
                lines=[Line(line_id="l1", text="STT", bbox=bbox, geometry_provenance="MEASURED")]
            )

    processor = ProcessDocument(
        PyMuPDFExtractor(), PdfRenderer(), ImagePreprocessor(), PdfPageClassifier()
    )
    document = processor.execute(
        str(path),
        "doc-1",
        Experiment(id="E1", engine="paddle"),
        SparseEngine(),
        tmp_path / "raw",
        "TEST",
        72,
    )
    table = document.pages[0].tables[0]
    assert table.header == ["STT", "", ""]
    assert table.rows[0].cells[0].text == ""
    assert table.rows[0].cells[0].bbox is not None  # geometry is real even when text isn't
