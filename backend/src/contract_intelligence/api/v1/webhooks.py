"""Inbound webhooks for AI1 (OCRSnapshot) and AI2 (CandidateFinding).

AI services POST asynchronous processing results here. Endpoints are
unauthenticated at the FastAPI layer (service-to-service; network policy
and shared secrets can be layered later).

Canonical persistence for DOC-05c envelopes lives in ``shared.ai.persistence``.
Loose CandidateFinding payloads still advance status to ``pending_review`` and
seed ReviewItem rows so the HITL queue is never empty after AI2 callback.
"""

from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, status
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.domain.entities.job import JobStatus
from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM, JobORM
from contract_intelligence.infrastructure.ai_adapters import (
    AiAdapterError,
    submit_to_ai2,
)
from contract_intelligence.schemas.webhooks import AI1SnapshotPayload, AI2FindingsPayload
from contract_intelligence.shared.ai.persistence import (
    persist_ai2_comparison,
    persist_ai2_extraction,
)
from contract_intelligence.shared.base import new_ulid, utcnow
from contract_intelligence.shared.persistence import get_async_session

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


async def _update_job_and_dossier_status(
    session: AsyncSession,
    *,
    status_value: str,
    dossier_id: str | None = None,
    run_id: str | None = None,
) -> tuple[str | None, str | None]:
    """Persist job (+ dossier) status. Returns ``(dossier_id, tenant_id)``."""
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
        return dossier_id, None

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
    return resolved_dossier_id, job.tenant_id


async def _seed_candidate_review_items(
    session: AsyncSession,
    *,
    tenant_id: str,
    dossier_id: str,
    run_id: str,
    findings: list[Any],
) -> int:
    """Create open ReviewItem rows from loose CandidateFinding payloads."""
    created = 0
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        target_id = str(finding.get("finding_id") or finding.get("id") or new_ulid("fnd_"))
        reason = str(
            finding.get("summary")
            or finding.get("rationale")
            or finding.get("key_or_topic")
            or "ai2_candidate_finding"
        )[:500]
        severity = str(finding.get("severity") or "medium").lower()
        priority = "P1" if severity == "high" else "P2" if severity == "medium" else "P3"
        await session.execute(
            text(
                """
                INSERT INTO review_item (
                    id, tenant_id, dossier_id, run_id, target_type, target_id,
                    reason, priority, status, version
                ) VALUES (
                    :id, :tenant_id, :dossier_id, :run_id, 'finding', :target_id,
                    :reason, :priority, 'open', 1
                )
                """
            ),
            {
                "id": new_ulid("ri_"),
                "tenant_id": tenant_id,
                "dossier_id": dossier_id,
                "run_id": run_id,
                "target_id": target_id,
                "reason": reason,
                "priority": priority,
            },
        )
        created += 1
    if created:
        await session.flush()
    return created


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
        "policy_flags": {"egress_allowed": False, "use_vector": True},
        "provenance": provenance,
    }

    try:
        ai2_response = await submit_to_ai2(ai2_payload)
    except AiAdapterError as exc:
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
    """Persist AI2 results when DOC-05c-shaped, else seed ReviewItems; set pending_review."""
    dossier_id, tenant_id = await _update_job_and_dossier_status(
        session,
        status_value=JobStatus.PENDING_REVIEW.value,
        run_id=payload.run_id,
    )

    persisted_facts = 0
    persisted_findings = 0
    review_items = 0

    # DOC-05c extraction envelope(s) nested in facts[]
    for block in payload.facts:
        if not isinstance(block, dict) or "document_id" not in block:
            continue
        if tenant_id is None:
            break
        try:
            persisted_facts += await persist_ai2_extraction(
                session,
                tenant_id=tenant_id,
                extraction=block,
                run_id=payload.run_id,
            )
        except Exception:
            logger.exception("webhooks.ai2.persist_extraction_failed", run_id=payload.run_id)

    # DOC-05c comparison envelope as a single findings object, or wrap loose list
    if tenant_id and dossier_id and payload.findings:
        comparison_candidate: dict[str, Any] | None = None
        first = payload.findings[0] if payload.findings else None
        if isinstance(first, dict) and first.get("schema_version", "").startswith("ai2.comparison"):
            comparison_candidate = first
        elif all(isinstance(f, dict) and "finding_type" in f for f in payload.findings):
            comparison_candidate = {
                "schema_version": "ai2.comparison.v2",
                "dossier_id": dossier_id,
                "annex_links": [],
                "findings": payload.findings,
            }
        if comparison_candidate is not None:
            try:
                persisted_findings = await persist_ai2_comparison(
                    session,
                    tenant_id=tenant_id,
                    comparison=comparison_candidate,
                    run_id=payload.run_id,
                )
            except Exception:
                logger.exception("webhooks.ai2.persist_comparison_failed", run_id=payload.run_id)

    if tenant_id and dossier_id and persisted_findings == 0 and payload.findings:
        review_items = await _seed_candidate_review_items(
            session,
            tenant_id=tenant_id,
            dossier_id=dossier_id,
            run_id=payload.run_id,
            findings=payload.findings,
        )

    if dossier_id and payload.findings:
        await session.execute(
            update(DossierORM)
            .where(DossierORM.id == dossier_id)
            .values(has_conflicts=True, updated_at=utcnow())
        )
        await session.flush()

    logger.info(
        "webhooks.ai2.findings_received",
        run_id=payload.run_id,
        facts=len(payload.facts),
        findings=len(payload.findings),
        index_contribution_keys=list(payload.index_contribution.keys()),
        persisted_facts=persisted_facts,
        persisted_findings=persisted_findings,
        review_items_seeded=review_items,
    )
    return {
        "status": "ok",
        "run_id": payload.run_id,
        "job_status": JobStatus.PENDING_REVIEW.value,
        "persisted_facts": persisted_facts,
        "persisted_findings": persisted_findings,
        "review_items_seeded": review_items,
        "index_contribution": payload.index_contribution,
    }
