"""Conflict FastAPI dependencies — composition root."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.conflict.application.services.conflict_service import (
    ConflictService,
)
from contract_intelligence.conflict.infrastructure.persistence.repository_impl import (
    AnnexLinkRepositoryImpl,
    FindingRepositoryImpl,
)
from contract_intelligence.shared.auth.tenant import get_tenant_id
from contract_intelligence.shared.persistence import get_async_session


async def get_conflict_service(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    tenant_id: Annotated[str, Depends(get_tenant_id)],
) -> ConflictService:
    return ConflictService(
        finding_repo=FindingRepositoryImpl(session, tenant_id),
        annex_link_repo=AnnexLinkRepositoryImpl(session, tenant_id),
        tenant_id=tenant_id,
    )


ConflictServiceDep = Annotated[ConflictService, Depends(get_conflict_service)]


__all__ = ["ConflictServiceDep", "get_conflict_service"]
