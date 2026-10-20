"""Runnable end-to-end demo of the docs/architecture.md pipeline (see repo root
DOC-04 v0.2, sections 5-9 and 27): a Contract PDF plus 0..N Appendix PDFs go
through OCR (reusing the existing ai1.snapshot.v1 pipeline from
export_snapshot_demo.py) and then a minimal structure -> classification ->
fact -> citation -> conflict-detection layer, ending in a single
self-contained HTML report. No API server or database is involved; the
primary action is still "upload the contract" per section 27.11's Sprint-1
slice — appendices are additive (0..N), not a forced second required upload.

Fields extracted match section 27.11's MVP list (parties, amount, date,
payment term), plus a first-page-keyword document classification standing in
for section 27.2's "Classification" output row, and a signals-based
confidence object per fact/finding standing in for section 27.8. Deliberate
simplifications versus the full architecture (not production shortcuts, just
what a demo needs):
- Clause detection is a fixed "Dieu N." / "Khoan N." / "a)" regex 3-level
  hierarchy, not the rules+layout classifier described in section 8.1.
- Fact extraction is a handful of hand-picked regexes, not the typed
  extraction pipeline in section 8.3.
- Classification is first-page keyword sniffing, not the evidence-based
  classifier in section 27.2.
- Confidence is fixed signals (anchor precision) with no calibrated score, per
  section 27.8's own caution against treating an uncalibrated number as a
  probability.
- Candidate generation for comparison groups facts by `field` name instead of
  the keyword/embedding retrieval in section 9.2.
- Citation objects are embedded inline in the fact/finding JSON rather than
  resolved by id through a citation service (section 7.4) — there is no API or
  database in this demo.
- No table extraction (BuildSnapshot's tables[] is always empty — a disclosed
  gap in the underlying OCR snapshot pipeline itself, not something added
  here). Human review is an in-browser "Sua" action per fact (edits the
  rendered page only; nothing is saved anywhere) and there is no real
  evaluation report (no ground truth dataset is wired in) — both are called
  out again where they show up in the report.

Output is clearly SYNTHETIC data (see scripts/create_synthetic_demo.py for the
same convention): never a real contract, never benchmark evidence.

Run with no arguments for the built-in synthetic dossier, or point it at your
own PDF to try the same classification/fact/citation layer on real content:

    uv run python scripts/demo_ai2_pipeline.py --contract path/to/hop-dong.pdf

Add `--annex path/to/phu-luc.pdf` (repeatable — pass it more than once for
several appendices) only if you also want conflict detection against the
contract; it's optional. `--engine mistral` OCRs pages with no native text
layer (real scans) via Mistral's OCR endpoint; needs `MISTRAL_API_KEY` set
in the environment and `--extra mistral` installed.
Fact/heading regexes only recognize the "Dieu N." / "Ben A:" / dd/mm/yyyy /
"trong vong N ngay" / "N.NNN.NNN VND" style phrasing this demo was built
around (diacritics-insensitive) — a real contract with different wording will
still OCR and show up as clauses/facts=0, which is expected for this
deliberately small demo layer, not a pipeline failure.

The generated demo_report.html also has its own drag-and-drop PDF uploader
(scripts/demo_report_template.html): for a PDF with a native text layer, you
can skip the CLI entirely and drop it straight into the open report — analysis
runs automatically on drop, client-side, via a vendored pdf.js
(ai-service/frontend/vendor/pdfjs/), no server involved. Scanned PDFs still
need this script with --engine mistral, since OCR only exists in Python.
"""

import argparse
import base64
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pymupdf

from contract_ocr.application.ports.ocr_engine import OCREngine
from contract_ocr.application.use_cases.build_snapshot import BuildSnapshot
from contract_ocr.application.use_cases.classify_pdf import PdfPageClassifier
from contract_ocr.application.use_cases.extract_ai2_facts import (
    classify_document,
    compare_facts_multi,
    extract_clauses,
    extract_facts,
)
from contract_ocr.application.use_cases.process_document import ProcessDocument
from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import Context, Experiment, Line, OCRResult
from contract_ocr.domain.snapshot import DocumentSnapshot
from contract_ocr.infrastructure.image.preprocessing import ImagePreprocessor
from contract_ocr.infrastructure.image.renderer import PdfRenderer
from contract_ocr.infrastructure.pdf.pymupdf_extractor import PyMuPDFExtractor
from contract_ocr.infrastructure.reporting import write_json

OUTPUT_ROOT = Path("data/generated/demo_ai2_pipeline").resolve()
DOSSIER_ID = "demo-dossier-ai2"
PAGE_WIDTH, PAGE_HEIGHT = 595, 842  # A4 points

# Covers the MVP field set architecture.md section 27.11 asks for (parties,
# amount, date, payment term), plus one deliberate mismatch (payment term)
# so the demo still shows both `comparable_match` and `comparable_difference`
# from section 9.3. Party/date lines sit in the preamble, before "Dieu 1" —
# see extract_clauses()'s "Mo dau" pseudo-clause, which exists specifically so
# these lines aren't silently dropped. ASCII-only text (no Vietnamese
# diacritics) because pymupdf's base14 fonts can't render them, same
# convention as export_snapshot_demo.py.
CONTRACT_LINES = [
    "SYNTHETIC HOP DONG DICH VU SO 088/2026/HDDV",
    "Ben A: Cong ty TNHH Alpha",
    "Ben B: Cong ty TNHH Beta",
    "Hop dong ky ngay 01/03/2026",
    "Dieu 1. Gia tri hop dong",
    "Gia tri hop dong la 500.000.000 VND.",
    "Dieu 2. Thoi han thanh toan",
    "1. Ben B thanh toan trong vong 30 ngay ke tu ngay ky.",
    "a) Cham thanh toan qua 30 ngay bi tinh lai suat phat 0.05 phan tram/ngay.",
]
ANNEX_LINES = [
    "SYNTHETIC PHU LUC 01 - DIEU CHINH DIEU KHOAN",
    "Muc 1. Gia tri hop dong",
    "Gia tri hop dong la 500.000.000 VND.",
    "Muc 2. Thoi han thanh toan",
    "Ben B thanh toan trong vong 15 ngay ke tu ngay ky.",
]


class ReplayStubEngine(OCREngine):
    """Deterministic stand-in so this demo runs without a real OCR engine
    installed: replays the exact text/bbox baked into the synthetic scan
    (computed below from the pre-rasterized source page). Mirrors a generic
    line-level OCR engine's shape (line-level bbox and confidence, no word
    geometry) so the annex ends up with line-level citations only — see
    _citation() below. Never wire this into production. Copied from
    export_snapshot_demo.py."""

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
                    geometry_provenance="MEASURED",  # mirrors a real line-level detector
                )
                for i, (text, box) in enumerate(self._lines, 1)
            ]
        )


def _native_lines_with_bbox(lines: list[str]) -> list[tuple[str, "BBox"]]:
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        y = 80
        for line in lines:
            page.insert_text((72, y), line, fontsize=14)
            y += 30
        extracted = PyMuPDFExtractor().extract(page, "scratch")
    return [(line.text, line.bbox) for line in extracted.lines]


def _build_contract_pdf(output_dir: Path) -> Path:
    path = output_dir / "hop-dong-mau.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        y = 80
        for line in CONTRACT_LINES:
            page.insert_text((72, y), line, fontsize=14)
            y += 30
        pdf.save(path)
    return path


def _build_annex_pdf(output_dir: Path) -> tuple[Path, list[tuple[str, "BBox"]]]:
    known = _native_lines_with_bbox(ANNEX_LINES)
    path = output_dir / "phu-luc-mau.pdf"
    with pymupdf.open() as source:
        page = source.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        y = 80
        for line in ANNEX_LINES:
            page.insert_text((72, y), line, fontsize=14)
            y += 30
        pixmap = page.get_pixmap(dpi=150)
        with pymupdf.open() as scanned:
            target = scanned.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
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
        Experiment(id="demo", engine="mistral" if engine else "pymupdf"),
        engine,
        raw_dir,
        "demo-ai2",
        150,
    )


def _snapshot_for_document(
    document, role: str, filename: str, engine_name: str
) -> tuple[DocumentSnapshot, Path]:
    builder = BuildSnapshot(PdfRenderer(), image_dpi=150)
    doc_dir = OUTPUT_ROOT / DOSSIER_ID / document.document_id
    snapshot_id = f"ocr-run-demo-{document.document_id}-001"
    image_dir = doc_dir / snapshot_id
    snapshot = builder.execute(
        document,
        snapshot_id=snapshot_id,
        dossier_id=DOSSIER_ID,
        document_role=role,
        filename=filename,
        engine_name=engine_name,
        engine_version=pymupdf.VersionBind,
        image_output_dir=image_dir,
        image_uri_prefix=f"storage://ocr/{snapshot_id}",
    )
    write_json(doc_dir / f"{snapshot_id}.json", snapshot.model_dump(mode="json"))
    return snapshot, image_dir


SnapshotAndDir = tuple[DocumentSnapshot, Path]


def build_dossier_snapshots() -> dict[str, SnapshotAndDir | list[SnapshotAndDir]]:
    """Runs the existing OCR pipeline and returns {"contract": (snapshot, image_dir),
    "annexes": [(snapshot, image_dir), ...]}. Contract stays native (TEXT_LAYER,
    real word geometry); the one built-in annex is routed through the OCR stub
    (SCANNED_OCR, line geometry only) — same "native + scan" mix architecture.md
    asks the mentor demo to cover."""
    source_dir = OUTPUT_ROOT / "_source_pdfs"
    source_dir.mkdir(parents=True, exist_ok=True)

    contract_path = _build_contract_pdf(source_dir)
    annex_path, annex_known = _build_annex_pdf(source_dir)

    contract_doc = _process(contract_path, "contract-001", None, OUTPUT_ROOT / "_raw")
    annex_doc = _process(
        annex_path, "annex-001", ReplayStubEngine(annex_known), OUTPUT_ROOT / "_raw"
    )

    return {
        "contract": _snapshot_for_document(contract_doc, "contract", "hop-dong-mau.pdf", "pymupdf"),
        "annexes": [
            _snapshot_for_document(
                annex_doc, "annex", "phu-luc-mau.pdf", "pymupdf+demo-replay-stub"
            )
        ],
    }


def build_dossier_snapshots_from_files(
    contract_path: Path, annex_paths: list[Path], engine_choice: str
) -> dict[str, SnapshotAndDir | list[SnapshotAndDir]]:
    """Same OCR + snapshot pipeline as build_dossier_snapshots(), but on real
    PDF(s) you point it at instead of the built-in synthetic fixture. Every
    path in `annex_paths` (0..N) becomes its own appendix document."""
    engine = None
    engine_label = "pymupdf"
    if engine_choice == "mistral":
        from contract_ocr.infrastructure.ocr.mistral_ocr import MistralOCREngine

        engine = MistralOCREngine()
        engine_label = "pymupdf+mistral"

    raw_dir = OUTPUT_ROOT / "_raw"

    contract_doc = _process(contract_path, "contract-001", engine, raw_dir)
    contract_snapshot = _snapshot_for_document(
        contract_doc, "contract", contract_path.name, engine_label
    )

    annex_snapshots = []
    for index, annex_path in enumerate(annex_paths, start=1):
        annex_doc = _process(annex_path, f"annex-{index:03d}", engine, raw_dir)
        annex_snapshots.append(
            _snapshot_for_document(annex_doc, "annex", annex_path.name, engine_label)
        )

    return {"contract": contract_snapshot, "annexes": annex_snapshots}


# --------------------------------------------------------------------------
# Report assembly
# --------------------------------------------------------------------------


def _encode_page_images(snapshot: DocumentSnapshot, image_dir: Path) -> dict[str, str]:
    images = {}
    for page in snapshot.pages:
        png_path = image_dir / f"page-{page.page_number:03d}.png"
        if png_path.exists():
            encoded = base64.b64encode(png_path.read_bytes()).decode("ascii")
            images[f"{snapshot.document_id}:{page.page_number}"] = (
                f"data:image/png;base64,{encoded}"
            )
    return images


def _document_entry(role: str, snapshot: DocumentSnapshot, image_dir: Path) -> tuple[dict, dict]:
    clauses = extract_clauses(snapshot)
    facts = extract_facts(snapshot, clauses)
    entry = {
        "document_id": snapshot.document_id,
        "role": role,
        "filename": snapshot.filename,
        "input_type": snapshot.input_type,
        "engine": snapshot.engine.model_dump(),
        "page_count": snapshot.page_count,
        "classification": classify_document(snapshot),
        "clauses": clauses,
        "facts": facts,
    }
    return entry, _encode_page_images(snapshot, image_dir)


def build_report_payload(
    snapshots: dict[str, SnapshotAndDir | list[SnapshotAndDir]], *, synthetic: bool
) -> dict:
    documents = []
    images: dict[str, str] = {}

    contract_snapshot, contract_image_dir = snapshots["contract"]
    contract_entry, contract_images = _document_entry(
        "contract", contract_snapshot, contract_image_dir
    )
    documents.append(contract_entry)
    images.update(contract_images)

    annex_refs = []  # (document_id, filename, facts) for compare_facts_multi
    for annex_snapshot, annex_image_dir in snapshots.get("annexes", []):
        annex_entry, annex_images = _document_entry("annex", annex_snapshot, annex_image_dir)
        documents.append(annex_entry)
        images.update(annex_images)
        annex_refs.append(
            (annex_entry["document_id"], annex_entry["filename"], annex_entry["facts"])
        )

    findings = compare_facts_multi(contract_entry["facts"], annex_refs)
    disclaimer = (
        "SYNTHETIC DEMO du lieu tong hop - khong phai hop dong that, "
        "khong phai ket qua benchmark da do."
        if synthetic
        else (
            "DEMO PIPELINE tren file ban tai len - regex fact/clause chi nhan dien "
            "dung mau cau demo nay dung, khong phai ket qua extraction da benchmark."
        )
    )
    return {
        "dossier_id": DOSSIER_ID,
        "generated_at": datetime.now(UTC).isoformat(),
        "disclaimer": disclaimer,
        "documents": documents,
        "findings": findings,
        "images": images,
    }


TEMPLATE_PATH = Path(__file__).parent / "demo_report_template.html"
VENDOR_PDFJS_SRC = Path(__file__).parent.parent / "frontend" / "vendor" / "pdfjs"


def render_html_report(payload: dict, output_path: Path) -> None:
    """Renders scripts/demo_report_template.html with the dossier JSON inlined,
    and copies the vendored pdf.js build next to it (the template's browser
    upload feature loads it as a relative `vendor/pdfjs/...` script, so the
    output folder must be self-contained/portable, not point back at the repo)."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = template.replace("__DOSSIER_DATA_JSON__", json.dumps(payload, ensure_ascii=False))
    output_path.write_text(html, encoding="utf-8")

    vendor_dest = output_path.parent / "vendor" / "pdfjs"
    vendor_dest.mkdir(parents=True, exist_ok=True)
    for name in ("pdf.min.js", "pdf.worker.min.js"):
        shutil.copy2(VENDOR_PDFJS_SRC / name, vendor_dest / name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--contract", type=Path, help="Real PDF to use instead of the built-in synthetic contract"
    )
    parser.add_argument(
        "--annex",
        type=Path,
        action="append",
        default=[],
        help="Optional real PDF to compare against --contract (repeat for several appendices)",
    )
    parser.add_argument(
        "--engine",
        choices=["none", "mistral"],
        default="none",
        help=(
            "OCR engine for pages with no native text layer (real scans). "
            "'none' (default) only reads native text, fast; 'mistral' also OCRs "
            "scanned pages via Mistral's OCR endpoint (needs MISTRAL_API_KEY set "
            "and --extra mistral installed). Ignored for the synthetic demo "
            "(no --contract)."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.contract:
        for path in (args.contract, *args.annex):
            if not path.is_file():
                raise SystemExit(f"File khong ton tai: {path}")
        snapshots = build_dossier_snapshots_from_files(args.contract, args.annex, args.engine)
        payload = build_report_payload(snapshots, synthetic=False)
    else:
        snapshots = build_dossier_snapshots()
        payload = build_report_payload(snapshots, synthetic=True)

    write_json(
        OUTPUT_ROOT / "dossier_result.json", {k: v for k, v in payload.items() if k != "images"}
    )
    report_path = OUTPUT_ROOT / "demo_report.html"
    render_html_report(payload, report_path)
    print(f"dossier_result.json -> {(OUTPUT_ROOT / 'dossier_result.json').resolve()}")
    print(f"demo_report.html    -> {report_path.resolve()}")
    print("Mo file demo_report.html bang trinh duyet de xem fact/finding va bam vao tung dong.")
    if args.contract and args.engine == "none":
        for doc in payload["documents"]:
            if doc["page_count"] and not doc["clauses"] and not doc["facts"]:
                print(
                    f"  Luu y: '{doc['filename']}' khong co clause/fact nao duoc nhan dien - "
                    "neu day la file scan (anh) khong co text layer, chay lai voi --engine mistral."
                )


if __name__ == "__main__":
    main()
