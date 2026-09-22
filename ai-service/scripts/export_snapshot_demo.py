"""Produces a complete, runnable example of the ai1.snapshot.v1 handoff package:
one synthetic dossier with a contract (TEXT_LAYER) and an annex (SCANNED_OCR),
their OCR snapshots, page images, and a dossier manifest — matching every item
in AI1-OCR-SNAPSHOT-HANDOFF.md §1.

Output is clearly labeled SYNTHETIC smoke data, never real benchmark evidence or
a real contract (see scripts/create_synthetic_demo.py for the same convention).
Nothing under data/generated/ is committed (see .gitignore / CONTRIBUTING.md).
"""

from pathlib import Path

import pymupdf

from contract_ocr.application.ports.ocr_engine import OCREngine
from contract_ocr.application.use_cases.build_snapshot import BuildSnapshot, build_dossier_manifest
from contract_ocr.application.use_cases.classify_pdf import PdfPageClassifier
from contract_ocr.application.use_cases.process_document import ProcessDocument
from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import Context, Experiment, Line, OCRResult
from contract_ocr.infrastructure.image.preprocessing import ImagePreprocessor
from contract_ocr.infrastructure.image.renderer import PdfRenderer
from contract_ocr.infrastructure.pdf.pymupdf_extractor import PyMuPDFExtractor
from contract_ocr.infrastructure.reporting import write_json

OUTPUT_ROOT = Path("data/generated/synthetic_demo_dossier").resolve()
DOSSIER_ID = "dossier-001"
CONTRACT_LINES = [
    "SYNTHETIC HOP DONG MUA BAN SO 001/2026/HDMB",
    "Dieu 1. Gia tri hop dong",
    "Gia tri hop dong la 300.000.000.000 VND.",
]
ANNEX_LINES = [
    "SYNTHETIC PHU LUC 01 - BANG GIA CHI TIET",
    "Muc 1: 300.000.000.000 VND",
]


class ReplayStubEngine(OCREngine):
    """Deterministic stand-in used only to make this demo dossier runnable without
    a real OCR engine installed: it replays the exact text/bbox baked into the
    synthetic scan (computed below from the pre-rasterized source page) instead of
    performing recognition. Mirrors today's real Paddle path: line-level bbox and
    confidence, no fabricated word-level geometry. Never wire this into production."""

    name, model, runtime_info = "demo-replay-stub", "0.0", {}

    def __init__(self, lines_with_bbox: list[tuple[str, BBox]]) -> None:
        self._lines = lines_with_bbox

    def recognize_page(self, page_image, context: Context) -> OCRResult:
        return OCRResult(
            lines=[
                Line(
                    line_id=f"stub-l{i}",
                    text=text,
                    confidence=0.98,
                    bbox=box,
                    geometry_provenance="MEASURED",  # mirrors Paddle's own line detector
                )
                for i, (text, box) in enumerate(self._lines, 1)
            ]
        )


def _native_lines_with_bbox(
    width: float, height: float, lines: list[str]
) -> list[tuple[str, BBox]]:
    """Builds a one-page native PDF with `lines` drawn top-to-bottom and returns
    each line's text with its normalized bbox, read back from PyMuPDF's own word
    positions — i.e. exactly where we drew it, used as this demo's known-truth."""
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=width, height=height)
        y = 60
        for line in lines:
            page.insert_text((40, y), line, fontsize=14)
            y += 30
        extractor = PyMuPDFExtractor()
        extracted = extractor.extract(page, "scratch")
    return [(line.text, line.bbox) for line in extracted.lines]


def _build_contract(output_dir: Path) -> Path:
    path = output_dir / "hop-dong-mau.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=595, height=842)  # A4 points, matches handoff example
        y = 80
        for line in CONTRACT_LINES:
            page.insert_text((72, y), line, fontsize=14)
            y += 30
        pdf.save(path)
    return path


def _build_annex(output_dir: Path) -> tuple[Path, list[tuple[str, BBox]]]:
    width, height = 595, 842
    known = _native_lines_with_bbox(width, height, ANNEX_LINES)
    path = output_dir / "phu-luc-mau.pdf"
    with pymupdf.open() as source:
        page = source.new_page(width=width, height=height)
        y = 80
        for line in ANNEX_LINES:
            page.insert_text((72, y), line, fontsize=14)
            y += 30
        pixmap = page.get_pixmap(dpi=150)
        with pymupdf.open() as scanned:
            target = scanned.new_page(width=width, height=height)
            target.insert_image(target.rect, stream=pixmap.tobytes("png"))
            scanned.save(path)
    return path, known


def _process(pdf_path: Path, document_id: str, engine: OCREngine | None, raw_dir: Path):
    processor = ProcessDocument(
        PyMuPDFExtractor(), PdfRenderer(), ImagePreprocessor(), PdfPageClassifier()
    )
    return processor.execute(
        str(pdf_path),
        document_id,
        Experiment(id="demo", engine="paddle" if engine else "pymupdf"),
        engine,
        raw_dir,
        "demo-dossier",
        150,
    )


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=False)
    source_dir = OUTPUT_ROOT / "_source_pdfs"
    source_dir.mkdir()

    contract_path = _build_contract(source_dir)
    annex_path, annex_known = _build_annex(source_dir)

    contract_doc = _process(contract_path, "contract-001", None, OUTPUT_ROOT / "_raw")
    annex_doc = _process(
        annex_path, "annex-001", ReplayStubEngine(annex_known), OUTPUT_ROOT / "_raw"
    )

    builder = BuildSnapshot(PdfRenderer(), image_dpi=150)
    entries = [
        (contract_doc, "contract", "hop-dong-mau.pdf"),
        (annex_doc, "annex", "phu-luc-mau.pdf"),
    ]
    for document, role, filename in entries:
        doc_dir = OUTPUT_ROOT / DOSSIER_ID / document.document_id
        snapshot_id = f"ocr-run-demo-{document.document_id}-001"
        snapshot = builder.execute(
            document,
            snapshot_id=snapshot_id,
            dossier_id=DOSSIER_ID,
            document_role=role,
            filename=filename,
            engine_name="pymupdf" if role == "contract" else "pymupdf+demo-replay-stub",
            engine_version=pymupdf.VersionBind,
            image_output_dir=doc_dir / snapshot_id,
            image_uri_prefix=f"storage://ocr/{snapshot_id}",
        )
        write_json(doc_dir / f"{snapshot_id}.json", snapshot.model_dump(mode="json"))
        print(
            f"{document.document_id}: {snapshot.input_type}, {snapshot.page_count} page(s) -> "
            f"{(doc_dir / f'{snapshot_id}.json').resolve()}"
        )

    manifest = build_dossier_manifest(
        DOSSIER_ID,
        [
            ("contract-001", "hop-dong-mau.pdf", "contract"),
            ("annex-001", "phu-luc-mau.pdf", "annex"),
        ],
    )
    manifest_path = OUTPUT_ROOT / DOSSIER_ID / "dossier_manifest.json"
    write_json(manifest_path, manifest.model_dump(mode="json"))
    print(f"dossier manifest -> {manifest_path.resolve()}")


if __name__ == "__main__":
    main()
