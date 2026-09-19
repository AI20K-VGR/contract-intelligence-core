"""Contract FastAPI dependencies — composition root."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.application.services.contract_service import (
    ContractService,
)
from contract_intelligence.contract.infrastructure.persistence.repository_impl import (
    DocumentRepositoryImpl,
    DossierRepositoryImpl,
    JobRepositoryImpl,
    ManifestRepositoryImpl,
)
from contract_intelligence.shared.auth.tenant import get_tenant_id
from contract_intelligence.shared.persistence import get_async_session
from contract_intelligence.shared.storage import FileStorage, get_file_storage


async def get_contract_service(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    storage: Annotated[FileStorage, Depends(get_file_storage)],
) -> ContractService:
    """Compose ContractService bound to current tenant + session + storage."""
    return ContractService(
        dossier_repo=DossierRepositoryImpl(session, tenant_id),
        document_repo=DocumentRepositoryImpl(session, tenant_id),
        job_repo=JobRepositoryImpl(session, tenant_id),
        manifest_repo=ManifestRepositoryImpl(session, tenant_id),
        storage=storage,
        tenant_id=tenant_id,
    )


ContractServiceDep = Annotated[ContractService, Depends(get_contract_service)]


__all__ = ["ContractServiceDep", "get_contract_service"]
