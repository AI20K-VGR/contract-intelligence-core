r"""Contract bounded context router — Màn hình 3 (DOC-05b §5.3) + Màn hình 5 §5.5.

Endpoints:
    POST   /dossiers                     — Create dossier (multipart)
    GET    /dossiers                     — List dossiers
    GET    /dossiers/{id}                — Dossier detail
    PATCH  /dossiers/{id}                — Update name/batch
    POST   /dossiers/{id}/documents      — Upload PDF (multipart)
    GET    /dossiers/{id}/documents      — List PDFs in dossier
    GET    /dossiers/{id}/manifest       — Get manifest draft
    POST   /dossiers/{id}/manifest/confirm — Confirm manifest

    GET    /documents/{id}                — Document detail
    GET    /documents/{id}/content        — Stream PDF binary
    GET    /documents/{id}/pages          — List pages (basic — full impl in extraction router)
    GET    /documents/{id}/clauses        — Clause tree (extraction BC provides full)
    GET    /documents/{id}/tables         — Tables list (extraction BC provides full)

RBAC matrix (DOC-05b §2.3):
    OPERATOR, ADMINISTRATOR  → write ops (POST, PATCH, upload, manifest confirm)
    OPERATOR, REVIEWER, ADMIN → read ops
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

from contract_intelligence.contract.domain.entities.document import DocumentRole
from contract_intelligence.contract.interfaces.api.dependencies import (
    ContractServiceDep,
)
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
from contract_intelligence.shared.responses import ApiResponse

router = APIRouter(tags=["Contract"])


# -----------------------------------------------------------------------------
# Dossier endpoints — Màn hình 3
# -----------------------------------------------------------------------------


@router.post(
    "/dossiers",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[dict[str, Any]],
    summary="Create new dossier",
    responses={
        400: {"description": "Missing X-Tenant-Id"},
        403: {"description": "Tenant mismatch"},
    },
)
async def create_dossier(
    svc: ContractServiceDep,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    name: Annotated[str, Form(min_length=1, max_length=255)],
    batch_id: Annotated[str | None, Form()] = None,
) -> ApiResponse[dict[str, Any]]:
    """Tạo dossier mới — chỉ cần name (upload documents sau).

    RBAC: OPERATOR, ADMINISTRATOR.
    """
    if user.role not in ("OPERATOR", "ADMINISTRATOR"):
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient role — required OPERATOR or ADMINISTRATOR, got {user.role!r}",
        )

    dossier = await svc.create_dossier(name=name, batch_id=batch_id)
    return ApiResponse(
        data={
            "id": dossier.id,
            "tenant_id": user.tenant_id,
            "name": dossier.name,
            "batch_id": dossier.batch_id,
            "has_conflicts": dossier.has_conflicts,
            "created_at": dossier.created_at.isoformat(),
            "updated_at": dossier.updated_at.isoformat(),
        }
    )


@router.get(
    "/dossiers",
    response_model=ApiResponse[dict[str, Any]],
    summary="List dossiers",
)
async def list_dossiers(
    svc: ContractServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    has_conflicts: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[dict[str, Any]]:
    """Danh sách dossier có filter + pagination."""
    items, total = await svc.list_dossiers(
        status=status_filter,
        has_conflicts=has_conflicts,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(
        data={
            "items": [
                {
                    "id": d.id,
                    "name": d.name,
                    "batch_id": d.batch_id,
                    "has_conflicts": d.has_conflicts,
                    "created_at": d.created_at.isoformat(),
                    "updated_at": d.updated_at.isoformat(),
                }
                for d in items
            ],
            "total": total,
            "page": (offset // limit) + 1,
            "page_size": limit,
            "total_pages": (total + limit - 1) // limit if total > 0 else 0,
        }
    )


@router.get(
    "/dossiers/{dossier_id}",
    response_model=ApiResponse[dict[str, Any]],
    responses={404: {"description": "Dossier not found"}},
)
async def get_dossier(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ContractServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    """Chi tiết dossier."""
    dossier = await svc.get_dossier(dossier_id)
    documents = await svc.list_documents(dossier_id)
    return ApiResponse(
        data={
            "id": dossier.id,
            "name": dossier.name,
            "batch_id": dossier.batch_id,
            "has_conflicts": dossier.has_conflicts,
            "total_documents": len(documents),
            "documents": [
                {
                    "id": d.id,
                    "filename": d.filename,
                    "role": d.role.value,
                    "page_count": d.page_count,
                }
                for d in documents
            ],
            "created_at": dossier.created_at.isoformat(),
            "updated_at": dossier.updated_at.isoformat(),
        }
    )


@router.patch(
    "/dossiers/{dossier_id}",
    response_model=ApiResponse[dict[str, Any]],
    responses={
        404: {"description": "Dossier not found"},
        403: {"description": "Insufficient role"},
    },
)
async def patch_dossier(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ContractServiceDep,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    name: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
) -> ApiResponse[dict[str, Any]]:
    """Đổi tên hoặc metadata dossier. RBAC: OPERATOR, ADMINISTRATOR."""
    if user.role not in ("OPERATOR", "ADMINISTRATOR"):
        raise HTTPException(status_code=403, detail="Insufficient role")

    dossier = await svc.patch_dossier(dossier_id, name=name)
    return ApiResponse(
        data={
            "id": dossier.id,
            "name": dossier.name,
            "updated_at": dossier.updated_at.isoformat(),
        }
    )


# -----------------------------------------------------------------------------
# Document upload + list — Màn hình 3
# -----------------------------------------------------------------------------


@router.post(
    "/dossiers/{dossier_id}/documents",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[dict[str, Any]],
    summary="Upload PDF vào dossier",
    responses={
        400: {"description": "Bad form data"},
        403: {"description": "Insufficient role"},
        404: {"description": "Dossier not found"},
    },
)
async def upload_document(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ContractServiceDep,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    file: Annotated[UploadFile, File(description="PDF binary")],
    role: Annotated[str, Form(description="CONTRACT | ANNEX")],
    order_index: Annotated[int, Form(ge=0)] = 0,
) -> ApiResponse[dict[str, Any]]:
    """Upload PDF vào dossier. RBAC: OPERATOR, ADMINISTRATOR.

    Multipart: file + role + order_index
    """
    if user.role not in ("OPERATOR", "ADMINISTRATOR"):
        raise HTTPException(status_code=403, detail="Insufficient role")
    if role not in ("CONTRACT", "ANNEX"):
        raise HTTPException(
            status_code=422,
            detail=f"role must be CONTRACT or ANNEX, got {role!r}",
        )

    document = await svc.upload_document(
        dossier_id=dossier_id,
        filename=file.filename or "document.pdf",
        content=file.file,
        role=DocumentRole(role),
        order_index=order_index,
    )
    return ApiResponse(
        data={
            "id": document.id,
            "dossier_id": document.dossier_id,
            "role": document.role.value,
            "order_index": document.order_index,
            "filename": document.filename,
            "sha256": document.sha256,
            "blob_uri": document.blob_uri,
            "page_count": document.page_count,
            "lang_detected": document.lang_detected,
            "created_at": document.created_at.isoformat(),
        }
    )


@router.get(
    "/dossiers/{dossier_id}/documents",
    response_model=ApiResponse[list[Any]],
    summary="List documents trong dossier",
)
async def list_documents(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ContractServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[list[Any]]:
    """Danh sách PDFs kèm role."""
    documents = await svc.list_documents(dossier_id)
    return ApiResponse(
        data=[
            {
                "id": d.id,
                "role": d.role.value,
                "order_index": d.order_index,
                "filename": d.filename,
                "sha256": d.sha256,
                "blob_uri": d.blob_uri,
                "page_count": d.page_count,
                "lang_detected": d.lang_detected,
                "signing_date": d.signing_date,
                "effective_date": d.effective_date,
                "created_at": d.created_at.isoformat(),
            }
            for d in documents
        ]
    )


# -----------------------------------------------------------------------------
# Manifest endpoints — Màn hình 3
# -----------------------------------------------------------------------------


@router.get(
    "/dossiers/{dossier_id}/manifest",
    response_model=ApiResponse[dict[str, Any]],
    summary="Get manifest draft",
)
async def get_manifest(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ContractServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    """Lấy manifest dự thảo (auto-generate nếu chưa có)."""

    # Reuse same service for session/tenant — but we need raw repo access for items
    manifest = await svc.get_or_create_manifest(dossier_id)
    # Note: chúng ta dùng lại service session/tenant từ dependency
    # Manifest items đã được tạo trong get_or_create_manifest
    return ApiResponse(
        data={
            "id": manifest.id,
            "dossier_id": manifest.dossier_id,
            "status": manifest.status,
            "confirmed_at": manifest.confirmed_at.isoformat() if manifest.confirmed_at else None,
            "confirmed_by": manifest.confirmed_by,
            "created_at": manifest.created_at.isoformat(),
        }
    )


@router.post(
    "/dossiers/{dossier_id}/manifest/confirm",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[dict[str, Any]],
    summary="Confirm manifest → trigger deep analysis",
    responses={
        403: {"description": "Insufficient role"},
        404: {"description": "Dossier or manifest not found"},
    },
)
async def confirm_manifest(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ContractServiceDep,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    """Xác nhận phân loại tài liệu. RBAC: OPERATOR, ADMINISTRATOR."""
    if user.role not in ("OPERATOR", "ADMINISTRATOR"):
        raise HTTPException(status_code=403, detail="Insufficient role")

    manifest = await svc.confirm_manifest(dossier_id, user.user_id)
    return ApiResponse(
        data={
            "manifest_id": manifest.id,
            "status": manifest.status,
            "confirmed_at": manifest.confirmed_at.isoformat() if manifest.confirmed_at else None,
            "confirmed_by": manifest.confirmed_by,
        }
    )


# -----------------------------------------------------------------------------
# Document detail & content — Màn hình 5 §5.5
# -----------------------------------------------------------------------------


@router.get(
    "/documents/{document_id}",
    response_model=ApiResponse[dict[str, Any]],
    responses={404: {"description": "Document not found"}},
)
async def get_document(
    document_id: Annotated[str, Path(min_length=1)],
    svc: ContractServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    """Chi tiết document: tổng số trang, ngôn ngữ, filename."""
    doc = await svc.get_document(document_id)
    return ApiResponse(
        data={
            "id": doc.id,
            "dossier_id": doc.dossier_id,
            "role": doc.role.value,
            "filename": doc.filename,
            "sha256": doc.sha256,
            "blob_uri": doc.blob_uri,
            "page_count": doc.page_count,
            "lang_detected": doc.lang_detected,
            "signing_date": doc.signing_date,
            "effective_date": doc.effective_date,
            "created_at": doc.created_at.isoformat(),
        }
    )


@router.get(
    "/documents/{document_id}/content",
    summary="Stream PDF binary",
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
    """Tải PDF gốc — trả về binary stream."""
    data, filename = await svc.get_document_blob(document_id)
    return StreamingResponse(
        iter([data]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(data)),
        },
    )


# Stub endpoints — extraction BC provides full implementation
# Placeholder routes để OpenAPI doc đầy đủ


@router.get(
    "/documents/{document_id}/pages",
    response_model=ApiResponse[dict[str, Any]],
    summary="[STUB] List pages — full impl in extraction router",
)
async def list_pages_stub(
    document_id: Annotated[str, Path(min_length=1)],
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    """Sprint 3 stub — full implementation in extraction_router."""
    return ApiResponse(
        data={
            "items": [],
            "total": 0,
            "note": "See GET /documents/{id}/pages in extraction router",
        }
    )


@router.get(
    "/documents/{document_id}/clauses",
    response_model=ApiResponse[list[Any]],
    summary="[STUB] Clause tree — full impl in extraction router",
)
async def list_clauses_stub(
    document_id: Annotated[str, Path(min_length=1)],
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[list[Any]]:
    return ApiResponse(data=[])


@router.get(
    "/documents/{document_id}/tables",
    response_model=ApiResponse[list[Any]],
    summary="[STUB] Tables — full impl in extraction router",
)
async def list_tables_stub(
    document_id: Annotated[str, Path(min_length=1)],
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[list[Any]]:
    return ApiResponse(data=[])
