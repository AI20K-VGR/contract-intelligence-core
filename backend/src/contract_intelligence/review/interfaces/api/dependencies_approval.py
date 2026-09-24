"""Approval FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.infrastructure.persistence.repository_impl import (
    DocumentRepositoryImpl,
    DossierRepositoryImpl,
)
from contract_intelligence.review.application.services.approval_service import (
    ApprovalService,
)
from contract_intelligence.shared.auth.tenant import get_tenant_id
from contract_intelligence.shared.persistence import get_async_session


async def get_approval_service(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    tenant_id: Annotated[str, Depends(get_tenant_id)],
) -> ApprovalService:
    return ApprovalService(
        session=session,
        tenant_id=tenant_id,
        dossier_repo=DossierRepositoryImpl(session, tenant_id),
        document_repo=DocumentRepositoryImpl(session, tenant_id),
    )


ApprovalServiceDep = Annotated[ApprovalService, Depends(get_approval_service)]


__all__ = ["ApprovalServiceDep", "get_approval_service"]
