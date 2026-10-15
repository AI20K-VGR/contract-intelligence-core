"""Explicit, audited per-dossier AI2 content-sharing consent endpoint."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StrictBool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.api.dossier_guard import require_dossier_action
from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM
from contract_intelligence.shared.acl import AclAction
from contract_intelligence.shared.audit import add_audit_event
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
from contract_intelligence.shared.persistence import get_async_session

router = APIRouter(prefix="/dossiers", tags=["Dossier consent"])
CONSENT_KEY = "ai2_content_sharing_consent"


class ConsentUpdate(BaseModel):
    enabled: StrictBool


class ConsentResponse(BaseModel):
    dossier_id: str
    enabled: bool
    effective_from: Literal["next_request"] = "next_request"


@router.patch("/{dossier_id}/ai2-content-sharing-consent", response_model=ConsentResponse)
async def update_ai2_content_sharing_consent(
    dossier_id: str,
    body: ConsentUpdate,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ConsentResponse:
    dossier = await session.scalar(
        select(DossierORM)
        .where(DossierORM.id == dossier_id, DossierORM.tenant_id == user.tenant_id)
        .with_for_update()
    )
    if dossier is None or dossier.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Not found")
    await require_dossier_action(
        session, user, action=AclAction.DOSSIER_MANAGE, dossier_id=dossier_id
    )
    metadata = dict(dossier.metadata_json or {})
    had_consent = CONSENT_KEY in metadata
    prior = metadata.get(CONSENT_KEY)
    if prior is not body.enabled:
        prior_state = (
            "absent"
            if not had_consent
            else str(prior).lower()
            if isinstance(prior, bool) or prior is None
            else "invalid"
        )
        metadata[CONSENT_KEY] = body.enabled
        dossier.metadata_json = metadata
        add_audit_event(
            session,
            tenant_id=dossier.tenant_id,
            actor_id=user.user_id,
            action="ai2.content_sharing_consent_changed",
            entity_type="dossier",
            entity_id=dossier.id,
            dossier_id=dossier.id,
            from_state=prior_state,
            to_state=str(body.enabled).lower(),
            detail={
                "prior": prior if isinstance(prior, bool) else prior_state,
                "new": body.enabled,
            },
        )
    return ConsentResponse(dossier_id=dossier.id, enabled=body.enabled)
