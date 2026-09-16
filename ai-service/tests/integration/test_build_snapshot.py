"""Acceptance checks mirroring handoff §6 (AI1-OCR-SNAPSHOT-HANDOFF.md) so a
regression here is caught before it reaches AI2."""

from pathlib import Path

import pymupdf
import pytest
from pydantic import ValidationError

from contract_ocr.application.ports.ocr_engine import OCREngine
from contract_ocr.application.use_cases.build_snapshot import BuildSnapshot
from contract_ocr.application.use_cases.classify_pdf import PdfPageClassifier
from contract_ocr.application.use_cases.process_document import ProcessDocument
from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import Context, Experiment, Line, OCRResult
from contract_ocr.domain.snapshot import DocumentSnapshot
from contract_ocr.infrastructure.image.preprocessing import ImagePreprocessor
from contract_ocr.infrastructure.image.renderer import PdfRenderer
from contract_ocr.infrastructure.pdf.pymupdf_extractor import PyMuPDFExtractor


class GroundedEngine(OCREngine):
    """Stands in for a future engine that returns line-level bbox + confidence,
    unlike today's DeepSeek/vision engines (see docs/OUTPUT_SCHEMA.md)."""

    name, model, runtime_info = "grounded-mock", "1.0", {}

    def recognize_page(self, page_image, context: Context) -> OCRResult:
        return OCRResult(
            lines=[
                Line(
                    line_id="mock",
                    text="SYNTHETIC scanned page",
                    confidence=0.95,
                    bbox=BBox(x1=0.1, y1=0.1, x2=0.9, y2=0.2),
                )
            ]
        )


class UngroundedEngine(OCREngine):
    """Stands in for today's DeepSeek path: text but no grounding geometry."""

    name, model, runtime_info = "ungrounded-mock", "1.0", {}

    def recognize_page(self, page_image, context: Context) -> OCRResult:
        return OCRResult(lines=[Line(line_id="mock", text="SYNTHETIC scanned page")])


def _process(pdf_path: Path, tmp_path: Path, engine: OCREngine | None):
    processor = ProcessDocument(
        PyMuPDFExtractor(), PdfRenderer(), ImagePreprocessor(), PdfPageClassifier()
    )
    return processor.execute(
        str(pdf_path),
        "contract-001",
        Experiment(id="E1", engine="paddle" if engine else "pymupdf"),
        engine,
        tmp_path / "raw",
        "TEST",
        72,
    )


def _build(document, tmp_path: Path, engine_name: str = "mock", engine_version: str = "1.0"):
    return BuildSnapshot(PdfRenderer(), image_dpi=72).execute(
        document,
        snapshot_id="ocr-run-1",
        dossier_id="dossier-001",
        document_role="contract",
        filename="hop-dong.pdf",
        engine_name=engine_name,
        engine_version=engine_version,
        image_output_dir=tmp_path / "images",
        image_uri_prefix="storage://ocr/ocr-run-1",
    )


def test_traceability_geometry_and_document_metadata(synthetic_pdf, tmp_path):
    document = _process(synthetic_pdf, tmp_path, GroundedEngine())
    snap = _build(document, tmp_path, "pymupdf+grounded-mock", "1.0")

    # (1) document -> page -> line -> character span -> word/line bbox is resolvable.
    for page in snap.pages:
        line_ids = {line.line_id for line in page.lines}
        word_ids = {word.word_id for word in page.words}
        for line in page.lines:
            assert set(line.word_ids) <= word_ids
            x0, y0, x1, y1 = line.bbox_normalized
            assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1
        for word in page.words:
            assert word.line_id in line_ids
            assert 0 <= word.line_char_start < word.line_char_end <= len(
                next(line_ for line_ in page.lines if line_.line_id == word.line_id).text
            )

    # (4) one TEXT_LAYER page and one SCANNED_OCR page share the same output shape.
    kinds = {page.input_type for page in snap.pages}
    assert kinds == {"TEXT_LAYER", "SCANNED_OCR"}
    field_sets = {tuple(sorted(page.model_dump().keys())) for page in snap.pages}
    assert len(field_sets) == 1

    # (7) engine/version, processing time, input type and source digest for audit.
    assert snap.engine.name and snap.engine.version
    assert snap.processing_ms >= 0
    assert snap.source_digest.startswith("sha256:")
    assert snap.input_type == "MIXED"

    # Round-trips through JSON exactly as AI2 will receive it.
    assert DocumentSnapshot.model_validate_json(snap.model_dump_json()) == snap


def test_missing_geometry_marks_partial_not_silent_success(synthetic_pdf, tmp_path):
    document = _process(synthetic_pdf, tmp_path, UngroundedEngine())
    snap = _build(document, tmp_path)
    scanned = next(p for p in snap.pages if p.input_type == "SCANNED_OCR")
    assert scanned.status == "PARTIAL"
    assert "missing_line_geometry" in scanned.warnings
    assert scanned.lines == [] and scanned.text.strip()  # text kept, geometry withheld


def test_skipped_page_becomes_failed_with_explicit_error(synthetic_pdf, tmp_path):
    document = _process(synthetic_pdf, tmp_path, None)
    snap = _build(document, tmp_path, "pymupdf", "1.28.2")
    scanned = next(p for p in snap.pages if p.page_number == 2)
    assert scanned.status == "FAILED"
    assert scanned.error and scanned.error.startswith("SKIPPED:")


def test_blank_page_is_success_with_warning_not_an_error(tmp_path):
    path = tmp_path / "blank.pdf"
    with pymupdf.open() as pdf:
        pdf.new_page(width=300, height=400)
        pdf.save(path)
    document = _process(path, tmp_path, None)
    snap = _build(document, tmp_path)
    page = snap.pages[0]
    assert page.status == "SUCCESS"
    assert page.warnings == ["blank_page"]
    assert page.error is None


def test_broken_page_load_does_not_drop_the_whole_document(synthetic_pdf, tmp_path):
    class BrokenRenderer(PdfRenderer):
        def render(self, page, dpi):
            if page.number == 0:
                raise RuntimeError("synthetic render failure")
            return super().render(page, dpi)

    document = _process(synthetic_pdf, tmp_path, None)
    snap = BuildSnapshot(BrokenRenderer(), image_dpi=72).execute(
        document,
        snapshot_id="ocr-run-1",
        dossier_id="dossier-001",
        document_role="contract",
        filename="hop-dong.pdf",
        engine_name="pymupdf",
        engine_version="1.28.2",
        image_output_dir=tmp_path / "images",
        image_uri_prefix="storage://ocr/ocr-run-1",
    )
    assert len(snap.pages) == 2
    assert snap.pages[0].status == "FAILED" and "RuntimeError" in snap.pages[0].error


def test_reocr_produces_a_new_snapshot_without_touching_the_old_one(synthetic_pdf, tmp_path):
    document = _process(synthetic_pdf, tmp_path, GroundedEngine())
    first = BuildSnapshot(PdfRenderer(), image_dpi=72).execute(
        document,
        snapshot_id="ocr-run-1",
        dossier_id="dossier-001",
        document_role="contract",
        filename="hop-dong.pdf",
        engine_name="grounded-mock",
        engine_version="1.0",
        image_output_dir=tmp_path / "run1",
        image_uri_prefix="storage://ocr/ocr-run-1",
    )
    second = BuildSnapshot(PdfRenderer(), image_dpi=72).execute(
        document,
        snapshot_id="ocr-run-2",
        dossier_id="dossier-001",
        document_role="contract",
        filename="hop-dong.pdf",
        engine_name="grounded-mock",
        engine_version="1.0",
        image_output_dir=tmp_path / "run2",
        image_uri_prefix="storage://ocr/ocr-run-2",
    )
    assert first.snapshot_id != second.snapshot_id
    assert first.document_id == second.document_id == "contract-001"
    assert (tmp_path / "run1" / "page-001.png").exists()
    assert (tmp_path / "run2" / "page-001.png").exists()


def test_bbox_normalized_rejects_out_of_order_or_out_of_range_boxes():
    from contract_ocr.domain.snapshot import SnapshotLine

    SnapshotLine(
        line_id="l1", text="ok", page_char_start=0, page_char_end=2,
        bbox_normalized=[0.1, 0.1, 0.5, 0.5],
    )
    with pytest.raises(ValidationError):
        SnapshotLine(
            line_id="l1", text="bad", page_char_start=0, page_char_end=3,
            bbox_normalized=[0.5, 0.1, 0.1, 0.5],  # x0 > x1
        )
    with pytest.raises(ValidationError):
        SnapshotLine(
            line_id="l1", text="bad", page_char_start=0, page_char_end=3,
            bbox_normalized=[0.1, 0.1, 1.5, 0.5],  # out of [0, 1]
        )


def test_page_status_error_consistency_is_enforced():
    from contract_ocr.domain.snapshot import SnapshotPage

    with pytest.raises(ValidationError):
        SnapshotPage(page_number=1, status="FAILED", input_type="TEXT_LAYER",
                     source_page_width=1, source_page_height=1)  # FAILED needs error
    with pytest.raises(ValidationError):
        SnapshotPage(page_number=1, status="SUCCESS", input_type="TEXT_LAYER",
                     source_page_width=1, source_page_height=1, error="boom")
