"""DossierDeletionService — tombstone + async content purge (2-step delete).

Mentor / FE contract:
  1. Tombstone — hide from list, block file access, cancel OCR jobs, write ledger
  2. Purge — delete PDF/page images/OCR/clauses/citations/tables/names/errors;
     keep usage_ledger, review_action, job_event, deletion_ledger, and shells
     for dossier / job / pipeline_run (never CASCADE DELETE those rows).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import structlog
from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.conflict.infrastructure.persistence.orm import (
    AnnexLinkORM,
    FindingORM,
    FindingSideORM,
)
from contract_intelligence.contract.infrastructure.persistence.deletion_ledger import (
    DeletionLedgerORM,
)
from contract_intelligence.contract.infrastructure.persistence.orm import (
    DocumentORM,
    DossierORM,
    JobORM,
    ManifestItemORM,
    ManifestORM,
)
from contract_intelligence.extraction.infrastructure.persistence.orm import (
    CitationORM,
    ClauseNodeORM,
    DocTableORM,
    FactORM,
    OcrLineORM,
    PageORM,
    PipelineRunORM,
    PipelineStepORM,
)
from contract_intelligence.shared.ai.client import AiServiceClient
from contract_intelligence.shared.base import new_ulid, utcnow
from contract_intelligence.shared.exceptions import NotFoundError
from contract_intelligence.shared.storage import FileStorage

logger = structlog.get_logger(__name__)

_ACTIVE_JOB_STATUSES = frozenset({"uploaded", "processing"})


@dataclass(frozen=True, slots=True)
class TombstoneResult:
    dossier_id: str
    deleted_at: datetime
    purge_status: str
    name: str
    already_tombstoned: bool = False


class DossierDeletionService:
    """Orchestrates tombstone (sync) and purge (async, separate session)."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        storage: FileStorage,
        ai_client: AiServiceClient,
        tenant_id: str,
    ) -> None:
        self._session = session
        self._storage = storage
        self._ai_client = ai_client
        self._tenant_id = tenant_id

    @property
    def session(self) -> AsyncSession:
        return self._session

    async def tombstone(self, dossier_id: str, *, actor_user_id: str) -> TombstoneResult:
        orm = await self._load_dossier_orm(dossier_id, for_update=True)
        if orm is None:
            raise NotFoundError(entity_type="Dossier", entity_id=dossier_id)

        if orm.deleted_at is not None:
            return TombstoneResult(
                dossier_id=orm.id,
                deleted_at=orm.deleted_at,
                purge_status=orm.purge_status or "pending",
                name=orm.name,
                already_tombstoned=True,
            )

        now = utcnow()
        orm.deleted_at = now
        orm.deleted_by = actor_user_id
        orm.purge_status = "pending"
        orm.purge_error = None
        orm.updated_at = now

        self._session.add(
            DeletionLedgerORM(
                id=new_ulid("led_"),
                tenant_id=self._tenant_id,
                dossier_id=dossier_id,
                requested_by=actor_user_id,
                tombstoned_at=now,
                purge_status="pending",
                evidence={"dossier_name_len": len(orm.name)},
            )
        )

        cancelled = await self._cancel_active_jobs(dossier_id)
        await self._session.flush()

        logger.info(
            "dossier.tombstoned",
            dossier_id=dossier_id,
            actor=actor_user_id,
            cancelled_jobs=cancelled,
            tenant_id=self._tenant_id,
        )
        return TombstoneResult(
            dossier_id=dossier_id,
            deleted_at=now,
            purge_status="pending",
            name=orm.name,
            already_tombstoned=False,
        )

    async def commit(self) -> None:
        """Commit before background purge.

        FastAPI runs that task before the request session commits.
        """
        await self._session.commit()

    async def purge(self, dossier_id: str) -> None:
        """Purge contract content. Caller must use a dedicated session + commit."""
        orm = await self._load_dossier_orm(dossier_id, for_update=True)
        if orm is None:
            logger.warning("dossier.purge_skip_missing", dossier_id=dossier_id)
            return
        if orm.deleted_at is None:
            logger.warning("dossier.purge_skip_not_tombstoned", dossier_id=dossier_id)
            return
        if orm.purge_status == "completed":
            return

        orm.purge_status = "running"
        orm.purge_error = None
        orm.updated_at = utcnow()
        await self._session.flush()

        blob_uris = await self._collect_blob_uris(dossier_id)
        deleted_blobs = 0
        for uri in blob_uris:
            if await self._delete_blob(uri):
                deleted_blobs += 1

        try:
            await self._purge_db_content(dossier_id)
            now = utcnow()
            orm = await self._load_dossier_orm(dossier_id, for_update=True)
            if orm is None:
                return
            orm.purge_status = "completed"
            orm.purge_completed_at = now
            orm.purge_error = None
            orm.name = "[deleted]"
            orm.metadata_json = None
            orm.checksum = None
            orm.updated_at = now
            await self._update_ledger(
                dossier_id,
                purge_status="completed",
                purged_at=now,
                evidence={"blobs_deleted": deleted_blobs, "blob_count": len(blob_uris)},
            )
            await self._session.flush()
            logger.info(
                "dossier.purged",
                dossier_id=dossier_id,
                blobs_deleted=deleted_blobs,
                tenant_id=self._tenant_id,
            )
        except Exception as exc:
            logger.exception("dossier.purge_failed", dossier_id=dossier_id)
            orm = await self._load_dossier_orm(dossier_id, for_update=True)
            if orm is not None:
                orm.purge_status = "failed"
                orm.purge_error = str(exc)[:2000]
                orm.updated_at = utcnow()
                await self._update_ledger(
                    dossier_id,
                    purge_status="failed",
                    purged_at=None,
                    evidence={"error_len": min(len(str(exc)), 500)},
                )
                await self._session.flush()
            raise

    async def _update_ledger(
        self,
        dossier_id: str,
        *,
        purge_status: str,
        purged_at: datetime | None,
        evidence: dict[str, int],
    ) -> None:
        result = await self._session.execute(
            select(DeletionLedgerORM).where(
                DeletionLedgerORM.dossier_id == dossier_id,
                DeletionLedgerORM.tenant_id == self._tenant_id,
            )
        )
        ledger = result.scalar_one_or_none()
        if ledger is None:
            return
        ledger.purge_status = purge_status
        ledger.purged_at = purged_at
        ledger.evidence = {**(ledger.evidence or {}), **evidence}

    async def _load_dossier_orm(
        self, dossier_id: str, *, for_update: bool = False
    ) -> DossierORM | None:
        stmt = select(DossierORM).where(
            DossierORM.id == dossier_id, DossierORM.tenant_id == self._tenant_id
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _cancel_active_jobs(self, dossier_id: str) -> int:
        stmt = select(JobORM).where(
            JobORM.dossier_id == dossier_id,
            JobORM.tenant_id == self._tenant_id,
            JobORM.status.in_(tuple(_ACTIVE_JOB_STATUSES)),
        )
        result = await self._session.execute(stmt)
        jobs = list(result.scalars().all())
        cancelled = 0
        for job in jobs:
            # Best-effort AI cancel — job.id / current_run_id may map to AI job id
            for candidate in (job.current_run_id, job.id):
                if not candidate:
                    continue
                try:
                    await self._ai_client.cancel_job(candidate)
                except Exception:
                    logger.warning(
                        "dossier.cancel_ai_job_failed",
                        dossier_id=dossier_id,
                        candidate=candidate,
                        exc_info=True,
                    )
            job.status = "cancelled"
            job.error_code = "dossier_deleted"
            job.error_detail = None
            job.lease_owner = None
            job.lease_expires_at = None
            job.updated_at = utcnow()
            cancelled += 1

        run_stmt = select(PipelineRunORM).where(
            PipelineRunORM.dossier_id == dossier_id,
            PipelineRunORM.tenant_id == self._tenant_id,
            PipelineRunORM.status.in_(("queued", "running")),
        )
        runs = list((await self._session.execute(run_stmt)).scalars().all())
        for run in runs:
            run.status = "cancelled"
            run.error_code = "dossier_deleted"
            run.error_detail = None
            run.finished_at = utcnow()

        return cancelled

    async def _collect_blob_uris(self, dossier_id: str) -> list[str]:
        uris: list[str] = []
        docs = (
            (
                await self._session.execute(
                    select(DocumentORM).where(
                        DocumentORM.dossier_id == dossier_id,
                        DocumentORM.tenant_id == self._tenant_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        doc_ids = [d.id for d in docs]
        for doc in docs:
            if doc.blob_uri:
                uris.append(doc.blob_uri)

        if doc_ids:
            pages = (
                (
                    await self._session.execute(
                        select(PageORM).where(PageORM.document_id.in_(doc_ids))
                    )
                )
                .scalars()
                .all()
            )
            for page in pages:
                if page.render_blob_uri:
                    uris.append(page.render_blob_uri)
                if page.preview_blob_uri:
                    uris.append(page.preview_blob_uri)
        # de-dupe preserve order
        seen: set[str] = set()
        out: list[str] = []
        for u in uris:
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out

    async def _delete_blob(self, uri: str) -> bool:
        ok = False
        try:
            await self._storage.delete(uri)
            ok = True
        except Exception:
            logger.warning("dossier.blob_storage_delete_failed", uri=uri, exc_info=True)
        if uri.startswith("s3://"):
            try:
                from contract_intelligence.infrastructure.storage import delete_object

                await delete_object(uri)
                ok = True
            except Exception:
                logger.warning("dossier.blob_s3_delete_failed", uri=uri, exc_info=True)
        return ok

    async def _purge_db_content(self, dossier_id: str) -> None:
        bind = self._session.get_bind()
        dialect = bind.dialect.name if bind is not None else ""
        if dialect == "postgresql":
            await self._session.execute(
                text("SELECT purge_dossier_contract_content(:id)"),
                {"id": dossier_id},
            )
            return
        await self._purge_db_content_python(dossier_id)

    async def _purge_db_content_python(self, dossier_id: str) -> None:
        """SQLite / test fallback — same semantics as the Postgres function."""
        docs = (
            (
                await self._session.execute(
                    select(DocumentORM).where(
                        DocumentORM.dossier_id == dossier_id,
                        DocumentORM.tenant_id == self._tenant_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        doc_ids = [d.id for d in docs]

        finding_ids = [
            f.id
            for f in (
                await self._session.execute(
                    select(FindingORM).where(FindingORM.dossier_id == dossier_id)
                )
            )
            .scalars()
            .all()
        ]
        if finding_ids:
            await self._session.execute(
                delete(FindingSideORM).where(FindingSideORM.finding_id.in_(finding_ids))
            )
        await self._session.execute(delete(FindingORM).where(FindingORM.dossier_id == dossier_id))
        await self._session.execute(
            delete(AnnexLinkORM).where(AnnexLinkORM.dossier_id == dossier_id)
        )

        if doc_ids:
            await self._session.execute(
                delete(DocTableORM).where(DocTableORM.document_id.in_(doc_ids))
            )
            await self._session.execute(
                delete(ClauseNodeORM).where(ClauseNodeORM.document_id.in_(doc_ids))
            )
            await self._session.execute(delete(FactORM).where(FactORM.document_id.in_(doc_ids)))
            await self._session.execute(
                delete(CitationORM).where(CitationORM.document_id.in_(doc_ids))
            )
            await self._session.execute(
                delete(OcrLineORM).where(OcrLineORM.document_id.in_(doc_ids))
            )
            await self._session.execute(
                update(PageORM)
                .where(PageORM.document_id.in_(doc_ids))
                .values(render_blob_uri=None, preview_blob_uri=None, features=None)
            )

        await self._session.execute(
            update(DocumentORM)
            .where(DocumentORM.dossier_id == dossier_id)
            .values(
                filename="[purged]",
                blob_uri=None,
                sha256="[purged]",
                signing_date=None,
                effective_date=None,
            )
        )
        await self._session.execute(
            update(DossierORM)
            .where(DossierORM.id == dossier_id)
            .values(name="[deleted]", metadata_json=None, checksum=None, updated_at=utcnow())
        )

        manifests = (
            (
                await self._session.execute(
                    select(ManifestORM).where(ManifestORM.dossier_id == dossier_id)
                )
            )
            .scalars()
            .all()
        )
        for m in manifests:
            await self._session.execute(
                update(ManifestItemORM)
                .where(ManifestItemORM.manifest_id == m.id)
                .values(filename="[purged]")
            )

        await self._session.execute(
            update(JobORM)
            .where(JobORM.dossier_id == dossier_id)
            .values(
                error_code=None,
                error_detail=None,
                lease_owner=None,
                lease_expires_at=None,
                updated_at=utcnow(),
            )
        )
        await self._session.execute(
            update(PipelineRunORM)
            .where(PipelineRunORM.dossier_id == dossier_id)
            .values(error_code=None, error_detail=None, config_snapshot=None)
        )
        run_ids = [
            r.id
            for r in (
                await self._session.execute(
                    select(PipelineRunORM).where(PipelineRunORM.dossier_id == dossier_id)
                )
            )
            .scalars()
            .all()
        ]
        if run_ids:
            await self._session.execute(
                update(PipelineStepORM)
                .where(PipelineStepORM.run_id.in_(run_ids))
                .values(metrics=None)
            )
        await self._session.flush()


async def run_dossier_purge(*, dossier_id: str, tenant_id: str) -> None:
    """BackgroundTasks entrypoint — opens a fresh session after request commit."""
    from contract_intelligence.shared.ai.client import get_ai_service_client
    from contract_intelligence.shared.persistence.session import get_session_factory
    from contract_intelligence.shared.storage import get_file_storage

    factory = get_session_factory()
    storage = get_file_storage()
    ai_client = get_ai_service_client()
    async with factory() as session:
        try:
            svc = DossierDeletionService(
                session=session,
                storage=storage,
                ai_client=ai_client,
                tenant_id=tenant_id,
            )
            await svc.purge(dossier_id)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("dossier.purge_background_failed", dossier_id=dossier_id)
            raise


async def sweep_pending_purges() -> None:
    """Retry tombstones whose purge did not finish, including after a restore."""
    from contract_intelligence.shared.persistence.session import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(DeletionLedgerORM.tenant_id, DeletionLedgerORM.dossier_id).where(
                DeletionLedgerORM.purge_status.in_(("pending", "failed"))
            )
        )
        pending = list(result.all())
    for tenant_id, dossier_id in pending:
        try:
            await run_dossier_purge(dossier_id=str(dossier_id), tenant_id=str(tenant_id))
        except Exception:
            logger.exception(
                "dossier.purge_sweep_item_failed",
                dossier_id=dossier_id,
                tenant_id=tenant_id,
            )


__all__ = [
    "DossierDeletionService",
    "TombstoneResult",
    "run_dossier_purge",
    "sweep_pending_purges",
]
