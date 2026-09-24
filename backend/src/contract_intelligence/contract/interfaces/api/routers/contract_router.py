r"""Contract bounded context router — Phase 1 endpoints per DOC-05-api-spec.yaml.

Endpoints (Phase 1: Core Document Ingestion):
    POST   /dossiers                     — Multipart upload (per spec line 116-148)
    GET    /dossiers                     — List dossiers (spec line 150-183)
    GET    /dossiers/{id}                — Dossier detail (spec line 185-204)
    PATCH  /dossiers/{id}                — Update metadata (spec line 204-228)
    DELETE /dossiers/{id}                — Tombstone + schedule content purge
    GET    /dossiers/{id}/documents      — List documents (spec line 262-277)
    GET    /documents/{id}               — Document detail (spec line ~759)
    GET    /documents/{id}/content       — Stream PDF binary

RBAC matrix (DOC-05b §2.3):
    OPERATOR, ADMINISTRATOR  → write ops (POST, PATCH, DELETE, upload, manifest confirm)
    OPERATOR, REVIEWER, ADMINISTRATOR  → read ops

Layer: interfaces/api — composes application services, never directly hits ORM.
"""

from __future__ import annotations

import asyncio
import json
from io import BytesIO
from typing import Annotated, Any, Literal
from urllib.parse import quote

import structlog
from fastapi import (
    APIRouter,
    BackgroundTasks,
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
from pydantic import BaseModel, ConfigDict

from contract_intelligence.admin.activity_feed import record_activity
from contract_intelligence.contract.application.dtos.deletion_dtos import DossierDeletedDTO
from contract_intelligence.contract.application.dtos.document_dtos import (
    DocumentDetailDTO,
    DocumentListItemDTO,
)
from contract_intelligence.contract.application.dtos.dossier_dtos import (
    DossierCreatedDTO,
    DossierDetailDTO,
    DossierSummaryDTO,
)
from contract_intelligence.contract.application.dtos.manifest_dtos import (
    ConfirmManifestRequest,
    ManifestDTO,
)
from contract_intelligence.contract.domain.entities.document import (
    Document,
    DocumentRole,
)
from contract_intelligence.contract.infrastructure.persistence.dossier_deletion_service import (
    run_dossier_purge,
)
from contract_intelligence.contract.interfaces.api.dependencies import (
    ContractServiceDep,
    DossierDeletionServiceDep,
)
from contract_intelligence.infrastructure import messaging, storage
from contract_intelligence.shared.auth import (
    AuthenticatedUser,
    get_current_user,
    require_role,
)
from contract_intelligence.shared.auth.tenant import get_tenant_id
from contract_intelligence.shared.exceptions import NotFoundError
from contract_intelligence.shared.persistence import get_session_factory
from contract_intelligence.shared.responses import ApiMeta, ApiResponse
from contract_intelligence.shared.utils import safe_filename

router = APIRouter(tags=["Contract"])
logger = structlog.get_logger(__name__)


async def _record(
    *,
    tenant_id: str,
    title: str,
    actor_display_name: str | None,
    detail: str | None,
    kind: str,
) -> None:
    """Best-effort journal row. A feed failure must not undo the dossier action.

    Unit tests call these routes without a bound engine. Skip the row then.
    """
    try:
        factory = get_session_factory()
    except RuntimeError:
        return
    try:
        async with factory() as session:
            await record_activity(
                session,
                tenant_id=tenant_id,
                title=title,
                actor_display_name=actor_display_name,
                detail=detail,
                kind=kind,
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("activity.record_failed", kind=kind, error=str(exc))


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


class AccessGrantBody(BaseModel):
    id: str
    email: str = ""
    display_name: str = ""
    status: Literal["invited", "active", "disabled"] | None = None


class DossierAccessBody(BaseModel):
    """Quyền truy cập hồ sơ: của tôi, đã chia sẻ, được chia sẻ."""

    scope: Literal["mine", "shared_out", "shared_in"]
    shared_with: list[AccessGrantBody] = []


class DossierAccessDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dossier_id: str
    scope: Literal["mine", "shared_out", "shared_in"]
    shared_with: list[AccessGrantBody]


def _can_read_dossier(metadata: dict[str, Any] | None, user_id: str) -> bool:
    """Chủ hồ sơ luôn xem được. Người được chia sẻ chỉ xem khi quyền đang bật."""
    meta = metadata or {}
    owner = meta.get("created_by")
    if not isinstance(owner, str) or not owner:
        return True
    if owner == user_id:
        return True
    if meta.get("access_scope") == "mine":
        return False
    shares = meta.get("shared_with") or []
    return any(isinstance(item, dict) and item.get("id") == user_id for item in shares)


async def _require_readable(svc: Any, dossier_id: str, user_id: str) -> Any:
    dossier = await svc.get_dossier(dossier_id)
    if not _can_read_dossier(dossier.metadata, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Quyền xem hồ sơ này đã bị thu hồi.",
        )
    return dossier


def _send_share_emails(
    *,
    dossier_name: str,
    dossier_id: str,
    sender_name: str,
    recipients: list[dict[str, Any]],
) -> None:
    """Người chưa đăng nhập nhận lại thư đặt mật khẩu. Người đã đăng nhập nhận thư mở hồ sơ."""
    import os
    import smtplib
    import ssl
    from email.message import EmailMessage
    from html import escape

    from contract_intelligence.infrastructure.keycloak_admin import send_share_login_email_sync

    pending: list[dict[str, Any]] = []
    for person in recipients:
        user_id = str(person.get("id") or "").strip()
        must_set_password = person.get("status") == "invited"
        if user_id:
            try:
                if send_share_login_email_sync(
                    user_id=user_id,
                    email=str(person.get("email") or ""),
                    dossier_name=dossier_name,
                    sender_name=sender_name,
                    require_password=must_set_password,
                ):
                    continue
            except Exception:
                logger.warning("dossiers.access.login_email_failed", user_id=user_id, exc_info=True)
                if must_set_password:
                    continue
        elif must_set_password:
            continue
        pending.append(person)
    if not pending:
        return

    host = os.environ.get("SMTP_HOST", "mailpit")
    port = int(os.environ.get("SMTP_PORT", "1025"))
    sender = os.environ.get("SMTP_FROM", "lexis@localhost")
    user = (os.environ.get("SMTP_USER") or "").strip()
    password = os.environ.get("SMTP_PASSWORD") or ""
    starttls = os.environ.get("SMTP_STARTTLS", "").lower() in {"1", "true", "yes"}
    base = os.environ.get("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")
    link = f"{base}/cau-truc/{dossier_id}"
    safe_sender = escape(sender_name)
    safe_name = escape(dossier_name)
    safe_link = escape(link, quote=True)
    html = f"""<!DOCTYPE html>
<html lang="vi"><body style="margin:0;padding:0;background-color:#f8f9ff;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
 style="background-color:#f8f9ff;padding:32px 16px;"><tr><td align="center">
<table role="presentation" width="420" cellpadding="0" cellspacing="0"
 style="width:100%;max-width:420px;background-color:#ffffff;border-radius:8px;
 overflow:hidden;">
<tr><td style="height:4px;background-color:#0b1f3a;font-size:0;line-height:0;">
&nbsp;</td></tr>
<tr><td style="padding:32px;font-family:Arial,Helvetica,sans-serif;color:#0b1c30;">
<p style="margin:0 0 24px;font-size:12px;line-height:16px;letter-spacing:0.08em;
 font-weight:600;color:#0b1f3a;">LEXIS CONTRACT INTELLIGENCE</p>
<h1 style="margin:0 0 8px;font-size:18px;line-height:24px;font-weight:600;
 color:#0b1c30;">Bạn được chia sẻ hồ sơ</h1>
<p style="margin:0 0 24px;font-size:14px;line-height:20px;color:#545f73;">
{safe_sender} đã chia sẻ hồ sơ "{safe_name}" với bạn.</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
 style="margin:0 0 24px;"><tr>
<td align="center" style="background-color:#0b1f3a;border-radius:4px;">
<a href="{safe_link}" style="display:block;padding:12px 24px;
 font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:20px;
 font-weight:600;color:#ffffff;text-decoration:none;">Mở hồ sơ</a>
</td></tr></table>
<p style="margin:0;font-size:12px;line-height:16px;color:#75777e;
 word-break:break-all;">{safe_link}</p>
</td></tr></table>
<p style="margin:16px 0 0;font-family:Arial,Helvetica,sans-serif;font-size:12px;
 line-height:16px;color:#545f73;">© 2025 Lexis Contract Intelligence</p>
</td></tr></table></body></html>"""
    with smtplib.SMTP(host, port, timeout=20) as smtp:
        smtp.ehlo()
        if starttls:
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
        if user and password:
            smtp.login(user, password)
        for person in pending:
            address = str(person.get("email") or "").strip()
            if not address:
                continue
            message = EmailMessage()
            message["Subject"] = f"Bạn được chia sẻ hồ sơ {dossier_name}"
            message["From"] = sender
            message["To"] = address
            message.set_content(
                f'{sender_name} đã chia sẻ hồ sơ "{dossier_name}" với bạn.\n\nMở hồ sơ:\n{link}\n'
            )
            message.add_alternative(html, subtype="html")
            smtp.send_message(message)


async def _ingest_upload_file(
    *,
    svc: Any,
    dossier_id: str,
    file: UploadFile,
    role: DocumentRole,
    order_index: int,
) -> tuple[Document, int, str]:
    """Đọc UploadFile → MinIO → persist Document (compensate MinIO on DB failure).

    Returns:
        (Document entity, size_bytes, s3_path) — s3_path dùng cho Kafka event.
    """
    chunks: list[bytes] = []
    total_size = 0
    while chunk := await file.read(1024 * 1024):
        chunks.append(chunk)
        total_size += len(chunk)
    raw_bytes = b"".join(chunks)

    filename = safe_filename(file.filename, fallback=f"{role.value.lower()}.pdf")
    object_key = f"{dossier_id}/{order_index:02d}_{filename}"
    s3_path: str | None = None
    try:
        s3_path = await storage.upload_file(object_key, raw_bytes)
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
    except Exception:
        if s3_path:
            try:
                await storage.delete_object(s3_path)
            except Exception:
                logger.warning(
                    "dossier.ingest.compensate_minio_failed",
                    dossier_id=dossier_id,
                    s3_path=s3_path,
                    exc_info=True,
                )
        raise


async def _publish_dossier_uploaded(*, dossier_id: str, file_path: str) -> None:
    """Post-commit Kafka publish — runs via BackgroundTasks after DB commit."""
    await messaging.publish_event(
        "dossier_events",
        {
            "event": "dossier.uploaded",
            "dossier_id": str(dossier_id),
            "file_path": file_path,
        },
    )


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
    background_tasks: BackgroundTasks,
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
        if (
            key not in ("name", "tags", "notes", "created_by", "created_by_name")
            and value is not None
        ):
            meta_payload[key] = value
    meta_payload["created_by"] = user.user_id
    meta_payload["created_by_name"] = user.display_name

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

    # Publish after the request session commits (BackgroundTasks run post-response).
    background_tasks.add_task(
        _publish_dossier_uploaded,
        dossier_id=str(dossier.id),
        file_path=s3_path,
    )

    # ApiEnvelopeDossierCreated — dossier_id + job_id (openapi.yaml line 2320)
    return ApiResponse(
        data=DossierCreatedDTO(
            dossier_id=dossier.id,
            job_id=job.id if job else None,
        )
    )


class OcrRestartDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dossier_id: str
    status: str


@router.post(
    "/dossiers/{dossier_id}/ocr",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[OcrRestartDTO],
    summary="Chạy lại OCR cho hồ sơ đã tải",
    responses={404: {"description": "Dossier or document not found"}},
)
async def restart_dossier_ocr(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ContractServiceDep,
    user: Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))],
) -> ApiResponse[OcrRestartDTO]:
    """Đăng lại dossier.uploaded để worker gửi lệnh OCR."""
    dossier = await svc.get_dossier(dossier_id)
    documents = await svc.list_documents(dossier_id)
    if not documents:
        raise HTTPException(status_code=404, detail="Dossier has no document to OCR")
    await messaging.publish_event(
        "dossier_events",
        {
            "event": "dossier.uploaded",
            "dossier_id": str(dossier_id),
        },
    )
    await _record(
        tenant_id=user.tenant_id,
        title=f"Chạy lại OCR hồ sơ {dossier.name}",
        actor_display_name=user.email or user.display_name,
        detail=None,
        kind="dossier.ocr_restart",
    )
    return ApiResponse(data=OcrRestartDTO(dossier_id=dossier_id, status="queued"))


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
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
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
        viewer_id=user.user_id,
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


@router.delete(
    "/dossiers/{dossier_id}",
    response_model=ApiResponse[DossierDeletedDTO],
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        404: {"description": "Dossier not found"},
        403: {"description": "Insufficient role"},
    },
    summary="Xóa hồ sơ (tombstone + purge async)",
)
async def delete_dossier(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ContractServiceDep,
    deletion_svc: DossierDeletionServiceDep,
    background_tasks: BackgroundTasks,
    user: Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))],
    tenant_id: Annotated[str, Depends(get_tenant_id)],
) -> ApiResponse[DossierDeletedDTO]:
    """Bước 1: tombstone sync. Bước 2: purge nội dung chạy sau commit (BackgroundTasks).

    Không DELETE cascade dossier/job/pipeline_run — giữ usage_ledger và audit.
    RBAC: OPERATOR, ADMINISTRATOR.
    """
    dossier_name: str | None = None
    try:
        dossier_name = (await svc.get_dossier(dossier_id)).name
    except NotFoundError:
        dossier_name = None
    result = await deletion_svc.tombstone(dossier_id, actor_user_id=user.user_id)
    if not result.already_tombstoned:
        title = "Xóa hồ sơ" if result.name == "[deleted]" else f"Xóa hồ sơ {result.name}"
        await record_activity(
            deletion_svc.session,
            tenant_id=tenant_id,
            title=title,
            actor_display_name=user.email or user.display_name,
            detail=None,
            kind=f"dossier.deleted:{dossier_id}",
        )
        await deletion_svc.commit()
        background_tasks.add_task(
            run_dossier_purge,
            dossier_id=dossier_id,
            tenant_id=tenant_id,
        )
        title = f"Xóa hồ sơ {dossier_name}" if dossier_name else "Xóa hồ sơ"
        await _record(
            tenant_id=tenant_id,
            title=title,
            actor_display_name=user.email or user.display_name,
            detail=None,
            kind=f"dossier.deleted:{dossier_id}",
        )
    return ApiResponse(
        data=DossierDeletedDTO(
            dossier_id=result.dossier_id,
            deleted_at=result.deleted_at,
            purge_status=result.purge_status,
        )
    )


class DossierSearchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str


class DossierSearchHit(BaseModel):
    text: str
    page_no: int | None = None


class DossierSearchDTO(BaseModel):
    query: str
    answer: str | None
    connected: bool
    hits: list[DossierSearchHit]


def _hits_from_ai2(payload: dict[str, Any]) -> list[DossierSearchHit]:
    raw = payload.get("hits") or payload.get("citations") or []
    if not isinstance(raw, list):
        return []
    hits: list[DossierSearchHit] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = item.get("text") or item.get("quote") or item.get("snippet")
        if not isinstance(text, str) or not text.strip():
            continue
        page = item.get("page_no") or item.get("page")
        hits.append(
            DossierSearchHit(
                text=text.strip(),
                page_no=page if isinstance(page, int) else None,
            )
        )
    return hits


@router.post(
    "/dossiers/{dossier_id}/search",
    response_model=ApiResponse[DossierSearchDTO],
    responses={404: {"description": "Dossier not found"}},
    summary="Hỏi đáp trên hồ sơ (AI2)",
)
async def search_dossier(
    dossier_id: Annotated[str, Path(min_length=1)],
    body: DossierSearchBody,
    svc: ContractServiceDep,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[DossierSearchDTO]:
    """Nhận câu hỏi từ thanh search. AI2 trả câu trả lời khi đã nối."""
    question = body.query.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Thiếu câu hỏi.")
    await _require_readable(svc, dossier_id, user.user_id)
    from contract_intelligence.infrastructure.ai_adapters import (
        AiAdapterError,
        query_ai2,
    )

    try:
        payload = await asyncio.wait_for(
            query_ai2(
                {
                    "query": question,
                    "dossier_id": dossier_id,
                    "snapshot_version": "current",
                    "acl_context": user.user_id,
                    "policy_flags": {},
                }
            ),
            timeout=3,
        )
    except (AiAdapterError, TimeoutError, OSError) as exc:
        logger.info("dossier.search.ai2_unavailable", dossier_id=dossier_id, error=str(exc))
        return ApiResponse(
            data=DossierSearchDTO(query=question, answer=None, connected=False, hits=[])
        )
    if not isinstance(payload, dict):
        payload = {}
    answer = payload.get("answer") or payload.get("text")
    return ApiResponse(
        data=DossierSearchDTO(
            query=question,
            answer=answer.strip() if isinstance(answer, str) and answer.strip() else None,
            connected=True,
            hits=_hits_from_ai2(payload),
        )
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
    dossier = await _require_readable(svc, dossier_id, _user.user_id)
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
    user: Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))],
    body: DossierUpdateBody | None = Body(default=None),
) -> ApiResponse[DossierDetailDTO]:
    """Cập nhật metadata (name, metadata, tags, notes). RBAC: OPERATOR, ADMINISTRATOR.

    Body per openapi.yaml DossierUpdateRequest:
        { name?: string, metadata?: object }
    """
    if body is None:
        body = DossierUpdateBody()
    dossier = await svc.patch_dossier(dossier_id, name=body.name, metadata=body.metadata)
    await _record(
        tenant_id=user.tenant_id,
        title=f"Sửa hồ sơ {dossier.name}",
        actor_display_name=user.email or user.display_name,
        detail=None,
        kind="dossier.updated",
    )
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


@router.put(
    "/dossiers/{dossier_id}/access",
    response_model=ApiResponse[DossierAccessDTO],
    responses={404: {"description": "Dossier not found"}},
)
async def update_dossier_access(
    dossier_id: Annotated[str, Path(min_length=1)],
    body: DossierAccessBody,
    svc: ContractServiceDep,
    user: Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))],
) -> ApiResponse[DossierAccessDTO]:
    """Đặt quyền hồ sơ. Gộp vào metadata, giữ created_by."""
    dossier = await svc.get_dossier(dossier_id)
    current = dict(dossier.metadata or {})
    previous_ids = {
        str(item.get("id"))
        for item in (current.get("shared_with") or [])
        if isinstance(item, dict) and item.get("id")
    }
    current.setdefault("created_by", user.user_id)
    current.setdefault("created_by_name", user.display_name)
    grants = [] if body.scope == "mine" else [item.model_dump() for item in body.shared_with]
    if body.scope == "shared_in" and user.user_id not in {item["id"] for item in grants}:
        grants.append(
            {
                "id": user.user_id,
                "email": user.email or "",
                "display_name": user.display_name or "",
            }
        )
    current["access_scope"] = body.scope
    current["shared_with"] = grants
    await svc.patch_dossier(dossier_id, name=None, metadata=current)
    scope_label = "Chỉ mình tôi" if body.scope == "mine" else "Chia sẻ với người khác"
    await _record(
        tenant_id=user.tenant_id,
        title=f"Cập nhật quyền hồ sơ {dossier.name}",
        actor_display_name=user.email or user.display_name,
        detail=scope_label,
        kind="dossier.access",
    )
    fresh = [item for item in grants if item["id"] not in previous_ids and item.get("email")]
    if body.scope == "shared_out" and fresh:
        try:
            await asyncio.to_thread(
                _send_share_emails,
                dossier_name=dossier.name,
                dossier_id=dossier_id,
                sender_name=user.display_name or user.email or "Một người dùng",
                recipients=fresh,
            )
        except Exception:
            logger.warning("dossiers.access.email_failed", dossier_id=dossier_id, exc_info=True)
    return ApiResponse(
        data=DossierAccessDTO(
            dossier_id=dossier_id,
            scope=body.scope,
            shared_with=[AccessGrantBody.model_validate(item) for item in grants],
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
    await _require_readable(svc, dossier_id, _user.user_id)
    documents = await svc.list_documents(dossier_id)
    return ApiResponse(data=[DocumentListItemDTO.from_domain(d) for d in documents])


# -----------------------------------------------------------------------------
# GET /dossiers/{id}/manifest — current ManifestDTO
# -----------------------------------------------------------------------------


@router.get(
    "/dossiers/{dossier_id}/manifest",
    response_model=ApiResponse[ManifestDTO],
    responses={
        403: {"description": "Insufficient role (OPERATOR or ADMINISTRATOR required)"},
        404: {"description": "Dossier not found in tenant"},
    },
)
async def get_dossier_manifest(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ContractServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))],
) -> ApiResponse[ManifestDTO]:
    """Return the current ManifestDTO (creates a pending draft if none exists).

    RBAC: OPERATOR, ADMINISTRATOR only — REVIEWER receives 403.
    Wrong tenant / missing dossier → 404.
    """
    data = await svc.get_manifest(dossier_id)
    return ApiResponse(data=data)


# -----------------------------------------------------------------------------
# POST /dossiers/{id}/manifest/confirm — confirm membership + relations
# -----------------------------------------------------------------------------


@router.post(
    "/dossiers/{dossier_id}/manifest/confirm",
    response_model=ApiResponse[ManifestDTO],
    responses={
        403: {"description": "Insufficient role (OPERATOR or ADMINISTRATOR required)"},
        404: {"description": "Dossier not found in tenant"},
        409: {"description": "manifest_version_conflict"},
        422: {"description": "Manifest validation failed"},
    },
)
async def confirm_dossier_manifest(
    dossier_id: Annotated[str, Path(min_length=1)],
    body: ConfirmManifestRequest,
    svc: ContractServiceDep,
    user: Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))],
) -> ApiResponse[ManifestDTO]:
    """Confirm manifest within one DB transaction.

    Validates version, membership, and relations; does not delete excluded
    files and does not start a pipeline run.
    """
    data = await svc.confirm_manifest(dossier_id, user.user_id, body)
    return ApiResponse(data=data)


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


def _content_disposition(filename: str) -> str:
    """Giá trị header phải là latin-1. Tên tiếng Việt đi ở filename*."""
    fallback = "".join(ch if ord(ch) < 128 else "_" for ch in filename).replace('"', "")
    if not fallback.strip("._"):
        fallback = "document.pdf"
    encoded = quote(filename, safe="")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"


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
            "Content-Disposition": _content_disposition(filename),
            "Content-Length": str(len(data)),
        },
    )


__all__ = ["router"]
