"""Dossier ACL for extraction endpoints addressed by dossier, run or document id.

Same decision as the contract routes (:func:`shared.acl.dossier_access_decision`):
a share grant must be live and, for changes, carry ``permission="edit"``.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.infrastructure.persistence.orm import (
    DocumentORM,
    DossierORM,
)
from contract_intelligence.extraction.infrastructure.persistence.orm import PipelineRunORM
from contract_intelligence.shared.acl import AclAction, dossier_access_decision
from contract_intelligence.shared.auth import AuthenticatedUser


async def require_dossier_action(
    session: AsyncSession,
    user: AuthenticatedUser,
    *,
    action: AclAction,
    dossier_id: str | None = None,
    run_id: str | None = None,
    document_id: str | None = None,
) -> DossierORM:
    """Resolve the dossier behind the id given and enforce ``action`` on it.

    404 when it does not exist in the caller's tenant or is deleted; 403 when
    the caller has no live grant allowing ``action``.
    """
    if run_id is not None:
        dossier_id = await session.scalar(
            select(PipelineRunORM.dossier_id).where(
                PipelineRunORM.id == run_id, PipelineRunORM.tenant_id == user.tenant_id
            )
        )
    elif document_id is not None:
        dossier_id = await session.scalar(
            select(DocumentORM.dossier_id).where(
                DocumentORM.id == document_id, DocumentORM.tenant_id == user.tenant_id
            )
        )
    dossier = await session.get(DossierORM, dossier_id) if dossier_id else None
    if dossier is None or dossier.deleted_at is not None or dossier.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier not found")
    if not dossier_access_decision(
        action=action,
        principal=user,
        dossier_id=dossier.id,
        dossier_tenant_id=dossier.tenant_id,
        metadata=dossier.metadata_json,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn chỉ có quyền xem hồ sơ này, hoặc quyền đã hết hạn.",
        )
    return dossier


__all__ = ["require_dossier_action"]
