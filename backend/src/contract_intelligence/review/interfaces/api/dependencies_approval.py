"""Approval FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM
from contract_intelligence.contract.infrastructure.persistence.repository_impl import (
    DocumentRepositoryImpl,
    DossierRepositoryImpl,
)
from contract_intelligence.review.application.services.approval_service import (
    ApprovalService,
)
from contract_intelligence.shared.acl import AclAction, dossier_access_decision
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
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


async def require_approval_access(
    dossier_id: Annotated[str, Path(min_length=1)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> None:
    """Require the trusted administrator and dossier-level approval ACL."""
    dossier = await session.get(DossierORM, dossier_id)
    if dossier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Dossier {dossier_id} not found"},
        )
    if not dossier_access_decision(
        action=AclAction.APPROVE,
        principal=user,
        dossier_id=dossier_id,
        dossier_tenant_id=dossier.tenant_id,
        metadata=dossier.metadata_json,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACL_DENIED", "message": "Dossier access denied"},
        )


async def require_lock_access(
    dossier_id: Annotated[str, Path(min_length=1)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> None:
    """Require dossier ACL for lock mutations (reviewer/admin)."""
    dossier = await session.get(DossierORM, dossier_id)
    if dossier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Dossier not found"},
        )
    if not dossier_access_decision(
        action=AclAction.REVIEW_MUTATE,
        principal=user,
        dossier_id=dossier_id,
        dossier_tenant_id=dossier.tenant_id,
        metadata=dossier.metadata_json,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACL_DENIED", "message": "Dossier access denied"},
        )


async def require_external_approval_access(
    dossier_id: Annotated[str, Path(min_length=1)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> None:
    """Require dossier ACL for external approval creation/read."""
    dossier = await session.get(DossierORM, dossier_id)
    if dossier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Dossier not found"},
        )
    if not dossier_access_decision(
        action=AclAction.APPROVE,
        principal=user,
        dossier_id=dossier_id,
        dossier_tenant_id=dossier.tenant_id,
        metadata=dossier.metadata_json,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACL_DENIED", "message": "Dossier access denied"},
        )


async def require_external_approval_read_access(
    dossier_id: Annotated[str, Path(min_length=1)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> None:
    """Require dossier query ACL for listing external approvals."""
    dossier = await session.get(DossierORM, dossier_id)
    if dossier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Dossier not found"},
        )
    if not dossier_access_decision(
        action=AclAction.QUERY,
        principal=user,
        dossier_id=dossier_id,
        dossier_tenant_id=dossier.tenant_id,
        metadata=dossier.metadata_json,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACL_DENIED", "message": "Dossier access denied"},
        )


__all__ = [
    "ApprovalServiceDep",
    "get_approval_service",
    "require_approval_access",
    "require_external_approval_access",
    "require_external_approval_read_access",
    "require_lock_access",
]
