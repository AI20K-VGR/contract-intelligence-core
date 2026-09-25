"""Backend OCR job execution shared by the HTTP API and Kafka worker.

Keeps the DOC-05c OCR pipeline in one place so Kafka only adds transport.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import tempfile
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import pymupdf
from pydantic import BaseModel, ConfigDict, Field

from contract_ocr.application.ports.ocr_engine import OCREngine
from contract_ocr.application.use_cases.build_snapshot import BuildSnapshot
from contract_ocr.application.use_cases.classify_pdf import PdfPageClassifier
from contract_ocr.application.use_cases.process_document import ProcessDocument
from contract_ocr.domain.entities import Experiment
from contract_ocr.infrastructure.image.preprocessing import ImagePreprocessor
from contract_ocr.infrastructure.image.renderer import PdfRenderer
from contract_ocr.infrastructure.observability import observation
from contract_ocr.infrastructure.pdf.pymupdf_extractor import PyMuPDFExtractor

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
ENGINE_IDS = {"pymupdf", "openai", "gemini", "mistral"}
PARALLEL_ENGINES = {"openai", "gemini", "mistral"}
WEB_MAX_WORKERS = 4

_processor = ProcessDocument(
    PyMuPDFExtractor(), PdfRenderer(), ImagePreprocessor(), PdfPageClassifier()
)
_engine_lock = threading.Lock()
_process_lock = threading.Lock()
_engine_cache: dict[str, OCREngine] = {}
_backend_jobs: dict[str, dict[str, Any]] = {}
_backend_jobs_lock = threading.Lock()


class BackendOcrJobRequest(BaseModel):
    """Request sent by backend (DOC-05c §4.1 / Kafka ``ai1.ocr.command`` payload)."""

    model_config = ConfigDict(extra="forbid")

    task_id: int
    attempt_id: int
    tenant_id: str
    document_id: str
    source_blob_get_url: str
    source_sha256: str
    pages_to_process: list[int]
    render_target: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def new_backend_job(kind: str) -> tuple[str, dict[str, Any]]:
    job_id = f"ai1_{uuid.uuid4().hex}"
    job = {
        "job_id": job_id,
        "kind": kind,
        "status": "queued",
        "progress_pct": 0,
        "current_stage": "queued",
        "created_at": _now(),
        "updated_at": _now(),
        "finished_at": None,
        "result": None,
        "error": None,
    }
    with _backend_jobs_lock:
        _backend_jobs[job_id] = job
    return job_id, job


def get_backend_job(job_id: str) -> dict[str, Any] | None:
    with _backend_jobs_lock:
        job = _backend_jobs.get(job_id)
        return dict(job) if job is not None else None


def update_backend_job(job_id: str, **changes: Any) -> None:
    with _backend_jobs_lock:
        job = _backend_jobs.get(job_id)
        if job is not None:
            job.update(changes, updated_at=_now())


def read_source_blob(url: str, expected_sha256: str) -> bytes:
    try:
        with urlopen(url, timeout=30) as response:  # noqa: S310 - backend supplies a presigned URL
            content = response.read(MAX_UPLOAD_BYTES + 1)
    except (OSError, URLError) as exc:
        raise RuntimeError(f"cannot download source_blob_get_url: {exc}") from exc
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise RuntimeError("source document is empty or exceeds the 50 MB service limit")
    actual_sha256 = hashlib.sha256(content).hexdigest()
    if actual_sha256 != expected_sha256.removeprefix("sha256:"):
        raise RuntimeError("source_sha256 does not match downloaded document")
    if b"%PDF-" not in content[:1024]:
        raise RuntimeError("source document is not a valid PDF")
    return content


def align_pages_to_pdf(request: BackendOcrJobRequest) -> BackendOcrJobRequest:
    """Force ``pages_to_process`` to the full PDF range (AI1 OCR constraint)."""
    content = read_source_blob(request.source_blob_get_url, request.source_sha256)
    with pymupdf.open(stream=content, filetype="pdf") as source_pdf:
        pages = list(range(1, source_pdf.page_count + 1))
    if sorted(set(request.pages_to_process)) == pages:
        return request
    return request.model_copy(update={"pages_to_process": pages})


def _upload_rendered_pages(
    image_dir: Path,
    snapshot: Any,
    render_target: dict[str, Any],
) -> None:
    put_urls = render_target.get("presigned_put_urls", {})
    if not isinstance(put_urls, dict):
        put_urls = {}
    for page in snapshot.pages:
        target = put_urls.get(str(page.page_number))
        png_path = image_dir / f"page-{page.page_number:03d}.png"
        if not isinstance(target, str) or not target or not png_path.exists():
            page.warnings.append("render_artifact_not_uploaded")
            continue
        request = Request(
            target,
            data=png_path.read_bytes(),
            method="PUT",
            headers={"Content-Type": "image/png"},
        )
        try:
            with urlopen(request, timeout=30):  # noqa: S310 - backend supplies a presigned URL
                pass
        except (OSError, URLError) as exc:
            page.warnings.append(f"render_upload_failed:{type(exc).__name__}")


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
                # Text (prose) is read by OpenAI's vision model -- measurably more
                # accurate on Vietnamese diacritics than Mistral's dedicated OCR
                # endpoint on this codebase's documents (confirmed by re-running the
                # same page image through both: Mistral produced "khà nang truy vét t
                # ur du lieu..." where OpenAI read it correctly). Mistral stays the
                # source of table structure and bbox geometry -- it is the only
                # engine here whose blocks carry a real, measured pixel bbox and
                # whose table markdown `markdown_tables.build_table_from_block` can
                # parse. If OpenAI itself runs out of quota, FallbackOCREngine drops
                # back to Mistral for text rather than failing the page outright.
                from contract_ocr.infrastructure.ocr.fallback_ocr import FallbackOCREngine
                from contract_ocr.infrastructure.ocr.hybrid_ocr import HybridOCREngine
                from contract_ocr.infrastructure.ocr.mistral_ocr import MistralOCREngine
                from contract_ocr.infrastructure.ocr.openai_vision_ocr import (
                    OpenAIVisionOCREngine,
                )

                mistral = MistralOCREngine(enabled=True)
                text_engine = FallbackOCREngine(OpenAIVisionOCREngine(enabled=True), mistral)
                _engine_cache[engine_id] = HybridOCREngine(text_engine, mistral)
        return _engine_cache[engine_id]


def run_backend_ocr(
    job_id: str,
    request: BackendOcrJobRequest,
    *,
    trace_seed: str | None = None,
) -> None:
    """Execute one OCR job with a privacy-safe Langfuse trace when configured."""
    engine_id = str(request.options.get("engine", "pymupdf"))
    with observation(
        "process-ocr-job",
        input={
            "job_id": job_id,
            "task_id": request.task_id,
            "attempt_id": request.attempt_id,
            "document_id": request.document_id,
            "requested_page_count": len(request.pages_to_process),
            "engine": engine_id,
        },
        metadata={
            "tenant_id": request.tenant_id,
            "feature": "document-ocr",
            "schema_version": "ai1.snapshot.v1",
        },
        trace_seed=trace_seed or job_id,
        session_id=f"ocr-document:{request.document_id}",
        tags=["ai1", "ocr", engine_id],
    ) as root_span:
        _run_backend_ocr(job_id, request)
        if root_span is not None:
            job = get_backend_job(job_id) or {}
            snapshot = (job.get("result") or {}).get("snapshot") or {}
            pages = snapshot.get("pages") or []
            root_span.update(
                output={
                    "status": job.get("status"),
                    "page_count": snapshot.get("page_count", 0),
                    "line_count": sum(len(page.get("lines") or []) for page in pages),
                    "table_count": sum(len(page.get("tables") or []) for page in pages),
                    "node_count": len(snapshot.get("nodes") or []),
                },
                level="ERROR" if job.get("status") == "failed" else "DEFAULT",
                status_message=(
                    "OCR job failed; inspect application logs"
                    if job.get("status") == "failed"
                    else None
                ),
            )


def _run_backend_ocr(job_id: str, request: BackendOcrJobRequest) -> None:
    """Internal OCR execution; public callers should use :func:`run_backend_ocr`."""
    update_backend_job(job_id, status="processing", progress_pct=5, current_stage="download")
    try:
        with observation(
            "download-source",
            input={"document_id": request.document_id},
            metadata={"transport": "presigned-url"},
        ) as download_span:
            content = read_source_blob(request.source_blob_get_url, request.source_sha256)
            with pymupdf.open(stream=content, filetype="pdf") as source_pdf:
                available_pages = list(range(1, source_pdf.page_count + 1))
            if download_span is not None:
                download_span.update(
                    output={"size_bytes": len(content), "page_count": len(available_pages)}
                )
        requested_pages = sorted(set(request.pages_to_process))
        if requested_pages != available_pages:
            raise RuntimeError("AI1 OCR job currently supports only the full document page range")
        engine_id = str(request.options.get("engine", "pymupdf"))
        if engine_id not in ENGINE_IDS:
            raise RuntimeError(f"unsupported OCR engine: {engine_id}")
        dpi = int(request.options.get("dpi", 150))
        if not 72 <= dpi <= 600:
            raise RuntimeError("options.dpi must be within 72..600")

        update_backend_job(job_id, progress_pct=15, current_stage="ocr")
        with tempfile.TemporaryDirectory(prefix="contract_ocr_backend_") as tmp:
            tmp_path = Path(tmp)
            pdf_path = tmp_path / "source.pdf"
            pdf_path.write_bytes(content)
            engine = _get_engine(engine_id)
            max_workers = WEB_MAX_WORKERS if engine_id in PARALLEL_ENGINES else 1
            with observation(
                "process-document",
                as_type="chain",
                input={
                    "document_id": request.document_id,
                    "page_count": len(available_pages),
                    "engine": engine_id,
                    "dpi": dpi,
                },
            ) as process_span:
                with _process_lock:
                    document = _processor.execute(
                        source=str(pdf_path),
                        document_id=request.document_id,
                        experiment=Experiment(id="BACKEND_API", engine=engine_id, preprocessing=[]),
                        engine=engine,
                        output=tmp_path / "output",
                        run_id=job_id,
                        dpi=dpi,
                        max_workers=max_workers,
                    )
                if process_span is not None:
                    process_span.update(
                        output={
                            "page_count": len(document.pages),
                            "failed_pages": sum(
                                1 for page in document.pages if str(page.status) == "FAILED"
                            ),
                        }
                    )
            update_backend_job(job_id, progress_pct=80, current_stage="build_snapshot")
            image_dir = tmp_path / "images" / request.document_id
            with observation(
                "build-snapshot",
                as_type="chain",
                input={"document_id": request.document_id, "page_count": len(document.pages)},
            ) as snapshot_span:
                snapshot = BuildSnapshot(PdfRenderer(), image_dpi=dpi).execute(
                    document,
                    snapshot_id=f"ocr-run-{job_id}",
                    dossier_id=f"backend-task-{request.task_id}",
                    document_role=str(request.options.get("document_role", "contract")),
                    filename=str(request.options.get("filename", "source.pdf")),
                    engine_name="pymupdf" if engine is None else f"pymupdf+{engine_id}",
                    engine_version=pymupdf.VersionBind,
                    image_output_dir=image_dir,
                    image_uri_prefix=f"storage://ai1/{request.document_id}",
                )
                if snapshot_span is not None:
                    snapshot_span.update(
                        output={
                            "page_count": snapshot.page_count,
                            "node_count": len(snapshot.nodes),
                            "table_count": sum(len(page.tables) for page in snapshot.pages),
                        }
                    )
            with observation(
                "upload-renders",
                input={"page_count": snapshot.page_count},
                metadata={"transport": "presigned-url"},
            ) as upload_span:
                _upload_rendered_pages(image_dir, snapshot, request.render_target)
                if upload_span is not None:
                    upload_span.update(
                        output={"warning_count": sum(len(page.warnings) for page in snapshot.pages)}
                    )
            result = {
                "schema_version": "ai1.snapshot.v1",
                "snapshot": snapshot.model_dump(mode="json"),
            }
        update_backend_job(
            job_id,
            status="completed",
            progress_pct=100,
            current_stage="completed",
            result=result,
            finished_at=_now(),
        )
    except Exception as exc:
        update_backend_job(
            job_id,
            status="failed",
            progress_pct=100,
            current_stage="failed",
            error={"code": "AI1_OCR_FAILED", "message": str(exc)},
            finished_at=_now(),
        )


def cancel_backend_job(job_id: str) -> dict[str, Any] | None:
    with _backend_jobs_lock:
        job = _backend_jobs.get(job_id)
        if job is None:
            return None
        if job["status"] in {"queued", "processing"}:
            job.update(
                status="cancelled",
                current_stage="cancelled",
                finished_at=_now(),
                updated_at=_now(),
            )
        return dict(job)


def engine_status() -> list[dict[str, Any]]:
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
