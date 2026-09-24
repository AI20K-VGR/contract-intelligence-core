"""Contract application service — compose dossier/document/job/manifest logic.

Layer: application — orchestrates infrastructure impls (qua Protocols).
"""

from __future__ import annotations

import hashlib
from typing import Any, BinaryIO, cast

import structlog

from contract_intelligence.contract.application.dtos.manifest_dtos import (
    ConfirmManifestRequest,
    ManifestDTO,
)
from contract_intelligence.contract.application.services.manifest_confirmation import (
    build_manifest_dto,
    validate_and_prepare_confirmation,
)
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
from contract_intelligence.shared.utils import safe_filename

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
        blob_uri: str | None = None,
    ) -> Document:
        # Verify dossier exists + tenant
        dossier = await self._dossier_repo.get(dossier_id)
        if dossier is None:
            raise NotFoundError(entity_type="Dossier", entity_id=dossier_id)

        # Compute sha256 + save to storage
        data = content.read()
        sha256 = hashlib.sha256(data).hexdigest()
        size_bytes = file_size_bytes if file_size_bytes is not None else len(data)

        # Always persist bytes in app FileStorage so content streaming works
        # (tests use FakeFileStorage; prod may dual-write while MinIO is canonical).
        safe_name = safe_filename(filename, fallback=f"{role.value.lower()}.pdf")
        local_key = f"contracts/{dossier_id}/{sha256[:2]}/{safe_name}"
        storage_key = blob_uri if blob_uri is not None else local_key
        await self._storage.put(storage_key, _bytes_to_stream(data))
        stored_uri = blob_uri if blob_uri is not None else local_key

        document = Document(
            id=new_ulid("doc_"),
            dossier_id=dossier_id,
            role=role,
            order_index=order_index,
            filename=safe_name,
            sha256=sha256,
            blob_uri=stored_uri,
            file_size_bytes=size_bytes,
        )
        await self._document_repo.add(document)
        logger.info(
            "document.uploaded",
            document_id=document.id,
            dossier_id=dossier_id,
            filename=safe_name,
            sha256=sha256,
            size_bytes=size_bytes,
            blob_uri=stored_uri,
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
            dossier.metadata = metadata
        await self._dossier_repo.save(dossier)
        return dossier

    async def request_deletion(self, dossier_id: str, *, requested_by: str) -> None:
        """Block access and cancel jobs. File purge runs after this commits."""
        started = await self._dossier_repo.begin_deletion(dossier_id, requested_by)
        if not started:
            raise NotFoundError(entity_type="Dossier", entity_id=dossier_id)

    async def purge_dossier(self, dossier_id: str) -> None:
        """Delete files and contract text for a dossier already on the ledger."""
        if not await self._dossier_repo.has_deletion(dossier_id):
            return
        if not await self._dossier_repo.dossier_row_exists(dossier_id):
            await self._dossier_repo.mark_purged(dossier_id, {"documents": 0, "objects": 0})
            return
        documents = await self._document_repo.list_by_dossier(dossier_id)
        uris = [document.blob_uri for document in documents if document.blob_uri]
        uris.extend(await self._dossier_repo.related_blob_uris(dossier_id))
        for blob_uri in uris:
            await self._purge_blob(dossier_id, blob_uri)
        await self._dossier_repo.delete(dossier_id)
        await self._dossier_repo.mark_purged(
            dossier_id,
            {"documents": len(documents), "objects": len(uris)},
        )

    async def _purge_blob(self, dossier_id: str, blob_uri: str) -> None:
        """Best-effort removal of a local copy and the MinIO object."""
        if not blob_uri.strip():
            return
        try:
            await self._storage.delete(blob_uri)
        except Exception as exc:  # noqa: BLE001 — object storage is the other copy
            logger.warning(
                "dossier.delete.blob_failed",
                dossier_id=dossier_id,
                blob_uri=blob_uri,
                error=str(exc),
            )
        if blob_uri.startswith(("file://", "local://")):
            return
        try:
            from contract_intelligence.infrastructure.storage import delete_object

            await delete_object(blob_uri)
        except Exception as exc:  # noqa: BLE001 — DB purge still has to proceed
            logger.warning(
                "dossier.delete.object_failed",
                dossier_id=dossier_id,
                blob_uri=blob_uri,
                error=str(exc),
            )

    async def _hydrate_latest_job(self, dossier: Dossier) -> None:
        """Load latest Job onto dossier.jobs for navigation / DTO mapping."""
        if dossier.jobs:
            return
        page = await self._job_repo.list(dossier_id=dossier.id, limit=1, offset=0)
        if page.items:
            dossier.jobs = [cast(Job, page.items[0])]

    async def list_documents(self, dossier_id: str) -> list[Document]:
        await self.get_dossier(dossier_id)
        return await self._document_repo.list_by_dossier(dossier_id)

    async def get_document(self, document_id: str) -> Document:
        doc = await self._document_repo.get(document_id)
        if doc is None:
            raise NotFoundError(entity_type="Document", entity_id=document_id)
        await self.get_dossier(doc.dossier_id)
        return doc

    async def get_document_blob(self, document_id: str) -> tuple[bytes, str]:
        """Trả về (file_bytes, filename) — cho content endpoint streaming."""
        doc = await self.get_document(document_id)
        if await self._dossier_repo.is_tombstoned(doc.dossier_id):
            raise NotFoundError(entity_type="Document", entity_id=document_id)
        if not doc.blob_uri:
            raise NotFoundError(entity_type="Document", entity_id=document_id)
        if doc.blob_uri.startswith("s3://"):
            from contract_intelligence.infrastructure.storage import download_object

            try:
                data = await download_object(doc.blob_uri)
            except Exception as exc:
                logger.warning(
                    "document.content.missing",
                    document_id=document_id,
                    blob_uri=doc.blob_uri,
                    error=str(exc),
                )
                raise NotFoundError(entity_type="Document", entity_id=document_id) from exc
        else:
            try:
                data = await self._storage.get(doc.blob_uri)
            except FileNotFoundError as exc:
                raise NotFoundError(entity_type="Document", entity_id=document_id) from exc
        return data, doc.filename

    async def get_or_create_manifest(self, dossier_id: str) -> Manifest:
        """Lấy hoặc tạo manifest pending cho dossier.

        Application layer gọi Protocol — infrastructure lo toàn bộ ORM.
        """
        existing = await self._manifest_repo.get_by_dossier(dossier_id)
        if existing:
            return existing
        # Verify dossier tồn tại (tenant-scoped → 404 cross-tenant)
        await self.get_dossier(dossier_id)
        documents = await self._document_repo.list_by_dossier(dossier_id)
        documents_payload: list[dict[str, object]] = [
            {
                "id": d.id,
                "filename": d.filename,
                "role": d.role.value,
                "sha256": d.sha256,
                "order_index": d.order_index,
                "page_count": d.page_count,
                "file_size_bytes": d.file_size_bytes,
            }
            for d in documents
        ]
        return await self._manifest_repo.create_with_default_items(dossier_id, documents_payload)

    async def get_manifest(self, dossier_id: str) -> ManifestDTO:
        """GET /dossiers/{id}/manifest — current ManifestDTO (create draft if needed)."""
        dossier = await self.get_dossier(dossier_id)
        manifest = await self.get_or_create_manifest(dossier_id)
        documents = await self._document_repo.list_by_dossier(dossier_id)
        latest = dossier.latest_job()
        return build_manifest_dto(
            manifest,
            latest_job_status=latest.status.value if latest else None,
            documents_by_id={d.id: d for d in documents},
        )

    async def confirm_manifest(
        self,
        dossier_id: str,
        user_id: str,
        request: ConfirmManifestRequest | None = None,
    ) -> ManifestDTO | Manifest:
        """Confirm manifest.

        When ``request`` is provided (new API), run full validation + membership
        persistence inside the request transaction. Without ``request``, keep the
        legacy simple confirm used by older callers/tests.
        """
        # Lock dossier row (tenant-scoped) for the confirm transaction
        locked = await self._dossier_repo.get_for_update(dossier_id)
        if locked is None:
            raise NotFoundError(entity_type="Dossier", entity_id=dossier_id)
        await self._hydrate_latest_job(locked)

        if request is None:
            manifest = await self._manifest_repo.get_by_dossier_for_update(dossier_id)
            if manifest is None:
                raise NotFoundError(entity_type="Manifest", entity_id=dossier_id)
            await self._manifest_repo.confirm(manifest.id, user_id)
            await self._dossier_repo.update_status(dossier_id, "extracted")
            refreshed = await self._manifest_repo.get_by_dossier(dossier_id)
            return refreshed if refreshed is not None else manifest

        manifest = await self._manifest_repo.get_by_dossier_for_update(dossier_id)
        if manifest is None:
            # Auto-create pending manifest then re-lock
            await self.get_or_create_manifest(dossier_id)
            manifest = await self._manifest_repo.get_by_dossier_for_update(dossier_id)
            if manifest is None:
                raise NotFoundError(entity_type="Manifest", entity_id=dossier_id)

        documents = await self._document_repo.list_by_dossier(dossier_id)
        members, relations = validate_and_prepare_confirmation(
            manifest=manifest,
            request=request,
            dossier_documents=documents,
        )

        new_version = int(manifest.version or 1) + 1
        # Persist membership/roles/relations — do NOT delete excluded files,
        # do NOT start a new pipeline run.
        confirmed = await self._manifest_repo.apply_confirmation(
            manifest_id=manifest.id,
            user_id=user_id,
            new_version=new_version,
            members=members,
            relations=relations,
        )
        await self._dossier_repo.update_status(dossier_id, "extracted")

        latest = locked.latest_job()
        return build_manifest_dto(
            confirmed,
            latest_job_status=latest.status.value if latest else None,
            documents_by_id={d.id: d for d in documents},
        )


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
