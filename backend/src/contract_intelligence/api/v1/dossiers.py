"""HITL dossier approval endpoint — final gate after review items are resolved."""

from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.api.v1.reviews import list_unresolved_simulated
from contract_intelligence.contract.domain.entities.job import JobStatus
from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM, JobORM
from contract_intelligence.review.infrastructure.persistence.orm import ReviewItemORM
from contract_intelligence.shared.base import utcnow
from contract_intelligence.shared.persistence import get_async_session

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/dossiers", tags=["Dossiers"])


@router.post(
    "/{id}/approve",
    status_code=status.HTTP_200_OK,
    summary="Approve dossier after all review items are resolved",
    responses={
        404: {"description": "Dossier not found"},
        409: {"description": "Unresolved review items remain"},
    },
)
async def approve_dossier(
    id: str,  # noqa: A002 — path param name per API contract
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Simulate HITL approval: require resolved review items, set status APPROVED."""
    dossier = await session.get(DossierORM, id)
    if dossier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Dossier {id} not found"},
        )

    # Prefer real DB open items when present; fall back to simulated store.
    db_open = await session.execute(
        select(ReviewItemORM.id).where(
            ReviewItemORM.dossier_id == id,
            ReviewItemORM.status.in_(["open", "needs_more_evidence", "needs_review"]),
        )
    )
    open_ids = [row[0] for row in db_open.all()]
    if not open_ids:
        open_ids = list_unresolved_simulated(id)

    if open_ids:
        logger.warning(
            "dossiers.approve.unresolved_items",
            dossier_id=id,
            open_count=len(open_ids),
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "UNRESOLVED_REVIEW_ITEMS",
                "message": "All review items must be resolved before approval",
                "open_review_item_ids": open_ids,
            },
        )

    now = utcnow()
    approved = JobStatus.APPROVED.value
    dossier.status = approved
    dossier.is_approved = True
    dossier.is_locked = True
    dossier.updated_at = now

    await session.execute(
        update(JobORM).where(JobORM.dossier_id == id).values(status=approved, updated_at=now)
    )
    await session.flush()

    logger.info("dossiers.approve.ok", dossier_id=id, status=approved)
    return {
        "status": "ok",
        "message": "Dossier approved successfully",
        "dossier_id": id,
        "dossier_status": approved,
    }
