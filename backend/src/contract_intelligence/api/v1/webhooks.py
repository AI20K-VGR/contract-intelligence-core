"""Inbound webhooks for AI1 (OCRSnapshot) and AI2 (CandidateFinding).

AI services POST asynchronous processing results here. Endpoints are
unauthenticated at the FastAPI layer (service-to-service; network policy
and shared secrets can be layered later).
"""

from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.domain.entities.job import JobStatus
from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM, JobORM
from contract_intelligence.infrastructure.ai_adapters import (
    AiAdapterError,
    submit_to_ai2,
)
from contract_intelligence.schemas.webhooks import AI1SnapshotPayload, AI2FindingsPayload
from contract_intelligence.shared.base import utcnow
from contract_intelligence.shared.persistence import get_async_session

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


async def _update_job_and_dossier_status(
    session: AsyncSession,
    *,
    status_value: str,
    dossier_id: str | None = None,
    run_id: str | None = None,
) -> str | None:
    """Persist job (+ dossier) status. Returns the resolved ``dossier_id`` if found."""
    now = utcnow()
    job: JobORM | None = None

    if run_id:
        result = await session.execute(
            select(JobORM).where(JobORM.current_run_id == run_id).limit(1)
        )
        job = result.scalar_one_or_none()

    if job is None and dossier_id:
        result = await session.execute(
            select(JobORM)
            .where(JobORM.dossier_id == dossier_id)
            .order_by(JobORM.created_at.desc())
            .limit(1)
        )
        job = result.scalar_one_or_none()

    if job is None:
        logger.warning(
            "webhooks.job_not_found",
            dossier_id=dossier_id,
            run_id=run_id,
            target_status=status_value,
        )
        return dossier_id

    job.status = status_value
    job.updated_at = now
    if run_id and not job.current_run_id:
        job.current_run_id = run_id
    resolved_dossier_id = job.dossier_id

    await session.execute(
        update(DossierORM)
        .where(DossierORM.id == resolved_dossier_id)
        .values(status=status_value, updated_at=now)
    )
    await session.flush()
    logger.info(
        "webhooks.status_updated",
        job_id=job.id,
        dossier_id=resolved_dossier_id,
        status=status_value,
    )
    return resolved_dossier_id


@router.post(
    "/ai1/snapshot",
    status_code=status.HTTP_200_OK,
    summary="AI1 OCR snapshot webhook",
)
async def receive_ai1_snapshot(
    payload: AI1SnapshotPayload,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Accept an OCRSnapshot, mark the job extracted, and hand off to AI2."""
    provenance = payload.provenance or {}
    dossier_id = provenance.get("dossier_id")
    run_id = provenance.get("run_id")
    if dossier_id is not None:
        dossier_id = str(dossier_id)
    if run_id is not None:
        run_id = str(run_id)

    # Simulate persisting snapshot metadata by advancing job/dossier state.
    await _update_job_and_dossier_status(
        session,
        status_value=JobStatus.EXTRACTED.value,
        dossier_id=dossier_id,
        run_id=run_id,
    )
    logger.info(
        "webhooks.ai1.snapshot_received",
        snapshot_id=payload.snapshot_id,
        version=payload.version,
        digest=payload.digest,
        pages=len(payload.pages),
        dossier_id=dossier_id,
        run_id=run_id,
    )

    ai2_payload: dict[str, Any] = {
        "snapshot_id": payload.snapshot_id,
        "snapshot_version": payload.version,
        "digest": payload.digest,
        "dossier_members": [],
        "role_relation_map": {},
        "policy_flags": {"egress_allowed": True, "use_vector": True},
    }

    try:
        ai2_response = await submit_to_ai2(ai2_payload)
    except AiAdapterError as exc:
        # Best-effort handoff — AI1 snapshot is already accepted; do not fail the
        # webhook solely because AI2 is unreachable (local E2E / partial stack).
        logger.error(
            "webhooks.ai1.ai2_handoff_failed",
            snapshot_id=payload.snapshot_id,
            error=str(exc),
        )
        ai2_response = {"status": "handoff_failed", "error": str(exc)}

    return {
        "status": "ok",
        "snapshot_id": payload.snapshot_id,
        "job_status": JobStatus.EXTRACTED.value,
        "ai2": ai2_response,
    }


@router.post(
    "/ai2/findings",
    status_code=status.HTTP_200_OK,
    summary="AI2 candidate findings webhook",
)
async def receive_ai2_findings(
    payload: AI2FindingsPayload,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Accept CandidateFinding results and move the dossier into HITL review."""
    await _update_job_and_dossier_status(
        session,
        status_value=JobStatus.PENDING_REVIEW.value,
        run_id=payload.run_id,
    )
    logger.info(
        "webhooks.ai2.findings_received",
        run_id=payload.run_id,
        facts=len(payload.facts),
        findings=len(payload.findings),
    )
    return {
        "status": "ok",
        "run_id": payload.run_id,
        "job_status": JobStatus.PENDING_REVIEW.value,
    }
