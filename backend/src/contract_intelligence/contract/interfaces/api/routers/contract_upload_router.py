"""POST /dossiers — Multipart upload hợp đồng + phụ lục (DOC-05b §5.3).

Endpoint này nhận 1 file contract (bắt buộc) + 0..n annex files,
tạo dossier + documents trong 1 transaction, sau đó auto-trigger
pipeline run đầu tiên (qua BackgroundTasks) để bắt đầu xử lý bất đồng bộ.

Response 202 Accepted trả về:
    - dossier_id
    - run_id (pipeline run đầu tiên)
    - documents: list (id, role, sha256)

Khớp DOC-05c: Backend tạo presigned URL MinIO cho AI service đọc PDF gốc
(Sprint 4 sẽ wire MinIO; Sprint 3 dùng blob_uri trực tiếp).

Theo nguyên tắc trust boundary (DOC-04 ADR-03): Backend là system of record,
AI service là stateless worker — mọi orchestration chạy ở đây.

Lưu ý kiến trúc:
    - Router thuộc Contract BC interfaces — KHÔNG import từ Extraction BC interfaces
      (vi phạm import-linter layer rule).
    - Pipeline trigger được dispatch qua ``shared/ai`` (shared kernel) — OK.
"""

from __future__ import annotations

import hashlib
import uuid
from io import BytesIO
from typing import Annotated, Any

import structlog
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.application.services.contract_service import (
    ContractService,
)
from contract_intelligence.contract.domain.entities.document import DocumentRole
from contract_intelligence.contract.infrastructure.persistence.repository_impl import (
    DocumentRepositoryImpl,
    DossierRepositoryImpl,
    JobRepositoryImpl,
    ManifestRepositoryImpl,
)
from contract_intelligence.shared.ai.pipeline_orchestrator import (
    DocumentJob,
    get_pipeline_orchestrator,
)
from contract_intelligence.shared.auth.tenant import get_tenant_id
from contract_intelligence.shared.base import new_ulid
from contract_intelligence.shared.persistence import get_async_session
from contract_intelligence.shared.responses import ApiResponse
from contract_intelligence.shared.storage import get_file_storage

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Contract-Upload"])


# ──────────────────────────────────────────────────────────────────────────────
# Response schema
# ──────────────────────────────────────────────────────────────────────────────


class UploadedDocumentInfo(BaseModel):
    """Thông tin 1 document vừa upload."""

    model_config = ConfigDict(extra="forbid")

    id: str
    role: str
    order_index: int
    filename: str
    sha256: str
    blob_uri: str
    page_count: int = 0
    size_bytes: int = 0


class DossierUploadResponse(BaseModel):
    """Response cho POST /dossiers/upload (multipart)."""

    model_config = ConfigDict(extra="forbid")

    dossier_id: str
    run_id: str | None = Field(
        default=None,
        description="Pipeline run ID đã trigger — poll GET /runs/{id} để theo dõi",
    )
    documents: list[UploadedDocumentInfo] = Field(default_factory=list)
    status: str = "accepted"


# ──────────────────────────────────────────────────────────────────────────────
# Endpoint
# ──────────────────────────────────────────────────────────────────────────────


@router.post(
    "/dossiers/upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[DossierUploadResponse],
    summary="Tạo dossier + upload multipart + auto-trigger pipeline run",
    responses={
        400: {"description": "Missing/invalid files"},
        403: {"description": "Insufficient role (OPERATOR | ADMINISTRATOR)"},
    },
)
async def upload_dossier(
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    contract_file: Annotated[UploadFile, File(description="PDF hợp đồng chính")],
    name: Annotated[str, Form(min_length=1, max_length=255)],
    batch_id: Annotated[str | None, Form()] = None,
    annex_files: list[UploadFile] | None = File(default=None),
    auto_run: Annotated[
        bool,
        Form(
            description="Tự động trigger pipeline run đầu tiên (default: true)",
        ),
    ] = True,
) -> ApiResponse[DossierUploadResponse]:
    """Tạo dossier + upload files + (optional) auto-trigger pipeline run.

    Flow (DOC-04 ADR-03 — Backend là system of record):
        1. Compute sha256 từng file
        2. Lưu file vào storage (Sprint 3: local; Sprint 4: MinIO)
        3. Tạo Dossier + Document entities trong 1 transaction
        4. Auto-trigger pipeline run (async) → BackgroundTasks

    Response 202 Accepted — KHÔNG đợi AI service xử lý xong.
    Frontend poll GET /runs/{id} để theo dõi tiến độ.
    """
    # ── 1. Validate files ───────────────────────────────────────────────────
    if not contract_file or not contract_file.filename:
        raise HTTPException(
            status_code=400,
            detail="contract_file is required",
        )
    if contract_file.content_type and contract_file.content_type != "application/pdf":
        logger.warning(
            "dossier_upload.non_pdf_contract",
            content_type=contract_file.content_type,
            filename=contract_file.filename,
        )
    annex_files = annex_files or []

    # ── 2. Compose ContractService bound to current session/tenant ─────────
    storage = get_file_storage()
    contract_svc = ContractService(
        dossier_repo=DossierRepositoryImpl(session, tenant_id),
        document_repo=DocumentRepositoryImpl(session, tenant_id),
        job_repo=JobRepositoryImpl(session, tenant_id),
        manifest_repo=ManifestRepositoryImpl(session, tenant_id),
        storage=storage,
        tenant_id=tenant_id,
    )

    # ── 3. Create dossier + ingest contract ─────────────────────────────────
    dossier = await contract_svc.create_dossier(name=name, batch_id=batch_id)

    contract_doc = await _ingest_file(
        contract_svc=contract_svc,
        dossier_id=dossier.id,
        file=contract_file,
        role=DocumentRole.CONTRACT,
        order_index=0,
    )

    # ── 4. Ingest annexes ──────────────────────────────────────────────────
    uploaded_docs: list[UploadedDocumentInfo] = [
        UploadedDocumentInfo(
            id=contract_doc.id,
            role=contract_doc.role.value,
            order_index=contract_doc.order_index,
            filename=contract_doc.filename,
            sha256=contract_doc.sha256,
            blob_uri=contract_doc.blob_uri,
            page_count=contract_doc.page_count,
        )
    ]

    for idx, annex_file in enumerate(annex_files, start=1):
        if not annex_file.filename:
            continue
        doc = await _ingest_file(
            contract_svc=contract_svc,
            dossier_id=dossier.id,
            file=annex_file,
            role=DocumentRole.ANNEX,
            order_index=idx,
        )
        uploaded_docs.append(
            UploadedDocumentInfo(
                id=doc.id,
                role=doc.role.value,
                order_index=doc.order_index,
                filename=doc.filename,
                sha256=doc.sha256,
                blob_uri=doc.blob_uri,
                page_count=doc.page_count,
            )
        )

    # ── 5. Auto-trigger pipeline run (async, qua shared/ai orchestrator) ───
    run_id: str | None = None
    if auto_run and uploaded_docs:
        run_id = new_ulid("run_")
        await _create_pipeline_run_row(
            session=session,
            tenant_id=tenant_id,
            run_id=run_id,
            dossier_id=dossier.id,
            trace_id=str(uuid.uuid4()),
        )

        # Build DocumentJob list (loaded from DB) — orchestrator schedules
        # the OCR → Extract → Compare chain in background.
        doc_jobs = [
            DocumentJob(
                document_id=d.id,
                sha256=d.sha256,
                blob_uri=d.blob_uri,
                filename=d.filename,
                role=d.role.value,
                page_count=d.page_count,
            )
            for d in [
                contract_doc,
                *[
                    await _load_document(
                        session=session,
                        tenant_id=tenant_id,
                        doc_id=info.id,
                    )
                    for info in uploaded_docs[1:]  # skip contract (already loaded)
                ],
            ]
        ]

        orchestrator = get_pipeline_orchestrator()
        trace_id = str(uuid.uuid4())
        background_tasks.add_task(
            _safe_run_pipeline,
            orchestrator=orchestrator,
            run_id=run_id,
            dossier_id=dossier.id,
            tenant_id=tenant_id,
            documents=doc_jobs,
            trace_id=trace_id,
        )

    # ── 6. Commit transaction ──────────────────────────────────────────────
    await session.commit()

    logger.info(
        "dossier_upload.accepted",
        dossier_id=dossier.id,
        run_id=run_id,
        contract_filename=contract_file.filename,
        annex_count=len(annex_files),
        tenant_id=tenant_id,
    )

    return ApiResponse(
        data=DossierUploadResponse(
            dossier_id=dossier.id,
            run_id=run_id,
            documents=uploaded_docs,
            status="accepted",
        ),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


async def _ingest_file(
    *,
    contract_svc: ContractService,
    dossier_id: str,
    file: UploadFile,
    role: DocumentRole,
    order_index: int,
) -> Any:
    """Đọc UploadFile → ingest vào storage + persist Document."""
    chunks: list[bytes] = []
    total_size = 0
    while chunk := await file.read(1024 * 1024):  # 1 MB chunks
        chunks.append(chunk)
        total_size += len(chunk)
    raw_bytes = b"".join(chunks)

    sha256 = hashlib.sha256(raw_bytes).hexdigest()

    document = await contract_svc.upload_document(
        dossier_id=dossier_id,
        filename=file.filename or f"{role.value.lower()}.pdf",
        content=BytesIO(raw_bytes),
        role=role,
        order_index=order_index,
    )

    logger.info(
        "dossier_upload.file_ingested",
        document_id=document.id,
        filename=file.filename,
        role=role.value,
        size_bytes=total_size,
        sha256=sha256,
    )
    return document


async def _load_document(
    *,
    session: AsyncSession,
    tenant_id: str,
    doc_id: str,
) -> Any:
    """Load 1 document từ DB — cross-BC read (Contract BC owns table)."""
    repo = DocumentRepositoryImpl(session, tenant_id)
    return await repo.get(doc_id)


async def _create_pipeline_run_row(
    *,
    session: AsyncSession,
    tenant_id: str,
    run_id: str,
    dossier_id: str,
    trace_id: str,
) -> None:
    """Tạo pipeline_run row + 11 steps S0..S10 — sync trước khi commit transaction."""
    from contract_intelligence.extraction.infrastructure.persistence.orm import (
        PipelineRunORM,
        PipelineStepORM,
    )

    run = PipelineRunORM(
        id=run_id,
        tenant_id=tenant_id,
        job_id=run_id,  # 1:1 placeholder
        dossier_id=dossier_id,
        status="queued",
        pipeline_version="v1.0.0",
        git_sha="",
        trace_id=trace_id,
    )
    session.add(run)
    await session.flush()

    for step_code in ("S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10"):
        step = PipelineStepORM(
            tenant_id=tenant_id,
            run_id=run_id,
            step=step_code,
            status="queued",
        )
        session.add(step)
    await session.flush()


async def _safe_run_pipeline(
    *,
    orchestrator: Any,
    run_id: str,
    dossier_id: str,
    tenant_id: str,
    documents: list[DocumentJob],
    trace_id: str,
) -> None:
    """Wrap orchestrator.run_with_documents() với error handling để không crash background task."""
    try:
        await orchestrator.run_with_documents(
            run_id=run_id,
            dossier_id=dossier_id,
            tenant_id=tenant_id,
            documents=documents,
            trace_id=trace_id,
        )
    except Exception as exc:
        logger.exception(
            "pipeline_run.background_error",
            run_id=run_id,
            dossier_id=dossier_id,
            error=str(exc),
        )


__all__ = ["router", "upload_dossier", "DossierUploadResponse", "UploadedDocumentInfo"]
