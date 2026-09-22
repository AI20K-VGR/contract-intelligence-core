"""Section 11/19: a real 2-page document with one table split across the page break
must come out of BuildSnapshot with a MERGE-decision continuity link between the two
page-level tables -- and the link must reference real table_ids the snapshot itself
emits, so it is actually resolvable, not just internally consistent."""

from pathlib import Path

import pymupdf

from contract_ocr.application.use_cases.build_snapshot import BuildSnapshot
from contract_ocr.application.use_cases.classify_pdf import PdfPageClassifier
from contract_ocr.application.use_cases.process_document import ProcessDocument
from contract_ocr.domain.entities import Experiment
from contract_ocr.infrastructure.image.preprocessing import ImagePreprocessor
from contract_ocr.infrastructure.image.renderer import PdfRenderer
from contract_ocr.infrastructure.pdf.pymupdf_extractor import PyMuPDFExtractor

HEADER = ["STT", "Ten hang", "So luong"]


def _bordered_table(page, rows_y: list[float], cols_x: list[float], data: list[list[str]]) -> None:
    shape = page.new_shape()
    for y in rows_y:
        shape.draw_line((cols_x[0], y), (cols_x[-1], y))
    for x in cols_x:
        shape.draw_line((x, rows_y[0]), (x, rows_y[-1]))
    shape.finish()
    shape.commit()
    for r, row in enumerate(data):
        for c, val in enumerate(row):
            page.insert_text((cols_x[c] + 5, rows_y[r] + 15), val, fontsize=9)


def _split_table_pdf(path: Path) -> None:
    with pymupdf.open() as pdf:
        # Page 1: table's own header + one data row, sitting at the page's bottom edge.
        page1 = pdf.new_page(width=400, height=300)
        _bordered_table(
            page1,
            rows_y=[240, 260, 280],
            cols_x=[40, 140, 240, 340],
            data=[HEADER, ["1", "Hang A", "10"]],
        )
        # Page 2: continuation -- same column count, repeats the identical header,
        # sitting at the page's top edge (the layout signature link_continuities looks for).
        page2 = pdf.new_page(width=400, height=300)
        _bordered_table(
            page2,
            rows_y=[20, 40, 60],
            cols_x=[40, 140, 240, 340],
            data=[HEADER, ["2", "Hang B", "20"]],
        )
        pdf.save(path)


def test_split_table_across_a_page_break_gets_a_merge_link_with_real_table_ids(
    tmp_path: Path,
):
    path = tmp_path / "split_table.pdf"
    _split_table_pdf(path)
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
        filename="split_table.pdf",
        engine_name="pymupdf",
        engine_version="test",
        image_output_dir=tmp_path / "images",
        image_uri_prefix="storage://ocr/run-1",
    )
    assert len(snap.table_continuity) == 1
    link = snap.table_continuity[0]
    assert link.decision == "MERGE"
    assert "REPEATED_TABLE_HEADER" in link.reason_codes

    all_table_ids = {table.table_id for page in snap.pages for table in page.tables}
    assert link.from_table_id in all_table_ids
    assert link.to_table_id in all_table_ids
    assert link.from_page == 1 and link.to_page == 2
