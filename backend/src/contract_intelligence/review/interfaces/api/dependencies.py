"""Review FastAPI dependencies — composition root."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.review.application.services.review_service import ReviewService
from contract_intelligence.review.infrastructure.persistence.repository_impl import (
    ReviewRepositoryImpl,
)
from contract_intelligence.shared.auth.tenant import get_tenant_id
from contract_intelligence.shared.persistence import get_async_session


async def get_review_service(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    tenant_id: Annotated[str, Depends(get_tenant_id)],
) -> ReviewService:
    return ReviewService(
        repo=ReviewRepositoryImpl(session, tenant_id),
        tenant_id=tenant_id,
    )


ReviewServiceDep = Annotated[ReviewService, Depends(get_review_service)]


__all__ = ["ReviewServiceDep", "get_review_service"]
