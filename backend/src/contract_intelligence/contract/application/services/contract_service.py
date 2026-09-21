"""Contract application service — compose dossier/document/job/manifest logic.

Layer: application — orchestrates infrastructure impls (qua Protocols).
"""

from __future__ import annotations

import hashlib
from typing import Any, BinaryIO

import structlog

from contract_intelligence.contract.domain.entities.document import Document, DocumentRole
from contract_intelligence.contract.domain.entities.dossier import Dossier
from contract_intelligence.contract.domain.entities.job import Job, JobStatus
from contract_intelligence.contract.domain.entities.manifest import Manifest
from contract_intelligence.contract.domain.repositories.document_repository import (
    DocumentRepository,
)
from contract_intelligence.contract.domain.repositories.dossier_repository import (
    DossierRepository,
)
from contract_intelligence.contract.domain.repositories.job_repository import (
    JobRepository,
)
from contract_intelligence.contract.domain.repositories.manifest_repository import (
    ManifestRepository,
)
from contract_intelligence.shared.base import new_ulid
from contract_intelligence.shared.exceptions import NotFoundError
from contract_intelligence.shared.storage import FileStorage

logger = structlog.get_logger(__name__)


class ContractService:
    """Use-case orchestration cho Contract BC.

    Phương thức:
        create_dossier(...)  — creates Dossier + initial Job (UPLOADED)
        upload_document(...)
        list_dossiers(...)
        get_dossier(...)
        patch_dossier(...)
        list_documents(...)
        get_document_blob(...)
        get_or_create_manifest(...)
        confirm_manifest(...)
    """

    def __init__(
        self,
        *,
        dossier_repo: DossierRepository,
        document_repo: DocumentRepository,
        job_repo: JobRepository,
        manifest_repo: ManifestRepository,
        storage: FileStorage,
        tenant_id: str,
    ) -> None:
        self._dossier_repo = dossier_repo
        self._document_repo = document_repo
        self._job_repo = job_repo
        self._manifest_repo = manifest_repo
        self._storage = storage
        self._tenant_id = tenant_id

    async def create_dossier(
        self,
        *,
        name: str,
        batch_id: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> Dossier:
        """Create dossier + initial Job (status=uploaded) in one use-case.

        Per openapi.yaml createDossier: dossier/document/job are created together;
        documents are added via upload_document() after this call.
        """
        dossier = Dossier(
            id=new_ulid("dos_"),
            name=name,
            batch_id=batch_id,
            metadata=metadata,
        )
        await self._dossier_repo.add(dossier)

        job = Job(
            id=new_ulid("job_"),
            dossier_id=dossier.id,
            batch_id=batch_id,
            status=JobStatus.UPLOADED,
        )
        await self._job_repo.add(job)
        dossier.jobs = [job]

        logger.info(
            "dossier.created",
            dossier_id=dossier.id,
            job_id=job.id,
            tenant_id=self._tenant_id,
        )
        return dossier

    async def upload_document(
        self,
        *,
        dossier_id: str,
        filename: str,
        content: BinaryIO,
        role: DocumentRole,
        order_index: int = 0,
        file_size_bytes: int | None = None,
    ) -> Document:
        # Verify dossier exists + tenant
        dossier = await self._dossier_repo.get(dossier_id)
        if dossier is None:
            raise NotFoundError(entity_type="Dossier", entity_id=dossier_id)

        # Compute sha256 + save to storage
        data = content.read()
        sha256 = hashlib.sha256(data).hexdigest()
        size_bytes = file_size_bytes if file_size_bytes is not None else len(data)

        # Lưu file vào storage
        blob_key = f"contracts/{dossier_id}/{sha256[:2]}/{filename}"
        await self._storage.put(blob_key, _bytes_to_stream(data))

        document = Document(
            id=new_ulid("doc_"),
            dossier_id=dossier_id,
            role=role,
            order_index=order_index,
            filename=filename,
            sha256=sha256,
            blob_uri=blob_key,
            file_size_bytes=size_bytes,
        )
        await self._document_repo.add(document)
        logger.info(
            "document.uploaded",
            document_id=document.id,
            dossier_id=dossier_id,
            filename=filename,
            sha256=sha256,
            size_bytes=size_bytes,
        )
        return document

    async def list_dossiers(
        self,
        *,
        status: str | None = None,
        has_conflicts: bool | None = None,
        q: str | None = None,
        batch_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Dossier], int]:
        from typing import cast

        page = cast(
            Any,  # Page is generic with bound=str — runtime carries Dossier entities
            await self._dossier_repo.list(
                status=status,
                has_conflicts=has_conflicts,
                q=q,
                batch_id=batch_id,
                limit=limit,
                offset=offset,
            ),
        )
        items = list(page.items)
        # Hydrate latest job onto each dossier for DossierSummary.latest_job_status
        for dossier in items:
            await self._hydrate_latest_job(dossier)
        return items, page.total

    async def get_dossier(self, dossier_id: str) -> Dossier:
        dossier = await self._dossier_repo.get(dossier_id)
        if dossier is None:
            raise NotFoundError(entity_type="Dossier", entity_id=dossier_id)
        await self._hydrate_latest_job(dossier)
        return dossier

    async def patch_dossier(
        self,
        dossier_id: str,
        *,
        name: str | None,
        metadata: dict[str, object] | None = None,
    ) -> Dossier:
        dossier = await self.get_dossier(dossier_id)
        if name:
            dossier.name = name
        if metadata is not None:
            dossier.metadata = metadata  # type: ignore[assignment]
        await self._dossier_repo.save(dossier)
        return dossier

    async def _hydrate_latest_job(self, dossier: Dossier) -> None:
        """Load latest Job onto dossier.jobs for navigation / DTO mapping."""
        if dossier.jobs:
            return
        page = await self._job_repo.list(dossier_id=dossier.id, limit=1, offset=0)
        jobs = list(page.items)
        if jobs:
            dossier.jobs = [jobs[0]]  # type: ignore[list-item]

    async def list_documents(self, dossier_id: str) -> list[Document]:
        return await self._document_repo.list_by_dossier(dossier_id)

    async def get_document(self, document_id: str) -> Document:
        doc = await self._document_repo.get(document_id)
        if doc is None:
            raise NotFoundError(entity_type="Document", entity_id=document_id)
        return doc

    async def get_document_blob(self, document_id: str) -> tuple[bytes, str]:
        """Trả về (file_bytes, filename) — cho content endpoint streaming."""
        doc = await self.get_document(document_id)
        data = await self._storage.get(doc.blob_uri)
        return data, doc.filename

    async def get_or_create_manifest(self, dossier_id: str) -> Manifest:
        """Lấy hoặc tạo manifest draft cho dossier.

        Application layer gọi Protocol — infrastructure lo toàn bộ ORM.
        """
        existing = await self._manifest_repo.get_by_dossier(dossier_id)
        if existing:
            return existing
        # Verify dossier tồn tại
        await self.get_dossier(dossier_id)
        # Truyền plain dicts (id/filename/role/sha256) — không leak ORM lên application
        documents = await self._document_repo.list_by_dossier(dossier_id)
        documents_payload: list[dict[str, object]] = [
            {"id": d.id, "filename": d.filename, "role": d.role.value, "sha256": d.sha256}
            for d in documents
        ]
        return await self._manifest_repo.create_with_default_items(dossier_id, documents_payload)

    async def confirm_manifest(self, dossier_id: str, user_id: str) -> Manifest:
        manifest = await self._manifest_repo.get_by_dossier(dossier_id)
        if manifest is None:
            raise NotFoundError(entity_type="Manifest", entity_id=dossier_id)
        await self._manifest_repo.confirm(manifest.id, user_id)
        # Cập nhật dossier status → ready for extraction
        await self._dossier_repo.update_status(dossier_id, "extracted")
        # Refresh sau confirm
        refreshed = await self._manifest_repo.get_by_dossier(dossier_id)
        return refreshed if refreshed is not None else manifest


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


class _BytesStream:
    """Wrap bytes thành stream-like object cho storage.put()."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            chunk = self._data[self._pos :]
            self._pos = len(self._data)
            return chunk
        chunk = self._data[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk


def _bytes_to_stream(data: bytes) -> BinaryIO:
    return _BytesStream(data)  # type: ignore[return-value]


__all__ = ["ContractService"]
