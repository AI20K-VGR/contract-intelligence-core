"""Run dossier purge after the tombstone request has committed."""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.application.services.contract_service import ContractService
from contract_intelligence.contract.infrastructure.persistence.deletion_ledger import (
    DeletionLedgerORM,
)
from contract_intelligence.contract.infrastructure.persistence.repository_impl import (
    DocumentRepositoryImpl,
    DossierRepositoryImpl,
    JobRepositoryImpl,
    ManifestRepositoryImpl,
)
from contract_intelligence.shared.persistence.session import get_session_factory
from contract_intelligence.shared.storage import get_file_storage

logger = structlog.get_logger(__name__)


def _service(session: AsyncSession, tenant_id: str) -> ContractService:
    return ContractService(
        dossier_repo=DossierRepositoryImpl(session, tenant_id),
        document_repo=DocumentRepositoryImpl(session, tenant_id),
        job_repo=JobRepositoryImpl(session, tenant_id),
        manifest_repo=ManifestRepositoryImpl(session, tenant_id),
        storage=get_file_storage(),
        tenant_id=tenant_id,
    )


async def purge_dossier(tenant_id: str, dossier_id: str) -> None:
    """Delete files and extracted text. Keeps the deletion ledger row."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            await _service(session, tenant_id).purge_dossier(dossier_id)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("dossier.purge_failed", dossier_id=dossier_id)
            await _mark_failed(tenant_id, dossier_id)


async def _mark_failed(tenant_id: str, dossier_id: str) -> None:
    factory = get_session_factory()
    async with factory() as session:
        repo = DossierRepositoryImpl(session, tenant_id)
        await repo.mark_purge_failed(dossier_id)
        await session.commit()


async def sweep_pending_purges() -> None:
    """Retry tombstones whose purge did not finish, including after a restore."""
    factory = get_session_factory()
    async with factory() as session:
        connection = await session.connection()
        await connection.run_sync(DeletionLedgerORM.__table__.create, checkfirst=True)
        result = await session.execute(
            select(DeletionLedgerORM.tenant_id, DeletionLedgerORM.dossier_id).where(
                DeletionLedgerORM.purge_status.in_(("pending", "failed"))
            )
        )
        pending = list(result.all())
    for tenant_id, dossier_id in pending:
        await purge_dossier(str(tenant_id), str(dossier_id))
