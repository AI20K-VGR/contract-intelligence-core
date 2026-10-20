"""Turn validated PDF bytes into a new dossier: the one path every upload takes.

Layer: interfaces/api (shared by routers, no route of its own).

``POST /dossiers`` (one multipart request) and ``POST /uploads/{id}/complete``
(a file sent in chunks, issue #145) both end here, so a dossier is checked and
created the same way whichever route the bytes came through:

1. :func:`check_pdf` — size cap (413) and a readable PDF with its page count (422)
2. :func:`stage_new_dossier` — dossier + job, each file to MinIO and the
   ``document`` table, manifest confirmed unless ``split_pending``. No commit:
   the caller commits, so it can add its own rows to the same transaction.
3. :func:`publish_dossier_uploaded` — after the commit, starts OCR.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import structlog
from fastapi import HTTPException, UploadFile
from pydantic import BaseModel

from contract_intelligence.config.settings import get_settings
from contract_intelligence.contract.domain.entities.document import (
    MAX_DOSSIER_DOCUMENTS,
    Document,
    DocumentRole,
)
from contract_intelligence.infrastructure import messaging, storage
from contract_intelligence.shared.auth import AuthenticatedUser
from contract_intelligence.shared.exceptions import DossierTooManyDocuments
from contract_intelligence.shared.pdf import InvalidPdfError, count_pdf_pages
from contract_intelligence.shared.utils import safe_filename

logger = structlog.get_logger(__name__)

# Metadata keys the server sets itself; a client value is ignored.
_RESERVED_METADATA_KEYS = ("name", "tags", "notes", "created_by", "created_by_name")


class DossierUploadMetadata(BaseModel):
    """``metadata`` of a dossier upload (openapi.yaml DossierUploadRequest)."""

    model_config = {"extra": "allow"}  # tags, notes and UI fields (code, split_pending…)

    name: str | None = None
    tags: list[str] | None = None
    notes: str | None = None


def parse_upload_metadata(raw: str | dict[str, Any] | None) -> DossierUploadMetadata:
    """Validate the metadata JSON (multipart string or JSON object); 422 when invalid."""
    if not raw:
        return DossierUploadMetadata()
    try:
        if isinstance(raw, dict):
            return DossierUploadMetadata.model_validate(raw)
        return DossierUploadMetadata.model_validate_json(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid metadata JSON: {exc}") from exc


def check_document_count(count: int) -> None:
    """AI2 takes at most 6 documents per dossier (DEC-BE-AI2-01 D5): 422 above."""
    if count > MAX_DOSSIER_DOCUMENTS:
        raise DossierTooManyDocuments(limit=MAX_DOSSIER_DOCUMENTS, count=count)


def file_too_large(filename: str | None) -> HTTPException:
    limit = get_settings().upload_max_file_bytes
    return HTTPException(
        status_code=413,
        detail=f"{filename}: file exceeds {limit // (1024 * 1024)} MB",
    )


@dataclass(frozen=True, slots=True)
class PdfUpload:
    """One uploaded PDF, already size-checked and parsed."""

    filename: str | None
    data: bytes
    page_count: int


async def check_pdf(filename: str | None, data: bytes) -> PdfUpload:
    """Size cap (413) and a readable PDF (422), so AI1 gets the real page range."""
    if len(data) > get_settings().upload_max_file_bytes:
        raise file_too_large(filename)
    try:
        page_count = await asyncio.to_thread(count_pdf_pages, data)
    except InvalidPdfError as exc:
        raise HTTPException(status_code=422, detail=f"{filename}: {exc}") from exc
    return PdfUpload(filename=filename, data=data, page_count=page_count)


async def read_pdf_upload(file: UploadFile) -> PdfUpload:
    """Read one multipart PDF part, refusing an oversized one before reading it."""
    limit = get_settings().upload_max_file_bytes
    # The multipart parser has already spooled the part to disk and knows its
    # size: refuse before reading, then read once. Collecting 1 MiB chunks and
    # joining them held every file twice at the peak of an upload.
    if file.size is not None and file.size > limit:
        raise file_too_large(file.filename)
    data = await file.read(limit + 1)
    return await check_pdf(file.filename, data)


async def ingest_upload_file(
    *,
    svc: Any,
    dossier_id: str,
    upload: PdfUpload,
    role: DocumentRole,
    order_index: int,
) -> tuple[Document, int, str]:
    """Validated upload → MinIO → ``document`` row (MinIO object removed if the row fails).

    Returns ``(document, size_bytes, s3_path)``; ``s3_path`` goes in the Kafka event.
    """
    raw_bytes = upload.data
    total_size = len(raw_bytes)
    filename = safe_filename(upload.filename, fallback=f"{role.value.lower()}.pdf")
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


@dataclass(frozen=True, slots=True)
class StagedDossier:
    """A dossier written in the open transaction, not committed yet."""

    dossier_id: str
    job_id: str | None
    contract_path: str
    annex_paths: list[str]
    split_pending: bool


async def stage_new_dossier(
    *,
    svc: Any,
    user: AuthenticatedUser,
    meta: DossierUploadMetadata,
    contract: PdfUpload,
    annexes: list[PdfUpload],
    uploaded: list[str] | None = None,
) -> StagedDossier:
    """Create the dossier, its job and every document; the caller commits.

    The files are already checked (:func:`check_pdf`), so a bad annex never
    leaves a half-made dossier behind. Each MinIO object is appended to
    ``uploaded`` the moment it is stored, so a caller whose staging or commit
    fails can delete exactly what was written (:func:`discard_uploaded`).
    """
    uploaded = [] if uploaded is None else uploaded
    name = meta.name or contract.filename or "Untitled dossier"
    payload: dict[str, Any] = {}
    if meta.tags is not None:
        payload["tags"] = meta.tags
    if meta.notes is not None:
        payload["notes"] = meta.notes
    for key, value in (getattr(meta, "model_extra", None) or {}).items():
        if key not in _RESERVED_METADATA_KEYS and value is not None:
            payload[key] = value
    payload["created_by"] = user.user_id
    payload["created_by_name"] = user.display_name

    dossier = await svc.create_dossier(name=name, batch_id=None, metadata=payload or None)
    job = dossier.latest_job()

    # Contract is always role=CONTRACT at order_index 0, annexes follow from 1.
    _contract_doc, _size, contract_path = await ingest_upload_file(
        svc=svc,
        dossier_id=dossier.id,
        upload=contract,
        role=DocumentRole.CONTRACT,
        order_index=0,
    )
    uploaded.append(contract_path)
    annex_paths: list[str] = []
    for index, annex in enumerate(annexes, start=1):
        _, _, annex_path = await ingest_upload_file(
            svc=svc,
            dossier_id=dossier.id,
            upload=annex,
            role=DocumentRole.ANNEX,
            order_index=index,
        )
        uploaded.append(annex_path)
        annex_paths.append(annex_path)

    # A file holding a contract and its annexes (metadata.split_pending) waits
    # for POST /dossiers/{id}/split: no OCR yet, so no page is read twice.
    split_pending = payload.get("split_pending") is True
    if not split_pending:
        # Roles were chosen at upload: confirm now so the worker compares
        # conflicts once every file is read, without the manifest screen.
        await svc.confirm_uploaded_manifest(dossier.id, user.user_id)

    return StagedDossier(
        dossier_id=dossier.id,
        job_id=job.id if job else None,
        contract_path=contract_path,
        annex_paths=annex_paths,
        split_pending=split_pending,
    )


async def discard_uploaded(paths: list[str]) -> None:
    """Best-effort delete of files written for a dossier that was never committed.

    Awaited in the caller's ``except`` (a background task would not run: FastAPI
    runs those only after a response). A delete that fails is logged; the
    object is then only storage that no row points at.
    """
    for path in paths:
        try:
            await storage.delete_object(path)
        except Exception:
            logger.warning("dossier.ingest.orphan_delete_failed", s3_path=path, exc_info=True)
    if paths:
        logger.info("dossier.ingest.orphans_removed", count=len(paths))


async def publish_dossier_uploaded(*, dossier_id: str, file_path: str) -> None:
    """After the commit: the Kafka worker opens the run and sends the AI1 OCR commands."""
    await messaging.publish_event(
        "dossier_events",
        {
            "event": "dossier.uploaded",
            "dossier_id": str(dossier_id),
            "file_path": file_path,
        },
    )


__all__ = [
    "DossierUploadMetadata",
    "PdfUpload",
    "StagedDossier",
    "check_document_count",
    "check_pdf",
    "discard_uploaded",
    "file_too_large",
    "ingest_upload_file",
    "parse_upload_metadata",
    "publish_dossier_uploaded",
    "read_pdf_upload",
    "stage_new_dossier",
]
