"""Review FastAPI dependencies — composition root."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM
from contract_intelligence.review.application.services.review_service import ReviewService
from contract_intelligence.review.infrastructure.persistence.orm import ReviewItemORM
from contract_intelligence.review.infrastructure.persistence.repository_impl import (
    ReviewRepositoryImpl,
)
from contract_intelligence.shared.acl import AclAction, dossier_access_decision
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
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


def _deny(message: str = "Dossier access denied") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "ACL_DENIED", "message": message},
    )


async def require_review_dossier_access(
    dossier_id: Annotated[str, Path(min_length=1)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> None:
    dossier = await session.get(DossierORM, dossier_id)
    if dossier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Dossier {dossier_id} not found"},
        )
    if not dossier_access_decision(
        action=AclAction.REVIEW_READ,
        principal=user,
        dossier_id=dossier_id,
        dossier_tenant_id=dossier.tenant_id,
        metadata=dossier.metadata_json,
    ):
        raise _deny()


async def require_review_item_access(
    item_id: Annotated[str, Path(min_length=1)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> None:
    item = await session.get(ReviewItemORM, item_id)
    if item is None or item.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Review item {item_id} not found"},
        )
    dossier = await session.get(DossierORM, item.dossier_id)
    if dossier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Dossier {item.dossier_id} not found"},
        )
    if not dossier_access_decision(
        action=AclAction.REVIEW_READ,
        principal=user,
        dossier_id=item.dossier_id,
        dossier_tenant_id=dossier.tenant_id,
        metadata=dossier.metadata_json,
    ):
        raise _deny()


async def require_review_item_mutation_access(
    item_id: Annotated[str, Path(min_length=1)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> None:
    item = await session.get(ReviewItemORM, item_id)
    if item is None or item.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Review item {item_id} not found"},
        )
    dossier = await session.get(DossierORM, item.dossier_id)
    if dossier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Dossier {item.dossier_id} not found"},
        )
    if not dossier_access_decision(
        action=AclAction.REVIEW_MUTATE,
        principal=user,
        dossier_id=item.dossier_id,
        dossier_tenant_id=dossier.tenant_id,
        metadata=dossier.metadata_json,
    ):
        raise _deny()


__all__ = [
    "ReviewServiceDep",
    "get_review_service",
    "require_review_dossier_access",
    "require_review_item_access",
    "require_review_item_mutation_access",
]
