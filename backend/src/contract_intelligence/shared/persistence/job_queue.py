"""Postgres-backed job queue — claim via FOR UPDATE SKIP LOCKED (no Redis/Celery).

Workers claim ``job`` rows in ``uploaded`` status, hold a short lease, and an
async reaper resets stalled ``processing`` jobs whose ``lease_expires_at``
has passed back to ``uploaded`` so another worker can pick them up.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from contract_intelligence.shared.base import utcnow

logger = structlog.get_logger(__name__)

# Claimable statuses — ready work + re-queued after lease expiry.
_CLAIMABLE_STATUS = "uploaded"


@dataclass(slots=True, frozen=True)
class ClaimedJob:
    """A job row successfully claimed by a worker."""

    id: str
    tenant_id: str
    dossier_id: str
    batch_id: str | None
    current_run_id: str | None
    status: str
    lease_owner: str
    lease_expires_at: Any


async def claim_next_job(
    session: AsyncSession,
    *,
    worker_id: str,
    lease_seconds: int = 60,
) -> ClaimedJob | None:
    """Atomically claim the oldest ready job.

    Postgres path uses ``FOR UPDATE SKIP LOCKED`` so concurrent workers never
    double-claim. Non-Postgres dialects fall back to a simple ordered select
    + update (sufficient for local SQLite tests).
    """
    dialect = session.bind.dialect.name if session.bind is not None else "postgresql"
    lease_until = utcnow() + timedelta(seconds=lease_seconds)

    if dialect == "postgresql":
        result = await session.execute(
            text(
                """
                WITH cte AS (
                    SELECT id
                    FROM job
                    WHERE status = :status
                    ORDER BY created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE job AS j
                SET status = 'processing',
                    lease_owner = :worker_id,
                    lease_expires_at = :lease_until,
                    updated_at = :now
                FROM cte
                WHERE j.id = cte.id
                RETURNING
                    j.id, j.tenant_id, j.dossier_id, j.batch_id,
                    j.current_run_id, j.status, j.lease_owner, j.lease_expires_at
                """
            ),
            {
                "status": _CLAIMABLE_STATUS,
                "worker_id": worker_id,
                "lease_until": lease_until,
                "now": utcnow(),
            },
        )
    else:
        # SQLite / other — best-effort single-worker claim for tests.
        pick = await session.execute(
            text(
                """
                SELECT id FROM job
                WHERE status = :status
                ORDER BY created_at ASC
                LIMIT 1
                """
            ),
            {"status": _CLAIMABLE_STATUS},
        )
        row_id = pick.scalar_one_or_none()
        if row_id is None:
            return None
        result = await session.execute(
            text(
                """
                UPDATE job
                SET status = 'processing',
                    lease_owner = :worker_id,
                    lease_expires_at = :lease_until,
                    updated_at = :now
                WHERE id = :id AND status = :status
                RETURNING
                    id, tenant_id, dossier_id, batch_id,
                    current_run_id, status, lease_owner, lease_expires_at
                """
            ),
            {
                "id": row_id,
                "status": _CLAIMABLE_STATUS,
                "worker_id": worker_id,
                "lease_until": lease_until,
                "now": utcnow(),
            },
        )

    row = result.mappings().first()
    if row is None:
        return None
    claimed = ClaimedJob(
        id=row["id"],
        tenant_id=row["tenant_id"],
        dossier_id=row["dossier_id"],
        batch_id=row["batch_id"],
        current_run_id=row["current_run_id"],
        status=row["status"],
        lease_owner=row["lease_owner"],
        lease_expires_at=row["lease_expires_at"],
    )
    logger.info(
        "job_queue.claimed",
        job_id=claimed.id,
        worker_id=worker_id,
        dossier_id=claimed.dossier_id,
        lease_expires_at=str(lease_until),
    )
    return claimed


async def extend_lease(
    session: AsyncSession,
    *,
    job_id: str,
    worker_id: str,
    lease_seconds: int = 60,
) -> bool:
    """Heartbeat — renew lease while the worker is still processing."""
    lease_until = utcnow() + timedelta(seconds=lease_seconds)
    result = await session.execute(
        text(
            """
            UPDATE job
            SET lease_expires_at = :lease_until, updated_at = :now
            WHERE id = :job_id
              AND lease_owner = :worker_id
              AND status = 'processing'
            """
        ),
        {
            "job_id": job_id,
            "worker_id": worker_id,
            "lease_until": lease_until,
            "now": utcnow(),
        },
    )
    return int(getattr(result, "rowcount", 0) or 0) > 0


async def complete_job(
    session: AsyncSession,
    *,
    job_id: str,
    worker_id: str,
    status: str = "extracted",
) -> None:
    """Release lease and mark terminal success status."""
    await session.execute(
        text(
            """
            UPDATE job
            SET status = :status,
                lease_owner = NULL,
                lease_expires_at = NULL,
                updated_at = :now
            WHERE id = :job_id AND lease_owner = :worker_id
            """
        ),
        {"job_id": job_id, "worker_id": worker_id, "status": status, "now": utcnow()},
    )


async def fail_job(
    session: AsyncSession,
    *,
    job_id: str,
    worker_id: str,
    error_code: str,
    error_detail: str | None = None,
) -> None:
    """Release lease and mark job failed."""
    await session.execute(
        text(
            """
            UPDATE job
            SET status = 'failed',
                error_code = :error_code,
                error_detail = :error_detail,
                lease_owner = NULL,
                lease_expires_at = NULL,
                updated_at = :now
            WHERE id = :job_id AND lease_owner = :worker_id
            """
        ),
        {
            "job_id": job_id,
            "worker_id": worker_id,
            "error_code": error_code,
            "error_detail": error_detail,
            "now": utcnow(),
        },
    )


async def enqueue_job(
    session: AsyncSession,
    *,
    job_id: str,
    current_run_id: str | None = None,
) -> None:
    """Make a job claimable by the Postgres queue worker."""
    await session.execute(
        text(
            """
            UPDATE job
            SET status = 'uploaded',
                current_run_id = COALESCE(:run_id, current_run_id),
                lease_owner = NULL,
                lease_expires_at = NULL,
                error_code = NULL,
                error_detail = NULL,
                updated_at = :now
            WHERE id = :job_id
            """
        ),
        {"job_id": job_id, "run_id": current_run_id, "now": utcnow()},
    )
    logger.info("job_queue.enqueued", job_id=job_id, run_id=current_run_id)


async def reap_expired_leases(session: AsyncSession) -> int:
    """Requeue stalled processing jobs whose lease has expired.

    Returns number of jobs requeued.
    """
    result = await session.execute(
        text(
            """
            UPDATE job
            SET status = 'uploaded',
                lease_owner = NULL,
                lease_expires_at = NULL,
                updated_at = :now
            WHERE status = 'processing'
              AND lease_expires_at IS NOT NULL
              AND lease_expires_at < :now
            """
        ),
        {"now": utcnow()},
    )
    count = int(getattr(result, "rowcount", 0) or 0)
    if count:
        logger.warning("job_queue.reaped", count=count)
    return count


async def reap_expired_leases_on_engine(engine: AsyncEngine) -> int:
    """Open a short-lived session, reap, commit."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        count = await reap_expired_leases(session)
        await session.commit()
        return count


__all__ = [
    "ClaimedJob",
    "claim_next_job",
    "complete_job",
    "enqueue_job",
    "extend_lease",
    "fail_job",
    "reap_expired_leases",
    "reap_expired_leases_on_engine",
]
