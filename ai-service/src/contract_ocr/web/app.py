"""Local OCR test API: upload a PDF, run the existing OCR pipeline, read the text back.

API-only backend — no HTML here. The frontend lives separately in frontend/index.html
and talks to this over HTTP (CORS enabled below), typically served by
scripts/serve_frontend.py on a different port. Not part of the Sprint 1 spike scope in
README.md; this is a manual testing aid layered on top of ProcessDocument. It reuses the
same routing/engine/preprocessing logic as the CLI benchmark, so behavior (SKIPPED/FAILED
handling, evidence, engine availability) matches what `contract-ocr benchmark` would
produce for a single document.
"""

import base64
import importlib.util
import os
import tempfile
import threading
import uuid
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from time import perf_counter
from typing import Any

import pymupdf
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image
from pydantic import ValidationError

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
from contract_ocr.domain.entities import Document, Experiment
from contract_ocr.infrastructure.image.preprocessing import ImagePreprocessor, validate_steps
from contract_ocr.infrastructure.image.renderer import PdfRenderer
from contract_ocr.infrastructure.pdf.pymupdf_extractor import PyMuPDFExtractor

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
ENGINE_IDS = {"pymupdf", "openai", "gemini", "mistral"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
# Pages run concurrently only for stateless remote API engines.
PARALLEL_ENGINES = {"openai", "gemini", "mistral"}
WEB_MAX_WORKERS = 4

app = FastAPI(title="Contract OCR Lab - Backend API")

# Local-only test tool, no auth/cookies involved: allow any origin so the static
# frontend can be opened from any port (or file://) without CORS troubleshooting.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_processor = ProcessDocument(
    PyMuPDFExtractor(), PdfRenderer(), ImagePreprocessor(), PdfPageClassifier()
)
_engine_lock = threading.Lock()
_process_lock = threading.Lock()
_engine_cache: dict[str, OCREngine] = {}


def _engine_status() -> list[dict[str, Any]]:
    engines = [
        {
            "id": "pymupdf",
            "label": "PyMuPDF",
            "available": True,
            "note": "Đọc text có sẵn trong PDF, không cần OCR",
        }
    ]
    openai_ok = importlib.util.find_spec("openai") is not None
    has_key = bool(os.environ.get("OPENAI_API_KEY"))
    engines.append(
        {
            "id": "openai",
            "label": "OpenAI GPT-5.6 Terra (Vision)",
            "available": openai_ok and has_key,
            "external": True,
            "note": (
                "⚠️ Ảnh trang PDF được gửi lên OpenAI — chỉ dùng file demo, không dùng tài liệu thật"
                if openai_ok and has_key
                else "Chưa cài đặt. Chạy: uv sync --extra openai"
                if not openai_ok
                else "Thiếu biến môi trường OPENAI_API_KEY"
            ),
        }
    )
    gemini_ok = importlib.util.find_spec("google.genai") is not None
    has_gemini_key = bool(os.environ.get("GEMINI_API_KEY"))
    engines.append(
        {
            "id": "gemini",
            "label": "Gemini 3 Flash (Vision)",
            "available": gemini_ok and has_gemini_key,
            "external": True,
            "note": (
                "⚠️ Ảnh trang PDF được gửi lên Google Gemini — chỉ dùng file demo, không dùng tài liệu thật"
                if gemini_ok and has_gemini_key
                else "Chưa cài đặt. Chạy: uv sync --extra gemini"
                if not gemini_ok
                else "Thiếu biến môi trường GEMINI_API_KEY"
            ),
        }
    )
    mistral_ok = importlib.util.find_spec("mistralai") is not None
    has_mistral_key = bool(os.environ.get("MISTRAL_API_KEY"))
    engines.append(
        {
            "id": "mistral",
            "label": "Mistral OCR (Document AI)",
            "available": mistral_ok and has_mistral_key,
            "external": True,
            "note": (
                "⚠️ Ảnh trang PDF được gửi lên Mistral — chỉ dùng file demo, không dùng tài liệu thật"
                if mistral_ok and has_mistral_key
                else "Chưa cài đặt. Chạy: uv sync --extra mistral"
                if not mistral_ok
                else "Thiếu biến môi trường MISTRAL_API_KEY"
            ),
        }
    )
    return engines


def _get_engine(engine_id: str) -> OCREngine | None:
    if engine_id == "pymupdf":
        return None
    with _engine_lock:
        if engine_id not in _engine_cache:
            if engine_id == "openai":
                from contract_ocr.infrastructure.ocr.openai_vision_ocr import (
                    OpenAIVisionOCREngine,
                )

                _engine_cache[engine_id] = OpenAIVisionOCREngine(enabled=True)
            elif engine_id == "gemini":
                from contract_ocr.infrastructure.ocr.gemini_vision_ocr import (
                    GeminiVisionOCREngine,
                )

                _engine_cache[engine_id] = GeminiVisionOCREngine(enabled=True)
            elif engine_id == "mistral":
                from contract_ocr.infrastructure.ocr.mistral_ocr import MistralOCREngine

                _engine_cache[engine_id] = MistralOCREngine(enabled=True)
        return _engine_cache[engine_id]


def _image_bytes_to_pdf(content: bytes, dpi: int) -> bytes:
    """Wraps a single image in a 1-page PDF sized so re-rendering at `dpi` reproduces the
    original pixel dimensions exactly — same approach as cli/main.py's degraded-sample
    generator. The page has no text layer, so it always routes to the OCR engine."""
    image = Image.open(BytesIO(content))
    image.load()
    image = image.convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    with pymupdf.open() as doc:
        page = doc.new_page(width=image.width * 72 / dpi, height=image.height * 72 / dpi)
        page.insert_image(page.rect, stream=buffer.getvalue())
        return doc.tobytes()


def _document_response(document: Document, filename: str, elapsed_ms: float) -> dict[str, Any]:
    pages, texts = [], []
    for page in document.pages:
        text = "\n".join(line.text for line in page.lines)
        texts.append(text)
        pages.append(
            {
                "page_number": page.page_number,
                "status": page.status,
                "input_type": page.input_type,
                "error": page.error,
                "engine": page.engine,
                "model": page.model,
                "processing_ms": round(page.processing_ms, 1),
                "text": text,
                "line_count": len(page.lines),
                "geometry_available": page.geometry_available,
                "evidence": page.evidence.model_dump(mode="json") if page.evidence else None,
            }
        )
    return {
        "document_id": document.document_id,
        "filename": filename,
        "page_count": len(pages),
        "elapsed_ms": elapsed_ms,
        "full_text": "\f".join(texts),
        "pages": pages,
    }


@app.get("/")
def index() -> JSONResponse:
    return JSONResponse(
        {
            "service": "contract-ocr-lab backend",
            "docs": "/docs",
            "endpoints": ["/api/engines", "/api/ocr", "/api/ai2/analyze"],
            "frontend": "run scripts/serve_frontend.py separately, see README",
        }
    )


@app.get("/api/engines")
def engines() -> JSONResponse:
    return JSONResponse({"engines": _engine_status()})


@app.post("/api/ocr")
def ocr_pdf(
    file: UploadFile = File(...),
    engine: str = Form("pymupdf"),
    dpi: int = Form(300),
    preprocessing: str = Form(""),
) -> JSONResponse:
    filename = file.filename or "upload.pdf"
    suffix = Path(filename).suffix.lower()
    is_pdf = suffix == ".pdf"
    is_image = suffix in IMAGE_EXTENSIONS
    if not (is_pdf or is_image):
        raise HTTPException(400, "Chỉ nhận file .pdf hoặc ảnh (jpg, png, webp, bmp, tiff)")
    if engine not in ENGINE_IDS:
        raise HTTPException(400, "engine phải là pymupdf, openai, gemini hoặc mistral")
    if not 72 <= dpi <= 600:
        raise HTTPException(400, "DPI phải trong khoảng 72-600")
    content = file.file.read()
    if not content:
        raise HTTPException(400, "File rỗng")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File vượt quá 50MB")
    if is_pdf:
        if b"%PDF-" not in content[:1024]:
            raise HTTPException(400, "File không phải PDF hợp lệ")
    else:
        try:
            Image.open(BytesIO(content)).verify()
        except Exception as exc:
            raise HTTPException(400, f"File không phải ảnh hợp lệ: {exc}") from exc

    steps = [s for s in preprocessing.split(",") if s]
    try:
        validate_steps(steps)
        experiment = Experiment(id="WEBUI", engine=engine, preprocessing=steps)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc

    engine_obj = _get_engine(engine)
    document_id = f"web-{uuid.uuid4().hex[:8]}"
    with tempfile.TemporaryDirectory(prefix="contract_ocr_ui_") as tmp:
        tmp_path = Path(tmp)
        pdf_path = tmp_path / "upload.pdf"
        if is_pdf:
            pdf_path.write_bytes(content)
        else:
            try:
                pdf_path.write_bytes(_image_bytes_to_pdf(content, dpi))
            except Exception as exc:
                raise HTTPException(
                    400, f"Không đọc được ảnh: {type(exc).__name__}: {exc}"
                ) from exc
        started = perf_counter()
        max_workers = WEB_MAX_WORKERS if engine in PARALLEL_ENGINES else 1
        try:
            with _process_lock:
                document = _processor.execute(
                    source=str(pdf_path),
                    document_id=document_id,
                    experiment=experiment,
                    engine=engine_obj,
                    output=tmp_path / "output",
                    run_id=document_id,
                    dpi=dpi,
                    max_workers=max_workers,
                )
        except ValueError as exc:
            raise HTTPException(400, f"Không xử lý được PDF: {exc}") from exc
        except Exception as exc:
            raise HTTPException(500, f"Lỗi không mong đợi: {type(exc).__name__}: {exc}") from exc
        elapsed_ms = (perf_counter() - started) * 1000

    return JSONResponse(_document_response(document, filename, elapsed_ms))


def _read_pdf_upload(file: UploadFile) -> bytes:
    filename = file.filename or "upload.pdf"
    if Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(400, f"'{filename}': chỉ nhận file .pdf cho endpoint này")
    content = file.file.read()
    if not content:
        raise HTTPException(400, f"'{filename}': file rỗng")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"'{filename}': vượt quá 50MB")
    if b"%PDF-" not in content[:1024]:
        raise HTTPException(400, f"'{filename}': không phải PDF hợp lệ")
    return content


def _analyze_one(
    content: bytes,
    filename: str,
    role: str,
    dossier_id: str,
    engine_id: str,
    engine_obj: OCREngine | None,
    dpi: int,
    tmp_path: Path,
) -> tuple[dict, dict[str, str]]:
    """OCR (existing pipeline) -> ai1.snapshot.v1 -> AI2 layer for one uploaded
    PDF. Returns (document entry for the /api/ai2/analyze response, that
    document's page images keyed "document_id:page_number")."""
    document_id = f"web-{role}-{uuid.uuid4().hex[:8]}"
    pdf_path = tmp_path / f"{role}.pdf"
    pdf_path.write_bytes(content)

    max_workers = WEB_MAX_WORKERS if engine_id in PARALLEL_ENGINES else 1
    with _process_lock:
        document = _processor.execute(
            source=str(pdf_path),
            document_id=document_id,
            experiment=Experiment(id="AI2WEB", engine=engine_id, preprocessing=[]),
            engine=engine_obj,
            output=tmp_path / f"{role}-output",
            run_id=document_id,
            dpi=dpi,
            max_workers=max_workers,
        )

    engine_label = "pymupdf" if engine_obj is None else f"pymupdf+{engine_id}"
    image_dir = tmp_path / "images" / document_id
    snapshot = BuildSnapshot(PdfRenderer(), image_dpi=dpi).execute(
        document,
        snapshot_id=f"ocr-run-{document_id}",
        dossier_id=dossier_id,
        document_role="contract" if role == "contract" else "annex",
        filename=filename,
        engine_name=engine_label,
        engine_version=pymupdf.VersionBind,
        image_output_dir=image_dir,
        image_uri_prefix=f"storage://ocr/{document_id}",
    )

    clauses = extract_clauses(snapshot)
    facts = extract_facts(snapshot, clauses)
    images = {}
    for page in snapshot.pages:
        png_path = image_dir / f"page-{page.page_number:03d}.png"
        if png_path.exists():
            encoded = base64.b64encode(png_path.read_bytes()).decode("ascii")
            images[f"{document_id}:{page.page_number}"] = f"data:image/png;base64,{encoded}"

    doc_entry = {
        "document_id": document_id,
        "role": role,
        "filename": filename,
        "input_type": snapshot.input_type,
        "engine": snapshot.engine.model_dump(),
        "page_count": snapshot.page_count,
        "classification": classify_document(snapshot),
        "clauses": clauses,
        "facts": facts,
    }
    return doc_entry, images


@app.post("/api/ai2/analyze")
def ai2_analyze(
    contract: UploadFile = File(...),
    annexes: list[UploadFile] = File([]),
    engine: str = Form("pymupdf"),
    dpi: int = Form(200),
) -> JSONResponse:
    """Runs OCR + the AI2 layer (classification, clause/preamble structure,
    typed facts with citations and confidence, conflict detection against 0..N
    appendices — see contract_ocr.application.use_cases.extract_ai2_facts) on
    one required Contract PDF plus any number of Appendix PDFs. Unlike the
    pdf.js-only path in scripts/demo_report_template.html, this goes through
    the real OCR engines below (including Mistral for scanned pages), so it
    isn't limited to PDFs with a native text layer."""
    if engine not in ENGINE_IDS:
        raise HTTPException(400, "engine phải là pymupdf, openai, gemini hoặc mistral")
    if not 72 <= dpi <= 600:
        raise HTTPException(400, "DPI phải trong khoảng 72-600")

    contract_content = _read_pdf_upload(contract)
    annex_contents = [(a, _read_pdf_upload(a)) for a in annexes]
    engine_obj = _get_engine(engine)
    dossier_id = f"web-dossier-{uuid.uuid4().hex[:8]}"

    with tempfile.TemporaryDirectory(prefix="contract_ocr_ai2_") as tmp:
        tmp_path = Path(tmp)
        try:
            documents = []
            images: dict[str, str] = {}

            contract_entry, contract_images = _analyze_one(
                contract_content,
                contract.filename or "hop-dong.pdf",
                "contract",
                dossier_id,
                engine,
                engine_obj,
                dpi,
                tmp_path,
            )
            documents.append(contract_entry)
            images.update(contract_images)

            annex_refs = []
            for annex_file, annex_content in annex_contents:
                annex_entry, annex_images = _analyze_one(
                    annex_content,
                    annex_file.filename or "phu-luc.pdf",
                    "annex",
                    dossier_id,
                    engine,
                    engine_obj,
                    dpi,
                    tmp_path,
                )
                documents.append(annex_entry)
                images.update(annex_images)
                annex_refs.append(
                    (annex_entry["document_id"], annex_entry["filename"], annex_entry["facts"])
                )
        except ValueError as exc:
            raise HTTPException(400, f"Không xử lý được PDF: {exc}") from exc
        except Exception as exc:
            raise HTTPException(500, f"Lỗi không mong đợi: {type(exc).__name__}: {exc}") from exc

        findings = compare_facts_multi(contract_entry["facts"], annex_refs)

    return JSONResponse(
        {
            "dossier_id": dossier_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "disclaimer": (
                "DEMO PIPELINE qua backend that (OCR engine da chon + lop AI2 don gian hoa) - "
                "khong phai ket qua extraction da benchmark."
            ),
            "documents": documents,
            "findings": findings,
            "images": images,
        }
    )
