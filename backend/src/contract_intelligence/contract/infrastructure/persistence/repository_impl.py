"""Contract repositories — real SQLAlchemy async implementations.

Layer: infrastructure (persistence) — concrete impl cho Dossier/Document/Job/Manifest.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.domain.entities.document import Document, DocumentRole
from contract_intelligence.contract.domain.entities.dossier import Dossier
from contract_intelligence.contract.domain.entities.job import Job, JobStatus
from contract_intelligence.contract.domain.entities.manifest import (
    Manifest,
    ManifestItem,
    ManifestRelation,
)
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
    ManifestRelationORM,
)
from contract_intelligence.shared.base import Page, new_ulid, utcnow

# ============================================================================
# Dossier
# ============================================================================


def _dossier_to_domain(orm: DossierORM) -> Dossier:
    return Dossier(
        id=orm.id,
        name=orm.name,
        batch_id=orm.batch_id,
        has_conflicts=orm.has_conflicts,
        metadata=orm.metadata_json,
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
        metadata_json=d.metadata,
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

    async def get_for_update(self, dossier_id: str) -> Dossier | None:
        """Lock dossier row for the current transaction (tenant-scoped)."""
        stmt = (
            select(DossierORM)
            .where(DossierORM.id == dossier_id, DossierORM.tenant_id == self._tenant_id)
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _dossier_to_domain(orm) if orm else None

    async def list(
        self,
        *,
        status: str | None = None,
        has_conflicts: bool | None = None,
        q: str | None = None,
        batch_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[str]:
        stmt = select(DossierORM).where(DossierORM.tenant_id == self._tenant_id)
        if status:
            stmt = stmt.where(DossierORM.status == status)
        if has_conflicts is not None:
            stmt = stmt.where(DossierORM.has_conflicts == has_conflicts)
        if q:
            stmt = stmt.where(DossierORM.name.ilike(f"%{q}%"))
        if batch_id:
            stmt = stmt.where(DossierORM.batch_id == batch_id)
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
        orm.metadata_json = dossier.metadata
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

    async def get_flags(self, dossier_id: str) -> dict[str, object] | None:
        stmt = select(DossierORM).where(
            DossierORM.id == dossier_id, DossierORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        return {
            "is_locked": bool(orm.is_locked),
            "is_approved": bool(orm.is_approved),
            "status": str(orm.status),
        }


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
        file_size_bytes=orm.file_size_bytes,
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
        file_size_bytes=d.file_size_bytes,
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
        stmt = select(JobORM).where(JobORM.id == job_id, JobORM.tenant_id == self._tenant_id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _job_to_domain(orm) if orm else None

    async def list(
        self,
        *,
        dossier_id: str | None = None,
        status: JobStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[str]:
        stmt = select(JobORM).where(JobORM.tenant_id == self._tenant_id)
        if dossier_id:
            stmt = stmt.where(JobORM.dossier_id == dossier_id)
        if status is not None:
            stmt = stmt.where(JobORM.status == status.value)
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
        stmt = select(JobORM).where(JobORM.id == entity.id, JobORM.tenant_id == self._tenant_id)
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
        stmt = select(JobORM).where(JobORM.id == job_id, JobORM.tenant_id == self._tenant_id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm:
            await self._session.delete(orm)
            await self._session.flush()


# ============================================================================
# Manifest
# ============================================================================


def _manifest_to_domain(
    orm: ManifestORM,
    items: list[ManifestItem],
    relations: list[ManifestRelation],
) -> Manifest:
    return Manifest(
        id=orm.id,
        dossier_id=orm.dossier_id,
        status=orm.status,
        version=int(orm.version or 1),
        items=list(items),
        relations=list(relations),
        confirmed_at=orm.confirmed_at,
        confirmed_by=orm.confirmed_by,
    )


def _manifest_item_to_domain(orm: ManifestItemORM) -> ManifestItem:
    return ManifestItem(
        id=orm.id,
        manifest_id=orm.manifest_id,
        document_id=orm.document_id or "",
        filename=orm.filename,
        doc_type=orm.doc_type,
        sha256=orm.sha256 or "",
        confidence=str(orm.confidence),
        order_index=int(orm.order_index),
        included=bool(orm.included),
        page_count=int(orm.page_count or 0),
        file_size_bytes=int(orm.file_size_bytes or 0),
    )


def _manifest_relation_to_domain(orm: ManifestRelationORM) -> ManifestRelation:
    return ManifestRelation(
        id=orm.id,
        manifest_id=orm.manifest_id,
        source_document_id=orm.source_document_id,
        target_document_id=orm.target_document_id,
        relation_type=orm.relation_type,
        confirmation=orm.confirmation,
    )


class ManifestRepositoryImpl:
    """Concrete implementation — convert ORM ↔ domain entities."""

    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def get_by_dossier(self, dossier_id: str) -> Manifest | None:
        stmt = select(ManifestORM).where(
            ManifestORM.dossier_id == dossier_id,
            ManifestORM.tenant_id == self._tenant_id,
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        items = await self.list_items(orm.id)
        relations = await self.list_relations(orm.id)
        return _manifest_to_domain(orm, items, relations)

    async def get_by_dossier_for_update(self, dossier_id: str) -> Manifest | None:
        stmt = (
            select(ManifestORM)
            .where(
                ManifestORM.dossier_id == dossier_id,
                ManifestORM.tenant_id == self._tenant_id,
            )
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        items = await self.list_items(orm.id)
        relations = await self.list_relations(orm.id)
        return _manifest_to_domain(orm, items, relations)

    async def create_with_default_items(
        self, dossier_id: str, documents: list[dict[str, object]]
    ) -> Manifest:
        """Tạo manifest pending + 1 item mỗi document + suggested annex_of relations."""
        manifest_orm = ManifestORM(
            id=new_ulid("mft_"),
            tenant_id=self._tenant_id,
            dossier_id=dossier_id,
            status="pending",
            version=1,
        )
        self._session.add(manifest_orm)
        await self._session.flush()

        contract_ids: list[str] = []
        annex_ids: list[str] = []
        for idx, doc in enumerate(documents):
            role = str(doc.get("role", "contract")).lower()
            doc_id = str(doc.get("id", ""))
            item = ManifestItemORM(
                id=new_ulid("mfi_"),
                manifest_id=manifest_orm.id,
                document_id=doc_id,
                filename=str(doc.get("filename", "")),
                doc_type=role,
                sha256=str(doc.get("sha256", "")),
                confidence="1.0",
                order_index=int(doc.get("order_index", idx) or idx),
                included=True,
                page_count=int(doc.get("page_count", 0) or 0),
                file_size_bytes=int(doc.get("file_size_bytes", 0) or 0),
            )
            self._session.add(item)
            if role == "annex":
                annex_ids.append(doc_id)
            else:
                contract_ids.append(doc_id)

        primary_contract = contract_ids[0] if contract_ids else None
        if primary_contract:
            for annex_id in annex_ids:
                self._session.add(
                    ManifestRelationORM(
                        id=new_ulid("mrel_"),
                        manifest_id=manifest_orm.id,
                        source_document_id=annex_id,
                        target_document_id=primary_contract,
                        relation_type="annex_of",
                        confirmation="unconfirmed",
                    )
                )

        await self._session.flush()
        items = await self.list_items(manifest_orm.id)
        relations = await self.list_relations(manifest_orm.id)
        return Manifest(
            id=manifest_orm.id,
            dossier_id=dossier_id,
            status="pending",
            version=1,
            items=items,
            relations=relations,
        )

    async def add_item(self, item: ManifestItemORM) -> None:
        self._session.add(item)
        await self._session.flush()

    async def confirm(self, manifest_id: str, user_id: str) -> None:
        """Legacy simple confirm — prefer ``apply_confirmation`` for full API."""
        stmt = select(ManifestORM).where(
            ManifestORM.id == manifest_id, ManifestORM.tenant_id == self._tenant_id
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm:
            orm.status = "confirmed"
            orm.confirmed_at = utcnow()
            orm.confirmed_by = user_id
            orm.version = int(orm.version or 1) + 1
            await self._session.flush()

    async def apply_confirmation(
        self,
        *,
        manifest_id: str,
        user_id: str,
        new_version: int,
        members: list[ManifestItem],
        relations: list[ManifestRelation],
    ) -> Manifest:
        stmt = (
            select(ManifestORM)
            .where(ManifestORM.id == manifest_id, ManifestORM.tenant_id == self._tenant_id)
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            msg = f"Manifest {manifest_id} not found"
            raise LookupError(msg)

        # Replace membership rows
        existing_items = (
            await self._session.execute(
                select(ManifestItemORM).where(ManifestItemORM.manifest_id == manifest_id)
            )
        ).scalars().all()
        for row in existing_items:
            await self._session.delete(row)

        for member in members:
            self._session.add(
                ManifestItemORM(
                    id=member.id or new_ulid("mfi_"),
                    manifest_id=manifest_id,
                    document_id=member.document_id,
                    filename=member.filename,
                    doc_type=member.doc_type,
                    sha256=member.sha256,
                    confidence=member.confidence or "1.0",
                    order_index=member.order_index,
                    included=member.included,
                    page_count=member.page_count,
                    file_size_bytes=member.file_size_bytes,
                )
            )

        # Replace relations
        existing_rels = (
            await self._session.execute(
                select(ManifestRelationORM).where(
                    ManifestRelationORM.manifest_id == manifest_id
                )
            )
        ).scalars().all()
        for row in existing_rels:
            await self._session.delete(row)

        for rel in relations:
            self._session.add(
                ManifestRelationORM(
                    id=rel.id or new_ulid("mrel_"),
                    manifest_id=manifest_id,
                    source_document_id=rel.source_document_id,
                    target_document_id=rel.target_document_id,
                    relation_type=rel.relation_type,
                    confirmation=rel.confirmation,
                )
            )

        # Update document roles / order for included members only (never delete files)
        for member in members:
            if not member.included or not member.document_id:
                continue
            doc_stmt = select(DocumentORM).where(
                DocumentORM.id == member.document_id,
                DocumentORM.tenant_id == self._tenant_id,
            )
            doc_result = await self._session.execute(doc_stmt)
            doc_orm = doc_result.scalar_one_or_none()
            if doc_orm is None:
                continue
            doc_orm.role = member.doc_type
            doc_orm.order_index = member.order_index

        orm.status = "confirmed"
        orm.version = new_version
        orm.confirmed_at = utcnow()
        orm.confirmed_by = user_id
        await self._session.flush()

        items = await self.list_items(manifest_id)
        rels = await self.list_relations(manifest_id)
        return _manifest_to_domain(orm, items, rels)

    async def list_items(self, manifest_id: str) -> list[ManifestItem]:
        stmt = (
            select(ManifestItemORM)
            .where(ManifestItemORM.manifest_id == manifest_id)
            .order_by(ManifestItemORM.order_index)
        )
        result = await self._session.execute(stmt)
        return [_manifest_item_to_domain(o) for o in result.scalars().all()]

    async def list_relations(self, manifest_id: str) -> list[ManifestRelation]:
        stmt = (
            select(ManifestRelationORM)
            .where(ManifestRelationORM.manifest_id == manifest_id)
            .order_by(ManifestRelationORM.created_at)
        )
        result = await self._session.execute(stmt)
        return [_manifest_relation_to_domain(o) for o in result.scalars().all()]


__all__ = [
    "DocumentRepositoryImpl",
    "DossierRepositoryImpl",
    "JobRepositoryImpl",
    "ManifestRepositoryImpl",
]
