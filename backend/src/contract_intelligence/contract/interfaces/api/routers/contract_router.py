r"""Contract bounded context router — Phase 1 endpoints per DOC-05-api-spec.yaml.

Endpoints (Phase 1: Core Document Ingestion):
    POST   /dossiers                     — Multipart upload (per spec line 116-148)
    GET    /dossiers                     — List dossiers (spec line 150-183)
    GET    /dossiers/{id}                — Dossier detail (spec line 185-204)
    PATCH  /dossiers/{id}                — Update metadata (spec line 204-228)
    GET    /dossiers/{id}/documents      — List documents (spec line 262-277)
    GET    /documents/{id}               — Document detail (spec line ~759)
    GET    /documents/{id}/content       — Stream PDF binary

RBAC matrix (DOC-05b §2.3):
    OPERATOR, ADMINISTRATOR  → write ops (POST, PATCH, upload, manifest confirm)
    OPERATOR, REVIEWER, ADMINISTRATOR  → read ops

Layer: interfaces/api — composes application services, never directly hits ORM.
"""

from __future__ import annotations

import json
from io import BytesIO
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from contract_intelligence.contract.application.dtos.document_dtos import (
    DocumentDetailDTO,
    DocumentListItemDTO,
)
from contract_intelligence.contract.application.dtos.dossier_dtos import (
    DossierCreatedDTO,
    DossierDetailDTO,
    DossierSummaryDTO,
)
from contract_intelligence.contract.domain.entities.document import (
    Document,
    DocumentRole,
)
from contract_intelligence.contract.interfaces.api.dependencies import (
    ContractServiceDep,
)
from contract_intelligence.infrastructure.messaging import publish_event
from contract_intelligence.infrastructure.storage import upload_file
from contract_intelligence.shared.auth import (
    AuthenticatedUser,
    get_current_user,
    require_role,
)
from contract_intelligence.shared.responses import ApiMeta, ApiResponse

router = APIRouter(tags=["Contract"])


# -----------------------------------------------------------------------------
# Multipart upload helper — accept JSON metadata field per spec
# -----------------------------------------------------------------------------


class DossierUploadMetadata(BaseModel):
    """metadata field của DossierUploadRequest (openapi.yaml: required)."""

    model_config = {"extra": "allow"}  # allow tags, notes, custom fields

    name: str | None = None
    tags: list[str] | None = None
    notes: str | None = None


def _parse_upload_metadata(raw: str | None) -> DossierUploadMetadata:
    """Parse metadata field — JSON string theo OpenAPI multipart encoding.

    Trả về empty object nếu thiếu (spec khuyến nghị name lấy từ filename).
    """
    if not raw:
        return DossierUploadMetadata()
    try:
        return DossierUploadMetadata.model_validate_json(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid metadata JSON: {exc}",
        ) from exc


class DossierUpdateBody(BaseModel):
    """Request body for PATCH /dossiers/{id} — per openapi.yaml DossierUpdateRequest."""

    name: str | None = None
    metadata: dict[str, Any] | None = None


async def _ingest_upload_file(
    *,
    svc: Any,
    dossier_id: str,
    file: UploadFile,
    role: DocumentRole,
    order_index: int,
) -> tuple[Document, int, str]:
    """Đọc UploadFile → MinIO → persist Document.

    Returns:
        (Document entity, size_bytes, s3_path) — s3_path dùng cho Kafka event.
    """
    chunks: list[bytes] = []
    total_size = 0
    while chunk := await file.read(1024 * 1024):
        chunks.append(chunk)
        total_size += len(chunk)
    raw_bytes = b"".join(chunks)

    filename = file.filename or f"{role.value.lower()}.pdf"
    object_key = f"{dossier_id}/{order_index:02d}_{filename}"
    s3_path = await upload_file(object_key, raw_bytes)

    doc = await svc.upload_document(
        dossier_id=dossier_id,
        filename=filename,
        content=BytesIO(raw_bytes),
        role=role,
        order_index=order_index,
        file_size_bytes=total_size,
        blob_uri=s3_path,
    )
    return doc, total_size, s3_path


# -----------------------------------------------------------------------------
# POST /dossiers — Multipart upload (Per openapi.yaml line 116)
# -----------------------------------------------------------------------------


@router.post(
    "/dossiers",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[DossierCreatedDTO],
    summary="Tạo dossier + upload file hợp đồng/phụ lục",
    description=(
        "Multipart upload: `contract` (bắt buộc), `annexes` (tuỳ chọn, 0..n), "
        '`metadata` (JSON string bắt buộc — vd `{"name": "..."}`).\n\n'
        "RBAC: OPERATOR, ADMINISTRATOR (per openapi.yaml x-rbac)."
    ),
    responses={
        400: {"description": "Missing contract file"},
        403: {"description": "Insufficient role"},
        422: {"description": "Invalid metadata JSON"},
    },
)
async def create_dossier(
    svc: ContractServiceDep,
    user: Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))],
    contract: Annotated[UploadFile, File(description="PDF hợp đồng chính (required)")],
    metadata: Annotated[str, File(description="JSON string: {name, tags?, notes?}")],
    annexes: Annotated[list[UploadFile] | None, File(description="PDF phụ lục (0..n)")] = None,
) -> ApiResponse[DossierCreatedDTO]:
    """Create dossier via multipart upload — per openapi.yaml createDossier operation.

    Flow:
        1. Validate metadata JSON
        2. Create dossier (name from metadata or contract filename)
        3. Ingest contract file + compute sha256 + store
        4. Ingest each annex file (if any)
        5. Return dossier_id + job_id (None — pipeline trigger happens in BackgroundTasks
           via contract_upload_router.py for the legacy endpoint)

    Note:
        For the canonical multipart upload flow with auto-trigger of pipeline run,
        use the legacy `/dossiers/upload` endpoint — preserved for backward compat.
        This `/dossiers` endpoint mirrors the OpenAPI spec contract.
    """
    # Validate contract file
    if not contract or not contract.filename:
        raise HTTPException(status_code=400, detail="contract file is required")
    if contract.content_type and contract.content_type not in (
        "application/pdf",
        "application/octet-stream",
    ):
        # Warn but don't reject — Sprint 3 local dev sometimes sends octet-stream
        pass

    # Parse metadata
    meta = _parse_upload_metadata(metadata)
    name = meta.name or contract.filename or "Untitled dossier"

    # Build metadata dict from optional tags/notes + any extra fields
    meta_payload: dict[str, Any] = {}
    if meta.tags is not None:
        meta_payload["tags"] = meta.tags
    if meta.notes is not None:
        meta_payload["notes"] = meta.notes
    extras = getattr(meta, "model_extra", None) or {}
    for key, value in extras.items():
        if key not in ("name", "tags", "notes") and value is not None:
            meta_payload[key] = value

    # Create dossier + initial Job (UPLOADED) — per openapi.yaml createDossier
    dossier = await svc.create_dossier(
        name=name,
        batch_id=None,
        metadata=meta_payload or None,
    )
    job = dossier.latest_job()

    # Ingest contract (always role=CONTRACT, order_index=0) → MinIO + DB
    _contract_doc, _size, s3_path = await _ingest_upload_file(
        svc=svc,
        dossier_id=dossier.id,
        file=contract,
        role=DocumentRole.CONTRACT,
        order_index=0,
    )

    # Ingest annexes (role=ANNEX, order_index=1..n)
    annexes = annexes or []
    for idx, annex_file in enumerate(annexes, start=1):
        if not annex_file.filename:
            continue
        await _ingest_upload_file(
            svc=svc,
            dossier_id=dossier.id,
            file=annex_file,
            role=DocumentRole.ANNEX,
            order_index=idx,
        )

    # Publish domain event for async downstream processing (OCR / extraction).
    await publish_event(
        "dossier_events",
        {
            "event": "dossier.uploaded",
            "dossier_id": str(dossier.id),
            "file_path": s3_path,
        },
    )

    # ApiEnvelopeDossierCreated — dossier_id + job_id (openapi.yaml line 2320)
    return ApiResponse(
        data=DossierCreatedDTO(
            dossier_id=dossier.id,
            job_id=job.id if job else None,
        )
    )


# -----------------------------------------------------------------------------
# GET /dossiers — List (Per openapi.yaml line 150)
# -----------------------------------------------------------------------------


@router.get(
    "/dossiers",
    response_model=ApiResponse[list[DossierSummaryDTO]],
    summary="List dossiers",
)
async def list_dossiers(
    svc: ContractServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    has_conflicts: Annotated[bool | None, Query()] = None,
    batch_id: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=200, description="Tìm theo tên dossier")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[list[DossierSummaryDTO]]:
    """Danh sách dossier có filter + pagination. RBAC: any authenticated."""
    items, total = await svc.list_dossiers(
        status=status_filter,
        has_conflicts=has_conflicts,
        q=q,
        batch_id=batch_id,
        limit=limit,
        offset=offset,
    )
    summaries: list[DossierSummaryDTO] = []
    for d in items:
        latest = d.latest_job()
        summaries.append(
            DossierSummaryDTO.from_domain(
                d,
                latest_job_status=latest.status if latest else None,
            )
        )
    return ApiResponse(
        data=summaries,
        meta=ApiMeta(
            total=total,
            page=(offset // limit) + 1,
            page_size=limit,
        ),
    )


# -----------------------------------------------------------------------------
# GET /dossiers/{id} — Detail (Per openapi.yaml line 185)
# -----------------------------------------------------------------------------


@router.get(
    "/dossiers/{dossier_id}",
    response_model=ApiResponse[DossierDetailDTO],
    responses={404: {"description": "Dossier not found"}},
)
async def get_dossier(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ContractServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[DossierDetailDTO]:
    """Dossier detail kèm documents list."""
    dossier = await svc.get_dossier(dossier_id)
    documents = await svc.list_documents(dossier_id)
    latest = dossier.latest_job()
    return ApiResponse(
        data=DossierDetailDTO.from_domain(
            dossier,
            documents=documents,
            latest_job_id=latest.id if latest else None,
            latest_job_status=latest.status if latest else None,
        ),
    )


# -----------------------------------------------------------------------------
# PATCH /dossiers/{id} — Update (Per openapi.yaml line 204)
# -----------------------------------------------------------------------------


@router.patch(
    "/dossiers/{dossier_id}",
    response_model=ApiResponse[DossierDetailDTO],
    responses={
        404: {"description": "Dossier not found"},
        403: {"description": "Insufficient role"},
    },
)
async def patch_dossier(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ContractServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))],
    body: DossierUpdateBody | None = Body(default=None),
) -> ApiResponse[DossierDetailDTO]:
    """Cập nhật metadata (name, metadata, tags, notes). RBAC: OPERATOR, ADMINISTRATOR.

    Body per openapi.yaml DossierUpdateRequest:
        { name?: string, metadata?: object }
    """
    if body is None:
        body = DossierUpdateBody()
    dossier = await svc.patch_dossier(dossier_id, name=body.name, metadata=body.metadata)
    documents = await svc.list_documents(dossier_id)
    latest = dossier.latest_job()
    return ApiResponse(
        data=DossierDetailDTO.from_domain(
            dossier,
            documents=documents,
            latest_job_id=latest.id if latest else None,
            latest_job_status=latest.status if latest else None,
        )
    )


# -----------------------------------------------------------------------------
# GET /dossiers/{id}/documents — List (Per openapi.yaml line 262)
# -----------------------------------------------------------------------------


@router.get(
    "/dossiers/{dossier_id}/documents",
    response_model=ApiResponse[list[DocumentListItemDTO]],
    responses={404: {"description": "Dossier not found"}},
)
async def list_dossier_documents(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ContractServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[list[DocumentListItemDTO]]:
    """Danh sách toàn bộ văn bản trong dossier (contract + annexes)."""
    # Verify dossier exists for proper 404 semantics
    await svc.get_dossier(dossier_id)
    documents = await svc.list_documents(dossier_id)
    return ApiResponse(data=[DocumentListItemDTO.from_domain(d) for d in documents])


# -----------------------------------------------------------------------------
# Document endpoints
# -----------------------------------------------------------------------------


@router.get(
    "/documents/{document_id}",
    response_model=ApiResponse[DocumentDetailDTO],
    responses={404: {"description": "Document not found"}},
)
async def get_document(
    document_id: Annotated[str, Path(min_length=1)],
    svc: ContractServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[DocumentDetailDTO]:
    """Chi tiết document theo spec (DocumentDetail — extends DocumentListItem)."""
    doc = await svc.get_document(document_id)
    return ApiResponse(data=DocumentDetailDTO.from_domain(doc))


@router.get(
    "/documents/{document_id}/content",
    summary="Stream PDF binary từ MinIO/local storage",
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "PDF binary stream",
        },
        404: {"description": "Document not found"},
    },
)
async def get_document_content(
    document_id: Annotated[str, Path(min_length=1)],
    svc: ContractServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> StreamingResponse:
    """Tải PDF gốc — trả về binary stream từ storage."""
    data, filename = await svc.get_document_blob(document_id)
    return StreamingResponse(
        iter([data]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(data)),
        },
    )


__all__ = ["router"]
