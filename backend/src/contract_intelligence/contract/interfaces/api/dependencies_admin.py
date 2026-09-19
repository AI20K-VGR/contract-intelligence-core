"""FastAPI dependencies cho Batches + Ops + Optimization."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.application.services.batch_service import BatchService
from contract_intelligence.contract.application.services.optimization_service import (
    OptimizationService,
)
from contract_intelligence.shared.auth.tenant import get_tenant_id
from contract_intelligence.shared.persistence import get_async_session


async def get_batch_service(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    tenant_id: Annotated[str, Depends(get_tenant_id)],
) -> BatchService:
    return BatchService(session=session, tenant_id=tenant_id)


async def get_optimization_service(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    tenant_id: Annotated[str, Depends(get_tenant_id)],
) -> OptimizationService:
    return OptimizationService(session=session, tenant_id=tenant_id)


BatchServiceDep = Annotated[BatchService, Depends(get_batch_service)]
OptimizationServiceDep = Annotated[OptimizationService, Depends(get_optimization_service)]


__all__ = [
    "BatchServiceDep",
    "OptimizationServiceDep",
    "get_batch_service",
    "get_optimization_service",
]
