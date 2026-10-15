"""Explicit, audited per-dossier AI2 content-sharing consent endpoint.

Turning consent on also asks AI2 to rebuild the dossier from its stored OCR
(the same ``dossier.ai2.reindex`` event as ``POST /dossiers/{id}/ai2/reindex``)
when its last run has finished AI2. Without that, the result on screen stays
the one AI2 produced without consent (``RULE_ONLY_NO_CONSENT``) until someone
finds the reindex API.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StrictBool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.api.dossier_guard import require_dossier_action
from contract_intelligence.config.logging import get_logger
from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM, JobORM
from contract_intelligence.contract.interfaces.api.routers.contract_router import (
    _AI2_REINDEXABLE,
)
from contract_intelligence.infrastructure import messaging
from contract_intelligence.shared.acl import AclAction
from contract_intelligence.shared.audit import add_audit_event
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
from contract_intelligence.shared.persistence import get_async_session

logger = get_logger(__name__)

router = APIRouter(prefix="/dossiers", tags=["Dossier consent"])
CONSENT_KEY = "ai2_content_sharing_consent"


class ConsentUpdate(BaseModel):
    enabled: StrictBool


class ConsentResponse(BaseModel):
    dossier_id: str
    enabled: bool
    effective_from: Literal["next_request"] = "next_request"
    # True when turning consent on queued an AI2 rebuild of the last run.
    ai2_reindex_queued: bool = False


async def _reindexable_run(session: AsyncSession, dossier: DossierORM) -> str | None:
    """Run of the dossier's latest job when AI2 has finished it, else None."""
    job = await session.scalar(
        select(JobORM)
        .where(JobORM.dossier_id == dossier.id, JobORM.tenant_id == dossier.tenant_id)
        .order_by(JobORM.created_at.desc(), JobORM.id.desc())
        .limit(1)
    )
    if job is None or not job.current_run_id or job.status not in _AI2_REINDEXABLE:
        return None
    return str(job.current_run_id)


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
    reindex_run: str | None = None
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
        # Only on: turning it off cannot recall what was sent, and the next
        # run (or reindex) already drops the LLM proposals.
        if body.enabled:
            reindex_run = await _reindexable_run(session, dossier)
        if reindex_run is not None:
            add_audit_event(
                session,
                tenant_id=dossier.tenant_id,
                actor_id=user.user_id,
                action="ai2.reindex_on_consent",
                entity_type="pipeline_run",
                entity_id=reindex_run,
                dossier_id=dossier.id,
                run_id=reindex_run,
                detail={"reason": "content_sharing_consent_enabled"},
            )
    # The worker reads consent from the database when it builds the AI2
    # request: commit before the event, or it could still read the old value.
    await session.commit()
    queued = False
    if reindex_run is not None:
        try:
            await messaging.publish_event(
                "dossier_events",
                {"event": "dossier.ai2.reindex", "dossier_id": dossier.id, "run_id": reindex_run},
            )
            queued = True
        except Exception:  # noqa: BLE001 — consent is saved; the reindex API still works
            logger.warning(
                "dossier.consent.reindex_not_queued", dossier_id=dossier.id, run_id=reindex_run
            )
    return ConsentResponse(dossier_id=dossier.id, enabled=body.enabled, ai2_reindex_queued=queued)
