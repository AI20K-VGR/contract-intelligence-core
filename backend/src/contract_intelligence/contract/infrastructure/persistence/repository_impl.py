"""Contract repositories — real SQLAlchemy async implementations.

Layer: infrastructure (persistence) — concrete impl cho Dossier/Document/Job/Manifest.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.domain.entities.document import Document, DocumentRole
from contract_intelligence.contract.domain.entities.dossier import Dossier
from contract_intelligence.contract.domain.entities.job import Job, JobStatus
from contract_intelligence.contract.domain.repositories.document_repository import (
    DocumentRepository,
)
from contract_intelligence.contract.domain.repositories.dossier_repository import (
    DossierRepository,
)
from contract_intelligence.contract.domain.repositories.job_repository import (
    JobRepository,
)
from contract_intelligence.contract.infrastructure.persistence.orm import (
    DocumentORM,
    DossierORM,
    JobORM,
    ManifestItemORM,
    ManifestORM,
)
from contract_intelligence.shared.base import Page, utcnow

# ============================================================================
# Dossier
# ============================================================================


def _dossier_to_domain(orm: DossierORM) -> Dossier:
    return Dossier(
        id=orm.id,
        name=orm.name,
        batch_id=orm.batch_id,
        has_conflicts=orm.has_conflicts,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _dossier_from_domain(d: Dossier) -> DossierORM:
    return DossierORM(
        id=d.id,
        tenant_id="",  # set by caller / from session context
        name=d.name,
        batch_id=d.batch_id,
        has_conflicts=d.has_conflicts,
        status="uploaded",
    )


class DossierRepositoryImpl(DossierRepository):
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def get(self, dossier_id: str) -> Dossier | None:
        stmt = select(DossierORM).where(
            DossierORM.id == dossier_id, DossierORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _dossier_to_domain(orm) if orm else None

    async def list(
        self,
        *,
        status: str | None = None,
        has_conflicts: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[str]:
        stmt = select(DossierORM).where(DossierORM.tenant_id == self._tenant_id)
        if status:
            stmt = stmt.where(DossierORM.status == status)
        if has_conflicts is not None:
            stmt = stmt.where(DossierORM.has_conflicts == has_conflicts)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self._session.execute(count_stmt)
        total = int(total_result.scalar() or 0)
        stmt = stmt.order_by(DossierORM.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        orms = result.scalars().all()
        return Page(
            items=[_dossier_to_domain(o) for o in orms],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def add(self, dossier: Dossier) -> None:
        orm = _dossier_from_domain(dossier)
        orm.tenant_id = self._tenant_id
        self._session.add(orm)
        await self._session.flush()

    async def save(self, dossier: Dossier) -> None:
        stmt = select(DossierORM).where(
            DossierORM.id == dossier.id, DossierORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            await self.add(dossier)
            return
        orm.name = dossier.name
        orm.batch_id = dossier.batch_id
        orm.has_conflicts = dossier.has_conflicts
        orm.updated_at = utcnow()
        await self._session.flush()

    async def delete(self, dossier_id: str) -> None:
        stmt = select(DossierORM).where(
            DossierORM.id == dossier_id, DossierORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm:
            await self._session.delete(orm)
            await self._session.flush()

    async def update_status(self, dossier_id: str, status: str) -> None:
        stmt = select(DossierORM).where(
            DossierORM.id == dossier_id, DossierORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm:
            orm.status = status
            orm.updated_at = utcnow()
            await self._session.flush()

    async def lock(self, dossier_id: str, locked: bool = True) -> None:
        stmt = select(DossierORM).where(
            DossierORM.id == dossier_id, DossierORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm:
            orm.is_locked = locked
            orm.updated_at = utcnow()
            await self._session.flush()

    async def approve(self, dossier_id: str, checksum: str) -> None:
        stmt = select(DossierORM).where(
            DossierORM.id == dossier_id, DossierORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm:
            orm.is_approved = True
            orm.checksum = checksum
            orm.status = "approved"
            orm.updated_at = utcnow()
            await self._session.flush()


# ============================================================================
# Document
# ============================================================================


def _document_to_domain(orm: DocumentORM) -> Document:
    return Document(
        id=orm.id,
        dossier_id=orm.dossier_id,
        role=DocumentRole(orm.role),
        order_index=orm.order_index,
        filename=orm.filename,
        sha256=orm.sha256,
        blob_uri=orm.blob_uri,
        page_count=orm.page_count,
        lang_detected=orm.lang_detected,
        signing_date=orm.signing_date,
        effective_date=orm.effective_date,
        created_at=orm.created_at,
    )


def _document_from_domain(d: Document) -> DocumentORM:
    return DocumentORM(
        id=d.id,
        tenant_id="",
        dossier_id=d.dossier_id,
        role=d.role.value,
        order_index=d.order_index,
        filename=d.filename,
        sha256=d.sha256,
        blob_uri=d.blob_uri,
        page_count=d.page_count,
        lang_detected=d.lang_detected,
        signing_date=d.signing_date,
        effective_date=d.effective_date,
    )


class DocumentRepositoryImpl(DocumentRepository):
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def get(self, document_id: str) -> Document | None:
        stmt = select(DocumentORM).where(
            DocumentORM.id == document_id, DocumentORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _document_to_domain(orm) if orm else None

    async def list_by_dossier(self, dossier_id: str) -> list[Document]:
        stmt = (
            select(DocumentORM)
            .where(
                DocumentORM.dossier_id == dossier_id,
                DocumentORM.tenant_id == self._tenant_id,
            )
            .order_by(DocumentORM.order_index, DocumentORM.created_at)
        )
        result = await self._session.execute(stmt)
        return [_document_to_domain(o) for o in result.scalars().all()]

    async def list(
        self,
        *,
        dossier_id: str | None = None,
        role: DocumentRole | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[str]:
        stmt = select(DocumentORM).where(DocumentORM.tenant_id == self._tenant_id)
        if dossier_id:
            stmt = stmt.where(DocumentORM.dossier_id == dossier_id)
        if role:
            stmt = stmt.where(DocumentORM.role == role.value)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await self._session.execute(count_stmt)).scalar() or 0)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return Page(
            items=[_document_to_domain(o) for o in result.scalars().all()],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def add(self, document: Document) -> None:
        orm = _document_from_domain(document)
        orm.tenant_id = self._tenant_id
        self._session.add(orm)
        await self._session.flush()

    async def save(self, document: Document) -> None:
        stmt = select(DocumentORM).where(
            DocumentORM.id == document.id, DocumentORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            await self.add(document)
            return
        orm.role = document.role.value
        orm.order_index = document.order_index
        orm.filename = document.filename
        orm.page_count = document.page_count
        orm.lang_detected = document.lang_detected
        orm.signing_date = document.signing_date
        orm.effective_date = document.effective_date
        await self._session.flush()

    async def delete(self, document_id: str) -> None:
        stmt = select(DocumentORM).where(
            DocumentORM.id == document_id, DocumentORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm:
            await self._session.delete(orm)
            await self._session.flush()


# ============================================================================
# Job
# ============================================================================


def _job_to_domain(orm: JobORM) -> Job:
    return Job(
        id=orm.id,
        dossier_id=orm.dossier_id,
        batch_id=orm.batch_id,
        status=JobStatus(orm.status),
        has_conflicts=orm.has_conflicts,
        current_run_id=orm.current_run_id,
        error_code=orm.error_code,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


class JobRepositoryImpl(JobRepository):
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def get(self, job_id: str) -> Job | None:
        stmt = select(JobORM).where(
            JobORM.id == job_id, JobORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _job_to_domain(orm) if orm else None

    async def list(
        self, *, limit: int = 50, offset: int = 0, **filters: object
    ) -> Page[str]:
        stmt = select(JobORM).where(JobORM.tenant_id == self._tenant_id)
        if dossier_id := filters.get("dossier_id"):
            stmt = stmt.where(JobORM.dossier_id == dossier_id)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await self._session.execute(count_stmt)).scalar() or 0)
        stmt = stmt.order_by(JobORM.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return Page(
            items=[_job_to_domain(o) for o in result.scalars().all()],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def add(self, entity: Job) -> None:
        orm = JobORM(
            id=entity.id,
            tenant_id=self._tenant_id,
            dossier_id=entity.dossier_id,
            batch_id=entity.batch_id,
            status=entity.status.value,
            has_conflicts=entity.has_conflicts,
            current_run_id=entity.current_run_id,
            error_code=entity.error_code,
        )
        self._session.add(orm)
        await self._session.flush()

    async def save(self, entity: Job) -> None:
        stmt = select(JobORM).where(
            JobORM.id == entity.id, JobORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            await self.add(entity)
            return
        orm.status = entity.status.value
        orm.current_run_id = entity.current_run_id
        orm.error_code = entity.error_code
        orm.updated_at = utcnow()
        await self._session.flush()

    async def delete(self, job_id: str) -> None:
        stmt = select(JobORM).where(
            JobORM.id == job_id, JobORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm:
            await self._session.delete(orm)
            await self._session.flush()


# ============================================================================
# Manifest
# ============================================================================


class ManifestRepositoryImpl:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def get_by_dossier(self, dossier_id: str) -> ManifestORM | None:
        stmt = select(ManifestORM).where(
            ManifestORM.dossier_id == dossier_id,
            ManifestORM.tenant_id == self._tenant_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, dossier_id: str) -> ManifestORM:
        from ulid import ULID

        orm = ManifestORM(
            id=f"mft_{ULID()}",
            tenant_id=self._tenant_id,
            dossier_id=dossier_id,
            status="DRAFT",
        )
        self._session.add(orm)
        await self._session.flush()
        return orm

    async def add_item(self, item: ManifestItemORM) -> None:
        self._session.add(item)
        await self._session.flush()

    async def confirm(self, manifest_id: str, user_id: str) -> None:
        stmt = select(ManifestORM).where(
            ManifestORM.id == manifest_id, ManifestORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm:
            orm.status = "CONFIRMED"
            orm.confirmed_at = utcnow()
            orm.confirmed_by = user_id
            await self._session.flush()

    async def list_items(self, manifest_id: str) -> list[ManifestItemORM]:
        stmt = (
            select(ManifestItemORM)
            .where(ManifestItemORM.manifest_id == manifest_id)
            .order_by(ManifestItemORM.order_index)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


__all__ = [
    "DocumentRepositoryImpl",
    "DossierRepositoryImpl",
    "JobRepositoryImpl",
    "ManifestRepositoryImpl",
]
