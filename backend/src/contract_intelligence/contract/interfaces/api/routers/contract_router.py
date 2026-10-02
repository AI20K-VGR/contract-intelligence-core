# ruff: noqa: E501

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
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from typing import Annotated, Any, Literal, TypeVar
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
from pydantic import BaseModel, ConfigDict, Field

from contract_intelligence.admin.activity_feed import record_activity
from contract_intelligence.api.dossier_guard import (
    acl_document,
    acl_dossier,
)
from contract_intelligence.config.settings import get_settings
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
    MAX_DOSSIER_DOCUMENTS,
    Document,
    DocumentRole,
)
from contract_intelligence.contract.domain.entities.job import JobStatus
from contract_intelligence.contract.infrastructure.persistence.dossier_deletion_service import (
    run_dossier_purge,
)
from contract_intelligence.contract.interfaces.api.dependencies import (
    ContractServiceDep,
    DossierDeletionServiceDep,
)
from contract_intelligence.infrastructure import messaging, storage
from contract_intelligence.shared.acl import (
    AclAction,
    dossier_access_decision,
    dossier_denied_detail,
    visible_dossier_metadata,
)
from contract_intelligence.shared.auth import (
    AuthenticatedUser,
    get_current_user,
    require_role,
)
from contract_intelligence.shared.auth.tenant import get_tenant_id
from contract_intelligence.shared.base import utcnow
from contract_intelligence.shared.exceptions import (
    DomainErrorCode,
    DossierTooManyDocuments,
    InvalidStateTransition,
    ManifestValidationError,
    NotFoundError,
)
from contract_intelligence.shared.pdf import InvalidPdfError, count_pdf_pages, extract_pdf_pages
from contract_intelligence.shared.persistence import get_session_factory
from contract_intelligence.shared.query_policy import (
    QueryLimitExceeded,
    enforce_query_limits,
    enforce_result_acl,
    save_query_trace,
    server_query_policy_flags,
)
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
    # "read": xem; "edit": xem + thẩm định, chạy lại, sửa hồ sơ. Bỏ trống = "edit"
    # (giữ hành vi cũ cho client chưa gửi trường này).
    permission: Literal["read", "edit"] = "edit"
    # Hết hạn thì quyền không còn tác dụng (API trả 403). None = không hết hạn.
    expires_at: datetime | None = None


class DossierAccessBody(BaseModel):
    """Quyền truy cập hồ sơ: của tôi, đã chia sẻ, được chia sẻ."""

    scope: Literal["mine", "shared_out", "shared_in"]
    shared_with: list[AccessGrantBody] = []


class DossierAccessDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dossier_id: str
    scope: Literal["mine", "shared_out", "shared_in"]
    shared_with: list[AccessGrantBody]


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _parse_expiry(value: Any) -> datetime | None:
    """Stored ``expires_at`` as an aware UTC instant; None when absent or unreadable."""
    if not value:
        return None
    try:
        return _as_utc(datetime.fromisoformat(str(value)))
    except ValueError:
        return None


def _stored_grant(item: AccessGrantBody) -> dict[str, Any]:
    """Grant as kept in metadata; ``expires_at`` as UTC ISO so SQL can compare it as text."""
    grant = item.model_dump()
    grant["expires_at"] = (
        _as_utc(item.expires_at).isoformat(timespec="seconds") if item.expires_at else None
    )
    return grant


def _can_read_dossier(metadata: dict[str, Any] | None, user_id: str) -> bool:
    """Chủ hồ sơ luôn xem được. Người được chia sẻ chỉ xem khi quyền đang bật."""
    principal = AuthenticatedUser(
        user_id=user_id,
        tenant_id="",
        email="",
        display_name="",
        role="OPERATOR",
    )
    return dossier_access_decision(
        action=AclAction.QUERY,
        principal=principal,
        dossier_id="legacy",
        dossier_tenant_id="",
        metadata=metadata,
    )


async def _require_readable(
    svc: Any,
    dossier_id: str,
    user: AuthenticatedUser,
    *,
    action: AclAction = AclAction.QUERY,
) -> Any:
    dossier = await svc.get_dossier(dossier_id)
    decision: dict[str, Any] = {
        "action": action,
        "principal": user,
        "dossier_id": dossier_id,
        "dossier_tenant_id": getattr(dossier, "tenant_id", user.tenant_id),
        "metadata": dossier.metadata,
    }
    if not dossier_access_decision(**decision):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=dossier_denied_detail(**decision),
        )
    return dossier


_DossierDTO = TypeVar("_DossierDTO", DossierSummaryDTO, DossierDetailDTO)


def _for_viewer(dto: _DossierDTO, user: AuthenticatedUser) -> _DossierDTO:
    """Chỉ chủ hồ sơ / quản trị viên thấy toàn bộ ``shared_with``."""
    return dto.model_copy(update={"metadata": visible_dossier_metadata(dto.metadata, user)})


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


@dataclass(frozen=True, slots=True)
class _PdfUpload:
    file: UploadFile
    data: bytes
    page_count: int


async def _read_pdf_upload(file: UploadFile) -> _PdfUpload:
    """Read one uploaded PDF (size-capped) and count its pages.

    Raises 413 above ``upload_max_file_bytes`` and 422 for a file that is not a
    readable PDF, so a bad file is refused before anything is stored or sent
    to AI1 — and AI1 gets the real page range (one render URL per page).
    """
    limit = get_settings().upload_max_file_bytes
    chunks: list[bytes] = []
    total_size = 0
    while chunk := await file.read(1024 * 1024):
        total_size += len(chunk)
        if total_size > limit:
            raise HTTPException(
                status_code=413,
                detail=f"{file.filename}: file exceeds {limit // (1024 * 1024)} MB",
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    try:
        page_count = await asyncio.to_thread(count_pdf_pages, data)
    except InvalidPdfError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"{file.filename}: {exc}",
        ) from exc
    return _PdfUpload(file=file, data=data, page_count=page_count)


async def _ingest_upload_file(
    *,
    svc: Any,
    dossier_id: str,
    upload: _PdfUpload,
    role: DocumentRole,
    order_index: int,
) -> tuple[Document, int, str]:
    """Validated upload → MinIO → persist Document (compensate MinIO on DB failure).

    Returns:
        (Document entity, size_bytes, s3_path) — s3_path dùng cho Kafka event.
    """
    file = upload.file
    raw_bytes = upload.data
    total_size = len(raw_bytes)

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
            page_count=upload.page_count,
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
        422: {
            "description": (
                "Invalid metadata JSON, or more than 6 files (`DOSSIER_TOO_MANY_DOCUMENTS`)"
            )
        },
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
        5. Commit, then publish ``dossier.uploaded`` (post-response) — the Kafka
           worker opens the pipeline run and sends the AI1 OCR commands
        6. Return dossier_id + job_id

    This is the only dossier upload endpoint (the in-process
    ``/dossiers/upload`` pipeline was removed).
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

    # AI2 takes at most 6 documents per dossier (DEC-BE-AI2-01 D5): refuse
    # before reading any file, so nothing is created.
    file_count = 1 + sum(1 for annex_file in annexes or [] if annex_file.filename)
    if file_count > MAX_DOSSIER_DOCUMENTS:
        raise DossierTooManyDocuments(limit=MAX_DOSSIER_DOCUMENTS, count=file_count)

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

    # Read + validate every file (size, readable PDF, page count) before
    # anything is created, so a bad annex leaves no half-made dossier behind.
    contract_upload = await _read_pdf_upload(contract)
    annex_uploads = [
        (idx, await _read_pdf_upload(annex_file))
        for idx, annex_file in enumerate(annexes or [], start=1)
        if annex_file.filename
    ]

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
        upload=contract_upload,
        role=DocumentRole.CONTRACT,
        order_index=0,
    )

    # Ingest annexes (role=ANNEX, order_index=1..n)
    for idx, annex_upload in annex_uploads:
        await _ingest_upload_file(
            svc=svc,
            dossier_id=dossier.id,
            upload=annex_upload,
            role=DocumentRole.ANNEX,
            order_index=idx,
        )

    # A file holding a contract and its annexes (metadata.split_pending) waits
    # for POST /dossiers/{id}/split: no OCR yet, so no page is read twice.
    split_pending = meta_payload.get("split_pending") is True
    if not split_pending:
        # Vai trò hợp đồng/phụ lục đã chọn lúc tải lên. Xác nhận luôn để worker
        # so sánh xung đột khi OCR của mọi tệp xong, không chờ màn manifest.
        await svc.confirm_uploaded_manifest(dossier.id, user.user_id)

    # Commit before the 202 is sent. Otherwise the next GET/PATCH and the
    # dossier.uploaded consumer race an uncommitted transaction.
    await svc.commit()

    if not split_pending:
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


class SplitPartBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    role: Literal["contract", "annex"]


class DossierSplitBody(BaseModel):
    """Khoảng trang của từng tài liệu trong file trộn, theo thứ tự trang."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    parts: list[SplitPartBody] = Field(min_length=1, max_length=50)


class SplitDocumentDTO(BaseModel):
    id: str
    role: str
    filename: str
    page_start: int
    page_end: int
    page_count: int


class DossierSplitDTO(BaseModel):
    dossier_id: str
    status: str
    documents: list[SplitDocumentDTO]


def _check_split_parts(parts: list[SplitPartBody], page_count: int) -> str | None:
    """Parts must cover 1..page_count in order, without gap or overlap."""
    expected = 1
    for part in parts:
        if part.page_end < part.page_start:
            return f"page_end {part.page_end} < page_start {part.page_start}"
        if part.page_start != expected:
            return f"part starting at page {part.page_start}: expected page {expected}"
        expected = part.page_end + 1
    if expected != page_count + 1:
        return f"parts cover pages 1-{expected - 1}, the file has {page_count}"
    return None


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
    dossier = await _require_readable(svc, dossier_id, user, action=AclAction.DOSSIER_EDIT)
    documents = await svc.list_documents(dossier_id)
    if not documents:
        raise HTTPException(status_code=404, detail="Dossier has no document to OCR")
    await messaging.publish_event(
        "dossier_events",
        {
            "event": "dossier.uploaded",
            "dossier_id": str(dossier_id),
            "restart": True,
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


_AI2_RETRYABLE_ERRORS = frozenset({"AI2_PROCESSING_FAILED", "AI2_TIMEOUT"})


@router.post(
    "/dossiers/{dossier_id}/ocr/retry-failed",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[OcrRestartDTO],
    summary="Chạy lại OCR chỉ cho tài liệu lỗi; tài liệu đã xong được giữ",
    responses={
        404: {"description": "Dossier not found"},
        409: {"description": "Latest job did not fail at the OCR step"},
    },
)
async def retry_failed_dossier_ocr(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ContractServiceDep,
    user: Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))],
) -> ApiResponse[OcrRestartDTO]:
    """Mở run mới mang theo kết quả OCR của các tài liệu đã xong ở run lỗi.

    Worker chỉ gửi lệnh OCR cho tài liệu còn thiếu. Nếu mọi tài liệu đã có kết
    quả (kết quả tới sau khi run lỗi cũng được giữ), run chuyển thẳng sang AI2.
    Chỉ nhận khi job mới nhất FAILED ở bước OCR; lỗi AI2 dùng ``/ai2/retry``.
    """
    dossier = await _require_readable(svc, dossier_id, user, action=AclAction.DOSSIER_EDIT)
    job = dossier.latest_job()
    if (
        job is None
        or job.current_run_id is None
        or job.status != JobStatus.FAILED
        or job.error_code in _AI2_RETRYABLE_ERRORS
    ):
        raise HTTPException(
            status_code=409,
            detail="Chỉ chạy lại phần lỗi khi hồ sơ lỗi ở bước OCR; lỗi AI2 dùng chạy lại AI2.",
        )
    await messaging.publish_event(
        "dossier_events",
        {
            "event": "dossier.uploaded",
            "dossier_id": str(dossier_id),
            "restart": True,
            "retry_failed": True,
        },
    )
    await _record(
        tenant_id=user.tenant_id,
        title=f"Chạy lại phần OCR lỗi của hồ sơ {dossier.name}",
        actor_display_name=user.email or user.display_name,
        detail=None,
        kind="dossier.ocr_retry_failed",
    )
    return ApiResponse(data=OcrRestartDTO(dossier_id=dossier_id, status="queued"))


@router.post(
    "/dossiers/{dossier_id}/split",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[DossierSplitDTO],
    summary="Tách file trộn (hợp đồng + phụ lục) thành từng tài liệu rồi xử lý",
    responses={
        404: {"description": "Dossier or document not found"},
        409: {"description": "Processing already started, or manifest confirmed"},
        422: {
            "description": (
                "Parts do not cover the file; not exactly one contract "
                "(`contract_required`, `contract_not_unique`); or more than 6 documents "
                "(`DOSSIER_TOO_MANY_DOCUMENTS`)"
            )
        },
    },
)
async def split_dossier_document(
    dossier_id: Annotated[str, Path(min_length=1)],
    body: DossierSplitBody,
    svc: ContractServiceDep,
    user: Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))],
    background_tasks: BackgroundTasks,
) -> ApiResponse[DossierSplitDTO]:
    """Người dùng xác nhận khoảng trang và vai trò của từng phần.

    Chỉ cho hồ sơ tải lên với ``metadata.split_pending = true`` và chưa bắt đầu
    xử lý, nên không trang nào bị OCR hai lần. Mỗi phần thành một tài liệu
    (PDF cắt từ file gốc, sha256 riêng); file gốc bị bỏ. Một phần duy nhất phủ
    cả file = không cần tách. Sau đó vai trò được xác nhận và mọi tài liệu
    được gửi OCR riêng, như khi tải lên từng file.
    """
    dossier = await _require_readable(svc, dossier_id, user, action=AclAction.DOSSIER_EDIT)
    metadata = dict(dossier.metadata or {})
    job = dossier.latest_job()
    if metadata.get("split_pending") is not True or job is None or job.status != JobStatus.UPLOADED:
        raise HTTPException(
            status_code=409,
            detail="Hồ sơ không chờ tách file, hoặc đã bắt đầu xử lý (tách lúc này sẽ OCR lại).",
        )
    source = await svc.get_document(body.document_id)
    if source.dossier_id != dossier_id or not source.blob_uri:
        raise HTTPException(status_code=404, detail="Document not found in this dossier")
    problem = _check_split_parts(body.parts, int(source.page_count or 0))
    others = [d for d in await svc.list_documents(dossier_id) if d.id != source.id]
    if problem is not None:
        raise HTTPException(status_code=422, detail=problem)
    document_count = len(others) + len(body.parts)
    if document_count > MAX_DOSSIER_DOCUMENTS:
        raise DossierTooManyDocuments(
            limit=MAX_DOSSIER_DOCUMENTS, count=document_count, after_split=True
        )
    contracts = sum(d.role == DocumentRole.CONTRACT for d in others) + sum(
        part.role == "contract" for part in body.parts
    )
    if contracts != 1:
        raise ManifestValidationError(
            DomainErrorCode.CONTRACT_REQUIRED
            if contracts == 0
            else DomainErrorCode.CONTRACT_NOT_UNIQUE,
            f"Hồ sơ cần đúng một hợp đồng, các phần này cho {contracts}",
            count=contracts,
        )

    created: list[SplitDocumentDTO] = []
    if len(body.parts) == 1:
        part = body.parts[0]
        created.append(
            SplitDocumentDTO(
                id=source.id,
                role=source.role.value,
                filename=source.filename,
                page_start=part.page_start,
                page_end=part.page_end,
                page_count=int(source.page_count or 0),
            )
        )
    else:
        data = await storage.download_object(source.blob_uri)
        base = source.filename.removesuffix(".pdf").removesuffix(".PDF")
        next_index = max([source.order_index, *(d.order_index for d in others)]) + 1
        for number, part in enumerate(body.parts, start=1):
            try:
                piece = await asyncio.to_thread(
                    extract_pdf_pages, data, part.page_start, part.page_end
                )
            except InvalidPdfError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            role = DocumentRole.CONTRACT if part.role == "contract" else DocumentRole.ANNEX
            filename = f"{base}-p{part.page_start}-{part.page_end}.pdf"
            order_index = source.order_index if number == 1 else next_index + number - 2
            document, _size, _path = await _ingest_upload_file(
                svc=svc,
                dossier_id=dossier_id,
                upload=_PdfUpload(
                    file=UploadFile(file=BytesIO(piece), filename=filename),
                    data=piece,
                    page_count=part.page_end - part.page_start + 1,
                ),
                role=role,
                order_index=order_index,
            )
            created.append(
                SplitDocumentDTO(
                    id=document.id,
                    role=role.value,
                    filename=document.filename,
                    page_start=part.page_start,
                    page_end=part.page_end,
                    page_count=part.page_end - part.page_start + 1,
                )
            )
        try:
            await svc.remove_split_source(dossier_id, source.id)
        except InvalidStateTransition as exc:
            raise HTTPException(status_code=409, detail="Manifest đã được xác nhận") from exc

    metadata["split_pending"] = False
    metadata["split_from"] = {
        "document_id": source.id,
        "filename": source.filename,
        "parts": [part.model_dump() for part in body.parts],
    }
    await svc.patch_dossier(dossier_id, name=None, metadata=metadata)
    await svc.confirm_uploaded_manifest(dossier_id, user.user_id)
    await svc.commit()

    if len(body.parts) > 1:
        background_tasks.add_task(_delete_blob_quietly, source.blob_uri)
    background_tasks.add_task(
        _publish_dossier_uploaded, dossier_id=dossier_id, file_path=created[0].filename
    )
    await _record(
        tenant_id=user.tenant_id,
        title=f"Tách hồ sơ {dossier.name} thành {len(created)} tài liệu",
        actor_display_name=user.email or user.display_name,
        detail=None,
        kind="dossier.split",
    )
    return ApiResponse(
        data=DossierSplitDTO(dossier_id=dossier_id, status="queued", documents=created)
    )


async def _delete_blob_quietly(uri: str) -> None:
    try:
        await storage.delete_object(uri)
    except Exception:
        logger.warning("dossier.split.source_blob_delete_failed", uri=uri, exc_info=True)


@router.post(
    "/dossiers/{dossier_id}/ai2/retry",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[OcrRestartDTO],
    summary="Chạy lại AI2 (trích xuất/so sánh) mà không OCR lại",
    responses={
        404: {"description": "Dossier not found"},
        409: {"description": "Latest job did not fail at the AI2 step"},
    },
)
async def retry_dossier_ai2(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ContractServiceDep,
    user: Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))],
) -> ApiResponse[OcrRestartDTO]:
    """Gửi lại AI2 cho run hiện tại; kết quả OCR đã có được dùng lại.

    Chỉ nhận khi job mới nhất FAILED ở bước AI2. Worker kiểm tra lại điều kiện
    trước khi chạy (đủ snapshot OCR), rồi gửi AI2 với attempt kế tiếp.
    """
    dossier = await _require_readable(svc, dossier_id, user, action=AclAction.DOSSIER_EDIT)
    job = dossier.latest_job()
    if (
        job is None
        or job.current_run_id is None
        or job.status != JobStatus.FAILED
        or job.error_code not in _AI2_RETRYABLE_ERRORS
    ):
        raise HTTPException(
            status_code=409,
            detail="Chỉ chạy lại AI2 được khi hồ sơ lỗi ở bước AI2; lỗi OCR cần chạy lại OCR.",
        )
    await messaging.publish_event(
        "dossier_events",
        {
            "event": "dossier.ai2.retry",
            "dossier_id": str(dossier_id),
            "run_id": job.current_run_id,
        },
    )
    await _record(
        tenant_id=user.tenant_id,
        title=f"Chạy lại AI2 hồ sơ {dossier.name}",
        actor_display_name=user.email or user.display_name,
        detail=None,
        kind="dossier.ai2_retry",
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
        viewer_email=user.email,
        limit=limit,
        offset=offset,
    )
    summaries: list[DossierSummaryDTO] = []
    for d in items:
        latest = d.latest_job()
        summaries.append(
            _for_viewer(
                DossierSummaryDTO.from_domain(
                    d,
                    latest_job_status=latest.status if latest else None,
                ),
                user,
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
        dossier_name = (
            await _require_readable(svc, dossier_id, user, action=AclAction.DOSSIER_MANAGE)
        ).name
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
    source_file_id: str | None = None
    document_id: str | None = None
    line_id: str | None = None
    bbox: list[float] = Field(default_factory=list)
    # Anchors the UI uses to open the cited clause.
    node_id: str | None = None
    citation_id: str | None = None
    breadcrumb: list[str] = Field(default_factory=list)
    validation_status: str | None = None
    scope: str | None = None


class DossierSearchDTO(BaseModel):
    query: str
    answer: str | None
    connected: bool
    state: str | None = "INSUFFICIENT_EVIDENCE"
    used_llm: bool = False
    notes: list[str] = Field(default_factory=list)
    retrieval_layer: dict[str, Any] = Field(default_factory=dict)
    reasoning_trace: list[Any] = Field(default_factory=list)
    hits: list[DossierSearchHit]
    trace_id: str | None = None
    acl_decision: str | None = None


def _optional_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _hits_from_ai2(payload: dict[str, Any]) -> list[DossierSearchHit]:
    raw = payload.get("hits") or payload.get("citations") or []
    if not isinstance(raw, list):
        return []
    hits: list[DossierSearchHit] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = item.get("text") or item.get("quote") or item.get("snippet") or item.get("text_span")
        if not isinstance(text, str) or not text.strip():
            continue
        page = item.get("page_no") or item.get("page")
        page_range = item.get("page_range")
        if not isinstance(page, int) and isinstance(page_range, list) and page_range:
            page = page_range[0]
        line_ids = item.get("line_ids")
        line_id = item.get("line_id")
        if not isinstance(line_id, str) and isinstance(line_ids, list):
            line_id = next((value for value in line_ids if isinstance(value, str)), None)
        source_file_id = _optional_str(item.get("source_file_id"))
        document_id = _optional_str(item.get("document_id")) or source_file_id
        bbox = item.get("bbox")
        breadcrumb = item.get("breadcrumb")
        hits.append(
            DossierSearchHit(
                text=text.strip(),
                page_no=page if isinstance(page, int) else None,
                source_file_id=source_file_id or document_id,
                document_id=document_id,
                line_id=line_id if isinstance(line_id, str) else None,
                bbox=bbox if isinstance(bbox, list) else [],
                node_id=_optional_str(item.get("node_id")),
                citation_id=_optional_str(item.get("citation_id")),
                breadcrumb=[str(part) for part in breadcrumb]
                if isinstance(breadcrumb, list)
                else [],
                validation_status=_optional_str(item.get("validation_status")),
                scope=_optional_str(item.get("scope") or item.get("document_role")),
            )
        )
    return hits


def _notes_from_trace(trace: list[Any]) -> list[str]:
    notes: list[str] = []
    for step in trace:
        if isinstance(step, dict):
            code = _optional_str(step.get("code"))
            message = _optional_str(step.get("message"))
            if code and message:
                notes.append(f"{code}: {message}")
            elif message or code:
                notes.append(str(message or code))
        elif isinstance(step, str) and step.strip():
            notes.append(step.strip())
    return notes


def _search_dto_from_ai2(payload: dict[str, Any], *, fallback_query: str) -> DossierSearchDTO:
    """Preserve server semantics; transport success never implies ANSWERED."""
    answer = payload.get("answer") or payload.get("text")
    state = str(payload.get("state") or payload.get("review_state") or "INSUFFICIENT_EVIDENCE")
    if state not in {
        "PASS",
        "ANSWERED",
        "NEEDS_REVIEW",
        "INSUFFICIENT_EVIDENCE",
        "BLOCKED",
        "NOT_COMPARABLE",
    }:
        state = "INSUFFICIENT_EVIDENCE"
    raw_trace = payload.get("reasoning_trace")
    reasoning_trace: list[Any] = raw_trace if isinstance(raw_trace, list) else []
    raw_layer = payload.get("retrieval_layer")
    retrieval_layer: dict[str, Any] = raw_layer if isinstance(raw_layer, dict) else {}
    return DossierSearchDTO(
        query=str(payload.get("query") or fallback_query),
        answer=answer.strip() if isinstance(answer, str) and answer.strip() else None,
        connected=payload.get("connected") is not False,
        state=state,
        used_llm=bool(payload.get("used_llm", retrieval_layer.get("used_llm", False))),
        notes=_notes_from_trace(reasoning_trace),
        retrieval_layer=retrieval_layer,
        reasoning_trace=reasoning_trace,
        hits=_hits_from_ai2(payload),
    )


def _ai2_snapshot_digest(dossier: Any) -> str:
    metadata = dossier.metadata if isinstance(getattr(dossier, "metadata", None), dict) else {}
    return str(metadata.get("ai2_snapshot_digest") or dossier.checksum or "").strip()


def _optional_session_factory() -> Any:
    """Session factory when a DB is bound; None in offline router unit tests."""
    try:
        return get_session_factory()
    except RuntimeError:
        return None


async def _enforce_search_limits(factory: Any, user: AuthenticatedUser) -> None:
    try:
        if factory is None:
            await enforce_query_limits(None, tenant_id=user.tenant_id, actor_id=user.user_id)
            return
        async with factory() as session:
            await enforce_query_limits(session, tenant_id=user.tenant_id, actor_id=user.user_id)
    except QueryLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": exc.code, "message": exc.message},
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc


async def _save_search_trace(factory: Any, **fields: Any) -> str | None:
    if factory is None:
        logger.warning("dossier.search.trace_skipped_no_db", dossier_id=fields.get("dossier_id"))
        return None
    async with factory() as session:
        trace = await save_query_trace(session, **fields)
        await session.commit()
        return trace.id


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
    _tenant_id: Annotated[str, Depends(get_tenant_id)],
) -> ApiResponse[DossierSearchDTO]:
    """Nhận câu hỏi từ thanh search. AI2 trả câu trả lời khi đã nối.

    ACL (search) → rate limit + quota → AI2 → ACL lần 2 (citation_read + phạm vi
    tài liệu) → QueryTrace → FE.
    """
    question = body.query.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Thiếu câu hỏi.")
    dossier = await _require_readable(svc, dossier_id, user, action=AclAction.SEARCH)
    factory = _optional_session_factory()
    await _enforce_search_limits(factory, user)

    from contract_intelligence.infrastructure.ai_adapters import (
        AiAdapterError,
        query_ai2,
    )

    settings = get_settings()
    snapshot_digest = _ai2_snapshot_digest(dossier)
    trace_fields: dict[str, Any] = {
        "tenant_id": user.tenant_id,
        "dossier_id": dossier_id,
        "actor_id": user.user_id,
        "endpoint": "search",
        "query": question,
        "snapshot_version": "latest",
        "snapshot_digest": snapshot_digest,
        "query_contract_version": "ai2.query.v1",
    }
    started = time.monotonic()
    try:
        payload = await asyncio.wait_for(
            query_ai2(
                {
                    "query": question,
                    "dossier_id": dossier_id,
                    "snapshot_version": "latest",
                    "snapshot_digest": snapshot_digest,
                    "query_contract_version": "ai2.query.v1",
                    "acl_context": user.user_id,
                    "policy_flags": server_query_policy_flags(),
                    "tenant_id": user.tenant_id,
                    "actor_id": user.user_id,
                }
            ),
            timeout=settings.ai2_query_timeout_seconds,
        )
    except (AiAdapterError, TimeoutError, OSError) as exc:
        logger.info("dossier.search.ai2_unavailable", dossier_id=dossier_id, error=str(exc))
        trace_id = await _save_search_trace(
            factory,
            **trace_fields,
            state=None,
            citations=[],
            acl=None,
            error_code="AI2_UNAVAILABLE",
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        return ApiResponse(
            data=DossierSearchDTO(
                query=question,
                answer=None,
                connected=False,
                hits=[],
                trace_id=trace_id,
            )
        )
    latency_ms = int((time.monotonic() - started) * 1000)
    if not isinstance(payload, dict):
        payload = {}

    # ACL lần 2: quyền có thể bị thu hồi trong lúc AI2 trả lời.
    try:
        fresh = await svc.get_dossier(dossier_id)
        can_read = dossier_access_decision(
            action=AclAction.CITATION_READ,
            principal=user,
            dossier_id=dossier_id,
            dossier_tenant_id=getattr(fresh, "tenant_id", user.tenant_id),
            metadata=fresh.metadata,
        )
        allowed = {str(doc.id) for doc in await svc.list_documents(dossier_id)}
    except NotFoundError:
        can_read, allowed = False, set()
    filtered, acl = enforce_result_acl(
        payload, can_read_citations=can_read, allowed_document_ids=allowed
    )
    dto = _search_dto_from_ai2(filtered, fallback_query=question)
    if acl.decision != "passed":
        logger.warning(
            "dossier.search.acl_second_pass",
            dossier_id=dossier_id,
            actor_id=user.user_id,
            decision=acl.decision,
            dropped=acl.dropped,
        )
    dto.acl_decision = acl.decision
    dto.trace_id = await _save_search_trace(
        factory,
        **trace_fields,
        state=dto.state,
        citations=list(filtered.get("citations") or filtered.get("hits") or []),
        acl=acl,
        latency_ms=latency_ms,
    )
    return ApiResponse(data=dto)


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
    dossier = await _require_readable(svc, dossier_id, _user, action=AclAction.QUERY)
    documents = await svc.list_documents(dossier_id)
    latest = dossier.latest_job()
    return ApiResponse(
        data=_for_viewer(
            DossierDetailDTO.from_domain(
                dossier,
                documents=documents,
                latest_job_id=latest.id if latest else None,
                latest_job_status=latest.status if latest else None,
            ),
            _user,
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
    await _require_readable(svc, dossier_id, user, action=AclAction.DOSSIER_EDIT)
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
        data=_for_viewer(
            DossierDetailDTO.from_domain(
                dossier,
                documents=documents,
                latest_job_id=latest.id if latest else None,
                latest_job_status=latest.status if latest else None,
            ),
            user,
        ),
    )


@router.get(
    "/dossiers/{dossier_id}/access",
    response_model=ApiResponse[DossierAccessDTO],
    responses={404: {"description": "Dossier not found"}},
)
async def get_dossier_access(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ContractServiceDep,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[DossierAccessDTO]:
    """Đọc quyền hồ sơ. Ai xem được hồ sơ đều gọi được.

    Chủ hồ sơ và ADMINISTRATOR thấy mọi người được chia sẻ; người được chia sẻ
    chỉ thấy grant của chính mình. Grant hết hạn vẫn trả về (kèm ``expires_at``).
    """
    dossier = await _require_readable(svc, dossier_id, user, action=AclAction.QUERY)
    metadata = visible_dossier_metadata(dict(dossier.metadata or {}), user) or {}
    grants = [g for g in (metadata.get("shared_with") or []) if isinstance(g, dict)]
    scope = metadata.get("access_scope")
    if scope not in ("mine", "shared_out", "shared_in"):
        scope = "shared_out" if grants else "mine"
    return ApiResponse(
        data=DossierAccessDTO(
            dossier_id=dossier_id,
            scope=scope,
            shared_with=[AccessGrantBody.model_validate(item) for item in grants],
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
    """Đặt quyền hồ sơ. Gộp vào metadata, giữ created_by.

    Chỉ chủ hồ sơ hoặc ADMINISTRATOR. Mỗi người được chia sẻ có ``permission``
    (``read``/``edit``) và ``expires_at`` tuỳ chọn. ``expires_at`` mới đặt hoặc vừa
    đổi phải ở tương lai; grant đã hết hạn mà gửi lại nguyên ``expires_at`` cũ thì
    được giữ (vẫn không có tác dụng) để chủ hồ sơ sửa người khác không bị chặn.
    """
    dossier = await _require_readable(svc, dossier_id, user, action=AclAction.DOSSIER_MANAGE)
    now = utcnow()
    current = dict(dossier.metadata or {})
    previous_expiry = {
        str(item.get("id")): _parse_expiry(item.get("expires_at"))
        for item in (current.get("shared_with") or [])
        if isinstance(item, dict) and item.get("id")
    }
    for item in body.shared_with:
        if item.expires_at is None:
            continue
        expires_at = _as_utc(item.expires_at)
        if expires_at <= now and previous_expiry.get(item.id) != expires_at.replace(microsecond=0):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"expires_at của {item.email or item.id} đã ở quá khứ.",
            )
    previous_ids = {
        str(item.get("id"))
        for item in (current.get("shared_with") or [])
        if isinstance(item, dict) and item.get("id")
    }
    current.setdefault("created_by", user.user_id)
    current.setdefault("created_by_name", user.display_name)
    grants = [] if body.scope == "mine" else [_stored_grant(item) for item in body.shared_with]
    if body.scope == "shared_in" and user.user_id not in {item["id"] for item in grants}:
        grants.append(
            {
                "id": user.user_id,
                "email": user.email or "",
                "display_name": user.display_name or "",
                "permission": "edit",
                "expires_at": None,
            }
        )
    current["access_scope"] = body.scope
    current["shared_with"] = grants
    await svc.patch_dossier(dossier_id, name=None, metadata=current, acl_update=True)
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
    await _require_readable(svc, dossier_id, _user, action=AclAction.CITATION_READ)
    documents = await svc.list_documents(dossier_id)
    return ApiResponse(data=[DocumentListItemDTO.from_domain(d) for d in documents])


# -----------------------------------------------------------------------------
# GET /dossiers/{id}/manifest — current ManifestDTO
# -----------------------------------------------------------------------------


@router.get(
    "/dossiers/{dossier_id}/manifest",
    dependencies=[Depends(acl_dossier)],
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
    await _require_readable(svc, dossier_id, user, action=AclAction.DOSSIER_EDIT)
    data = await svc.confirm_manifest(dossier_id, user.user_id, body)
    await messaging.publish_event(
        "dossier_events",
        {
            "event": "dossier.manifest.confirmed",
            "dossier_id": dossier_id,
            "tenant_id": user.tenant_id,
            "manifest_version": data.version,
        },
        key=dossier_id,
    )
    return ApiResponse(data=data)


# -----------------------------------------------------------------------------
# Document endpoints
# -----------------------------------------------------------------------------


@router.get(
    "/documents/{document_id}",
    dependencies=[Depends(acl_document)],
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
    dependencies=[Depends(acl_document)],
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
    """Tải PDF gốc — trả về binary stream từ storage.

    Có ngay sau khi tải lên, trước OCR (kể cả hồ sơ ``split_pending``), nên màn
    tách file dựng ảnh trang bằng pdf.js từ đây. Cần quyền xem hồ sơ.
    """
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
