import pymupdf
from sqlalchemy import select

from app.domain import DomainError, require
from app.models import Document, Dossier
from app.storage import digest


def lock_dossier(db, dossier_id):
    dossier = db.scalar(select(Dossier).where(Dossier.id == dossier_id).with_for_update())
    require(dossier is not None, "DOSSIER_NOT_FOUND", 404)
    return dossier


def ingest(db, store, dossier_id, role, content, config):
    dossier = lock_dossier(db, dossier_id)
    require(dossier.active_job_id is None, "MANIFEST_FROZEN_CREATE_NEW_DOSSIER")
    require(len(content) <= config.max_upload_bytes, "UPLOAD_TOO_LARGE", 413)
    require(content.startswith(b"%PDF-"), "INVALID_PDF", 422)
    try:
        with pymupdf.open(stream=content, filetype="pdf") as pdf:
            require(not pdf.needs_pass, "PDF_ENCRYPTED", 422)
            require(0 < len(pdf) <= config.max_pages, "PAGE_LIMIT", 422)
            page_count = len(pdf)
    except (RuntimeError, ValueError) as exc:
        raise DomainError("PDF_CORRUPT", 422) from exc
    docs = list(db.scalars(select(Document).where(Document.dossier_id == dossier_id)))
    require(not any(d.sha256 == digest(content) for d in docs), "DUPLICATE_DOCUMENT")
    require(
        role != "contract" or not any(d.role == "contract" for d in docs), "EXACTLY_ONE_CONTRACT"
    )
    doc = Document(
        dossier_id=dossier_id,
        role=role,
        sha256=digest(content),
        storage_key=store.put(content, "pdf"),
        page_count=page_count,
    )
    db.add(doc)
    dossier.revision += 1
    db.flush()
    return {"id": doc.id, "sha256": doc.sha256, "page_count": doc.page_count}
