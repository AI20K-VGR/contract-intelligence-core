"""Chunked dossier upload: /uploads (issue #145).

Layer: interfaces/api (FastAPI router).

Why: Cloudflare Free ends a request that is still sending its body after about
125 s. On the 35–87 KB/s lines measured in production that is 4–10 MB, below
many real dossiers, so ``POST /dossiers`` (one multipart request) fails for
them with a 502. Here the browser sends each file as numbered chunks of
``upload_chunk_bytes`` (1 MiB: ~30 s at 35 KB/s), each its own short request,
and can resend a chunk or resume after a dropped connection.

    POST   /uploads                                   open: declare files + metadata (201)
    PUT    /uploads/{id}/files/{index}/chunks/{n}     one chunk, raw bytes (204)
    GET    /uploads/{id}                              chunks received so far (200)
    POST   /uploads/{id}/complete                     build the dossier (202, as POST /dossiers)
    DELETE /uploads/{id}                              cancel, drop the chunks (204)

Completing joins the chunks and goes through ``dossier_intake`` like
``POST /dossiers``, so the same checks apply (6 files, 50 MiB, readable PDF,
``split_pending``) and the response is the same ``DossierCreatedDTO``.

RBAC: OPERATOR, ADMINISTRATOR (as POST /dossiers). A session belongs to the
user who opened it; anyone else gets 404.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime
from typing import Annotated, Any, Literal

import structlog
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Path,
    Request,
    Response,
    status,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.config.settings import get_settings
from contract_intelligence.contract.application.dtos.dossier_dtos import DossierCreatedDTO
from contract_intelligence.contract.infrastructure.persistence.upload_session_store import (
    CANCELLED,
    COMPLETED,
    COMPLETING,
    EVICT_IDLE_AFTER,
    OPEN,
    DeclaredFile,
    UploadSessionORM,
    UploadSessionStore,
    aware,
    chunk_count,
    chunk_key,
    declared_files,
    delete_objects_quietly,
    expected_chunk_size,
    owner_lock,
    stale_completing,
)
from contract_intelligence.contract.interfaces.api.dependencies import ContractServiceDep
from contract_intelligence.contract.interfaces.api.dossier_intake import (
    PdfUpload,
    check_document_count,
    check_pdf,
    discard_uploaded,
    file_too_large,
    parse_upload_metadata,
    publish_dossier_uploaded,
    stage_new_dossier,
)
from contract_intelligence.infrastructure import storage
from contract_intelligence.shared.auth import AuthenticatedUser, require_role
from contract_intelligence.shared.auth.tenant import get_tenant_id
from contract_intelligence.shared.base import utcnow
from contract_intelligence.shared.exceptions import (
    DomainErrorCode,
    UploadSessionConflict,
    UploadSessionExpired,
)
from contract_intelligence.shared.persistence import get_async_session
from contract_intelligence.shared.responses import ApiResponse

router = APIRouter(prefix="/uploads", tags=["Contract"])
logger = structlog.get_logger(__name__)

Uploader = Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))]
Session = Annotated[AsyncSession, Depends(get_async_session)]
TenantId = Annotated[str, Depends(get_tenant_id)]
UploadId = Annotated[str, Path(min_length=1, max_length=64)]


# -----------------------------------------------------------------------------
# DTOs
# -----------------------------------------------------------------------------


class UploadFileBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["contract", "annex"]
    filename: str = Field(min_length=1, max_length=255)
    size: int = Field(ge=1, description="Bytes of the PDF as it will be sent.")


class UploadSessionCreateBody(BaseModel):
    """Same ``metadata`` as POST /dossiers, plus the files to come."""

    model_config = ConfigDict(extra="forbid")

    metadata: dict[str, Any] = Field(default_factory=dict)
    files: list[UploadFileBody] = Field(min_length=1, max_length=50)


class UploadFileStateDTO(BaseModel):
    index: int
    role: str
    filename: str
    size: int
    chunks: int
    received: list[int] = Field(description="Chunk numbers already stored, ascending.")


class UploadSessionDTO(BaseModel):
    upload_id: str
    status: Literal["open", "completing", "completed", "cancelled"]
    chunk_size: int = Field(description="Bytes of every chunk but the last of each file.")
    expires_at: datetime
    files: list[UploadFileStateDTO] = Field(description="Contract first (index 0).")
    dossier_id: str | None = None
    job_id: str | None = None


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Upload session not found")


def _expired(row: UploadSessionORM) -> bool:
    return row.status != COMPLETED and aware(row.expires_at) <= utcnow()


def _not_open(row: UploadSessionORM) -> UploadSessionConflict:
    """409 for a session that no longer takes chunks, with a code per state."""
    codes = {
        COMPLETING: DomainErrorCode.UPLOAD_COMPLETING,
        COMPLETED: DomainErrorCode.UPLOAD_COMPLETED,
        CANCELLED: DomainErrorCode.UPLOAD_CANCELLED,
    }
    return UploadSessionConflict(
        codes.get(row.status, DomainErrorCode.UPLOAD_NOT_OPEN),
        f"Upload session is {row.status}",
        details={"upload_id": row.id, "status": row.status, "dossier_id": row.dossier_id},
    )


async def _session_dto(store: UploadSessionStore, row: UploadSessionORM) -> UploadSessionDTO:
    received: dict[int, list[int]] = {}
    for chunk in await store.chunks(row.id):
        received.setdefault(chunk.file_index, []).append(chunk.chunk_no)
    return UploadSessionDTO(
        upload_id=row.id,
        status=row.status,
        chunk_size=row.chunk_bytes,
        expires_at=aware(row.expires_at),
        files=[
            UploadFileStateDTO(
                index=f.index,
                role=f.role,
                filename=f.filename,
                size=f.size,
                chunks=f.chunks,
                received=received.get(f.index, []),
            )
            for f in declared_files(row)
        ],
        dossier_id=row.dossier_id,
        job_id=row.job_id,
    )


async def _read_body(request: Request, limit: int) -> bytes:
    """Read the raw body, stopping at ``limit + 1`` bytes (the caller refuses that)."""
    data = bytearray()
    async for part in request.stream():
        data.extend(part)
        if len(data) > limit:
            break
    return bytes(data)


# Chunks read from MinIO at once while joining. /complete must answer within
# Cloudflare's 100 s, and a full dossier is up to 300 chunks of 1 MiB.
_JOIN_CONCURRENCY = 8


async def _join_chunks(paths: list[str]) -> bytes:
    """Download the chunk objects and join them **in the order of** ``paths``.

    This is the only place the PDF given to OCR is put back together, so order
    is by construction: chunk ``i`` is awaited before chunk ``i + 1`` is
    appended. Up to ``_JOIN_CONCURRENCY`` downloads run ahead of the one being
    appended (a sliding window), so at most that many chunks wait in memory
    besides the file being built.
    """
    result = bytearray()
    window: dict[int, asyncio.Task[bytes]] = {}
    try:
        for index in range(min(_JOIN_CONCURRENCY, len(paths))):
            window[index] = asyncio.create_task(storage.download_object(paths[index]))
        for index in range(len(paths)):
            result.extend(await window.pop(index))
            ahead = index + _JOIN_CONCURRENCY
            if ahead < len(paths):
                window[ahead] = asyncio.create_task(storage.download_object(paths[ahead]))
    finally:
        for task in window.values():
            task.cancel()
    return bytes(result)


def _missing_chunks(
    files: list[DeclaredFile], received: set[tuple[int, int]]
) -> dict[str, list[int]]:
    missing: dict[str, list[int]] = {}
    for f in files:
        gaps = [n for n in range(f.chunks) if (f.index, n) not in received]
        if gaps:
            missing[str(f.index)] = gaps
    return missing


def _created(row: UploadSessionORM) -> ApiResponse[DossierCreatedDTO]:
    return ApiResponse(data=DossierCreatedDTO(dossier_id=row.dossier_id or "", job_id=row.job_id))


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[UploadSessionDTO],
    summary="Mở phiên tải hồ sơ theo khúc",
    responses={
        413: {"description": "A file is larger than upload_max_file_bytes"},
        422: {
            "description": (
                "Not exactly one contract, invalid metadata, or more than 6 files "
                "(`DOSSIER_TOO_MANY_DOCUMENTS`)"
            )
        },
        429: {
            "description": (
                "3 unfinished sessions and none idle for 5 minutes: uploads still "
                "sending or completing are never cancelled (idle ones make room instead)"
            )
        },
    },
)
async def open_upload_session(
    body: UploadSessionCreateBody,
    user: Uploader,
    tenant_id: TenantId,
    session: Session,
    background_tasks: BackgroundTasks,
) -> ApiResponse[UploadSessionDTO]:
    """Declare the files and metadata; nothing is stored until the chunks come.

    Everything ``POST /dossiers`` checks before reading a file is checked here,
    before any byte is sent: file count, one contract, sizes, metadata.
    """
    settings = get_settings()
    check_document_count(len(body.files))
    contracts = [f for f in body.files if f.role == "contract"]
    if len(contracts) != 1:
        raise HTTPException(status_code=422, detail="Cần đúng một tệp hợp đồng (role=contract).")
    for f in body.files:
        if f.size > settings.upload_max_file_bytes:
            raise file_too_large(f.filename)
    parse_upload_metadata(body.metadata)  # 422 now rather than at /complete

    store = UploadSessionStore(session, tenant_id)
    chunk_bytes = settings.upload_chunk_bytes
    ordered = contracts + [f for f in body.files if f.role == "annex"]
    files = [
        DeclaredFile(
            index=index,
            role=f.role,
            filename=f.filename,
            size=f.size,
            chunks=chunk_count(f.size, chunk_bytes),
        )
        for index, f in enumerate(ordered)
    ]
    # A session left behind (tab closed, reload: the frontend keeps upload_id in
    # memory only) must not lock the user out until it expires. At the cap, open
    # sessions idle for EVICT_IDLE_AFTER are cancelled to make room, least
    # recently active first. A session still receiving chunks (another upload
    # running in parallel) or in the middle of /complete is never taken: 429.
    # Count, evict and create run under one lock per user and end in one commit,
    # so concurrent requests (several tabs) cannot all pass the same count.
    cap = settings.upload_sessions_per_user
    evicted: list[str] = []
    evicted_paths: list[str] = []
    async with owner_lock(session, tenant_id, user.user_id):
        open_count = await store.count_open(user.user_id)
        if open_count >= cap:
            idle_since = utcnow() - EVICT_IDLE_AFTER
            for old in await store.oldest_open(user.user_id, limit=open_count):
                if open_count - len(evicted) < cap:
                    break
                # Conditional: skipped if a chunk or /complete reached it meanwhile.
                paths = await store.cancel_if_open(old.id, idle_since=idle_since)
                if paths is not None:
                    evicted_paths += paths
                    evicted.append(old.id)
        if open_count - len(evicted) >= cap:
            await session.commit()  # keeps the evictions and releases the lock
            if evicted:
                logger.info("upload.session.evicted", upload_ids=evicted, user_cap=cap)
            # Background tasks do not run on an error response: delete now.
            await delete_objects_quietly(evicted_paths)
            raise HTTPException(
                status_code=429,
                detail=(
                    "Too many uploads in progress; finish or cancel one, "
                    "or try again in a few minutes."
                ),
            )
        row = await store.create(
            user_id=user.user_id,
            metadata=body.metadata,
            files=files,
            chunk_bytes=chunk_bytes,
            ttl_seconds=settings.upload_session_ttl_seconds,
        )
        await session.commit()
    if evicted:
        logger.info("upload.session.evicted", upload_ids=evicted, user_cap=cap)
        background_tasks.add_task(delete_objects_quietly, evicted_paths)
    logger.info(
        "upload.session.opened",
        upload_id=row.id,
        files=len(files),
        total_bytes=sum(f.size for f in files),
        chunks=sum(f.chunks for f in files),
    )
    return ApiResponse(data=await _session_dto(store, row))


@router.put(
    "/{upload_id}/files/{file_index}/chunks/{chunk_no}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Gửi một khúc của một tệp (byte thô)",
    responses={
        404: {"description": "No such session for this user, or no such file/chunk"},
        409: {"description": "`UPLOAD_COMPLETING`, `UPLOAD_COMPLETED` or `UPLOAD_CANCELLED`"},
        410: {"description": "`UPLOAD_EXPIRED`"},
        422: {"description": "Chunk size differs from the expected size"},
    },
)
async def put_chunk(
    upload_id: UploadId,
    file_index: Annotated[int, Path(ge=0, le=49)],
    chunk_no: Annotated[int, Path(ge=0, le=100_000)],
    request: Request,
    user: Uploader,
    tenant_id: TenantId,
    session: Session,
) -> Response:
    """Store one chunk. Sending the same chunk again replaces it (safe to retry)."""
    store = UploadSessionStore(session, tenant_id)
    row = await store.get(upload_id, user.user_id)
    if row is None:
        raise _not_found()
    if _expired(row):
        raise UploadSessionExpired(row.id)
    if row.status != OPEN:
        raise _not_open(row)
    file = next((f for f in declared_files(row) if f.index == file_index), None)
    if file is None or chunk_no >= file.chunks:
        raise HTTPException(status_code=404, detail="No such file or chunk in this upload")

    expected = expected_chunk_size(file, chunk_no, row.chunk_bytes)
    data = await _read_body(request, expected)
    if len(data) != expected:
        raise HTTPException(
            status_code=422,
            detail=f"Chunk {chunk_no} of file {file_index} must be {expected} bytes",
        )

    object_path = await storage.upload_file(
        chunk_key(tenant_id, row.id, file_index, chunk_no), data
    )
    # The object has a key of its own (chunk_key), so writing it changed
    # nothing anyone reads. It counts only once its row is saved below.
    if not await store.touch_open(row.id):
        # Cancelled, claimed or completed after the check above: refused, and
        # the object is not referenced by any chunk row.
        await session.rollback()
        await delete_objects_quietly([object_path])
        current = await store.get_refreshed(upload_id, user.user_id)
        if current is None:
            raise _not_found()
        raise _not_open(current)
    try:
        replaced = await store.save_chunk(
            row,
            file_index=file_index,
            chunk_no=chunk_no,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            object_path=object_path,
        )
        await session.commit()
    except IntegrityError as exc:
        # The same chunk sent twice at the same moment: the other send was
        # recorded first and is the one kept; this object is not referenced.
        await session.rollback()
        await delete_objects_quietly([object_path])
        logger.info("upload.chunk.concurrent_duplicate", upload_id=row.id, error=str(exc))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    if replaced is not None:
        # The previous send of this chunk, no longer referenced since the commit.
        await delete_objects_quietly([replaced])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{upload_id}",
    response_model=ApiResponse[UploadSessionDTO],
    summary="Trạng thái phiên tải lên: các khúc đã nhận",
    responses={
        404: {"description": "No such session for this user"},
        410: {"description": "`UPLOAD_EXPIRED`"},
    },
)
async def get_upload_session(
    upload_id: UploadId,
    user: Uploader,
    tenant_id: TenantId,
    session: Session,
) -> ApiResponse[UploadSessionDTO]:
    """What was received, so a client resumes after a dropped connection or a reload."""
    store = UploadSessionStore(session, tenant_id)
    row = await store.get(upload_id, user.user_id)
    if row is None:
        raise _not_found()
    if _expired(row):
        raise UploadSessionExpired(row.id)
    return ApiResponse(data=await _session_dto(store, row))


@router.post(
    "/{upload_id}/complete",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[DossierCreatedDTO],
    summary="Ghép các khúc và tạo hồ sơ (như POST /dossiers)",
    responses={
        404: {"description": "No such session for this user"},
        409: {
            "description": (
                "`UPLOAD_MISSING_CHUNKS` (details.missing_chunks), `UPLOAD_SIZE_MISMATCH`, "
                "`UPLOAD_COMPLETING` (call again later) or `UPLOAD_CANCELLED`"
            )
        },
        410: {"description": "`UPLOAD_EXPIRED`"},
        413: {"description": "A file is larger than upload_max_file_bytes"},
        422: {"description": "A file is not a readable PDF, or invalid metadata"},
    },
)
async def complete_upload_session(
    upload_id: UploadId,
    user: Uploader,
    tenant_id: TenantId,
    session: Session,
    svc: ContractServiceDep,
    background_tasks: BackgroundTasks,
) -> ApiResponse[DossierCreatedDTO]:
    """Join the chunks, then create the dossier exactly as POST /dossiers does.

    Calling it again after success returns the same dossier, so a client that
    lost the first response can safely retry.
    """
    store = UploadSessionStore(session, tenant_id)
    row = await store.get(upload_id, user.user_id)
    if row is None:
        raise _not_found()
    if row.status == COMPLETED:
        return _created(row)
    if _expired(row):
        raise UploadSessionExpired(row.id)
    if row.status == CANCELLED or (row.status == COMPLETING and not stale_completing(row)):
        raise _not_open(row)

    files = declared_files(row)
    chunks = await store.chunks(row.id)
    missing = _missing_chunks(files, {(c.file_index, c.chunk_no) for c in chunks})
    if missing:
        raise UploadSessionConflict(
            DomainErrorCode.UPLOAD_MISSING_CHUNKS,
            "Some chunks have not been received",
            details={"upload_id": row.id, "missing_chunks": missing},
        )

    # Hold the session so a concurrent /complete cannot build a second dossier.
    claimed = await store.claim_for_completion(row.id)
    await session.commit()
    if not claimed:
        # Re-fetch with populate_existing so the identity-map copy is refreshed
        # from the DB (claim ran with synchronize_session=False).
        row = await store.get_refreshed(upload_id, user.user_id)
        if row is not None and row.status == COMPLETED:
            return _created(row)
        raise UploadSessionConflict(
            DomainErrorCode.UPLOAD_COMPLETING,
            "Upload session is completing",
            details={"upload_id": upload_id, "status": COMPLETING, "dossier_id": None},
        )
    # Read again now that no chunk can be added: a resend may have landed
    # between the check above and the claim.
    chunks = await store.chunks(row.id)

    uploaded: list[str] = []
    try:
        uploads: list[PdfUpload] = []
        for f in files:
            parts = [c.object_path for c in chunks if c.file_index == f.index]
            data = await _join_chunks(parts)
            if len(data) != f.size:
                raise UploadSessionConflict(
                    DomainErrorCode.UPLOAD_SIZE_MISMATCH,
                    f"File {f.index} has {len(data)} bytes, {f.size} were declared",
                    details={
                        "upload_id": upload_id,
                        "file_index": f.index,
                        "received_bytes": len(data),
                        "declared_bytes": f.size,
                    },
                )
            uploads.append(await check_pdf(f.filename, data))

        staged = await stage_new_dossier(
            svc=svc,
            user=user,
            meta=parse_upload_metadata(row.dossier_metadata),
            contract=uploads[0],
            annexes=uploads[1:],
            uploaded=uploaded,
        )
        paths = await store.finish(
            row, status=COMPLETED, dossier_id=staged.dossier_id, job_id=staged.job_id
        )
        # Dossier, documents and the completed session in one commit.
        await svc.commit()
    except BaseException:
        # Nothing of the dossier was committed: give the session back so the
        # client can fix the file (or retry) and complete again.
        await session.rollback()
        try:
            await store.reopen(upload_id)
            await session.commit()
        except Exception:
            logger.warning("upload.session.reopen_failed", upload_id=upload_id, exc_info=True)
        # Objects already stored for the dossier that was not committed
        # (contract, first annexes...). Awaited: background tasks run only
        # after a response, never on this error path.
        await discard_uploaded(uploaded)
        raise

    if not staged.split_pending:
        background_tasks.add_task(
            publish_dossier_uploaded,
            dossier_id=staged.dossier_id,
            file_path=staged.contract_path,
        )
    background_tasks.add_task(delete_objects_quietly, paths)
    logger.info(
        "upload.session.completed",
        upload_id=upload_id,
        dossier_id=staged.dossier_id,
        files=len(files),
        total_bytes=sum(f.size for f in files),
    )
    return ApiResponse(data=DossierCreatedDTO(dossier_id=staged.dossier_id, job_id=staged.job_id))


@router.delete(
    "/{upload_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Huỷ phiên tải lên và xoá các khúc đã gửi",
    responses={
        404: {"description": "No such session for this user"},
        409: {
            "description": "`UPLOAD_COMPLETED` (delete the dossier instead) or `UPLOAD_COMPLETING`"
        },
    },
)
async def cancel_upload_session(
    upload_id: UploadId,
    user: Uploader,
    tenant_id: TenantId,
    session: Session,
    background_tasks: BackgroundTasks,
) -> Response:
    """Cancel an unfinished upload. Cancelling twice is not an error."""
    store = UploadSessionStore(session, tenant_id)
    row = await store.get(upload_id, user.user_id)
    if row is None:
        raise _not_found()
    if row.status in (COMPLETED, COMPLETING):
        raise _not_open(row)
    if row.status == OPEN:
        paths = await store.cancel_if_open(row.id)
        await session.commit()
        if paths is None:
            # /complete (or another cancel) got there between the read and the
            # update: report what happened instead of overwriting it.
            current = await store.get_refreshed(upload_id, user.user_id)
            if current is not None and current.status in (COMPLETED, COMPLETING):
                raise _not_open(current)
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        background_tasks.add_task(delete_objects_quietly, paths)
        logger.info("upload.session.cancelled", upload_id=upload_id, chunks=len(paths))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
