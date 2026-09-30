"""Human steps of the dossier lifecycle: pending_review → reviewed → approved.

The worker owns the states up to ``pending_review``; these steps are taken by
people. The dossier row and its latest job move together (the frontend reads
the job's status), and every step is written to the append-only audit trail.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.domain.entities.job import JobStatus
from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM, JobORM
from contract_intelligence.shared.audit import add_audit_event
from contract_intelligence.shared.base import utcnow


async def advance_dossier_status(
    session: AsyncSession,
    *,
    tenant_id: str,
    dossier_id: str,
    from_status: JobStatus,
    to_status: JobStatus,
    actor_id: str,
    detail: dict[str, Any] | None = None,
) -> bool:
    """Move the dossier and its latest job from ``from_status`` to ``to_status``.

    Returns False (and writes nothing) when the dossier is not in
    ``from_status``, so a repeated call is a no-op. The caller holds the
    dossier row lock and commits.
    """
    dossier = await session.scalar(
        select(DossierORM).where(
            DossierORM.id == dossier_id,
            DossierORM.tenant_id == tenant_id,
            DossierORM.deleted_at.is_(None),
        )
    )
    if dossier is None or dossier.status != from_status.value:
        return False
    now = utcnow()
    dossier.status = to_status.value
    dossier.updated_at = now

    job = await session.scalar(
        select(JobORM)
        .where(JobORM.dossier_id == dossier_id, JobORM.tenant_id == tenant_id)
        .order_by(JobORM.created_at.desc())
        .limit(1)
    )
    if job is not None and job.status == from_status.value:
        job.status = to_status.value
        job.updated_at = now

    add_audit_event(
        session,
        tenant_id=tenant_id,
        action=f"dossier.{to_status.value}",
        entity_type="dossier",
        entity_id=dossier_id,
        actor_id=actor_id,
        dossier_id=dossier_id,
        run_id=job.current_run_id if job is not None else None,
        from_state=from_status.value,
        to_state=to_status.value,
        detail=detail or {},
    )
    await session.flush()
    return True


__all__ = ["advance_dossier_status"]
