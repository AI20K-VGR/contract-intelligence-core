"""Dossiers waiting for the caller's review (GET /review-queue).

Read-only. Every dossier goes through ``shared.acl.dossier_access_decision``
with ``AclAction.REVIEW_MUTATE``; no access rule lives here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM
from contract_intelligence.review.application.dtos.review_dtos import ReviewQueueEntryDTO
from contract_intelligence.review.infrastructure.persistence.orm import ReviewItemORM
from contract_intelligence.shared.acl import AclAction, dossier_access_decision
from contract_intelligence.shared.auth import AuthenticatedUser

# Same meaning of "open" as the per-dossier queue and the dossier's review counts.
_OPEN_STATUSES = ("open", "awaiting_evidence")


def _count(condition: Any) -> Any:
    return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)


def _can_review(
    user: AuthenticatedUser, dossier: DossierORM, metadata: dict[str, Any], now: datetime
) -> bool:
    return dossier_access_decision(
        action=AclAction.REVIEW_MUTATE,
        principal=user,
        dossier_id=dossier.id,
        dossier_tenant_id=dossier.tenant_id,
        metadata=metadata,
        now=now,
    )


def _grant_expiry(
    user: AuthenticatedUser, dossier: DossierORM, metadata: dict[str, Any], now: datetime
) -> datetime | None:
    """When the caller's review access ends; None for the owner or an open-ended grant.

    Each grant is asked on its own through the ACL seam, so matching and
    liveness stay defined in one place. With several usable grants the access
    lasts until the latest one ends.
    """
    if metadata.get("created_by") == user.user_id:
        return None
    latest: datetime | None = None
    shared_with = metadata.get("shared_with")
    for grant in shared_with if isinstance(shared_with, list) else []:
        if not isinstance(grant, dict):
            continue
        if not _can_review(user, dossier, {**metadata, "shared_with": [grant]}, now):
            continue
        raw = grant.get("expires_at")
        if raw in (None, ""):
            return None
        moment = datetime.fromisoformat(str(raw))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        if latest is None or moment > latest:
            latest = moment
    return latest


async def load_review_queue(
    session: AsyncSession,
    user: AuthenticatedUser,
    *,
    limit: int,
    offset: int,
    now: datetime | None = None,
) -> tuple[list[ReviewQueueEntryDTO], int]:
    """Dossiers the caller may review that still have open items, P1 first."""
    moment = now or datetime.now(tz=UTC)
    counts = (
        select(
            ReviewItemORM.dossier_id.label("dossier_id"),
            func.count().label("open_items"),
            _count(ReviewItemORM.target_type == "finding").label("conflicts"),
            _count(ReviewItemORM.priority == "P1").label("p1"),
            _count(ReviewItemORM.priority == "P2").label("p2"),
            _count(ReviewItemORM.priority == "P3").label("p3"),
        )
        .where(
            ReviewItemORM.tenant_id == user.tenant_id,
            ReviewItemORM.status.in_(_OPEN_STATUSES),
        )
        .group_by(ReviewItemORM.dossier_id)
        .subquery()
    )
    rows = (
        await session.execute(
            select(DossierORM, counts)
            .join(counts, counts.c.dossier_id == DossierORM.id)
            .where(DossierORM.tenant_id == user.tenant_id, DossierORM.deleted_at.is_(None))
        )
    ).all()

    entries: list[ReviewQueueEntryDTO] = []
    for row in rows:
        dossier: DossierORM = row[0]
        metadata = dossier.metadata_json if isinstance(dossier.metadata_json, dict) else {}
        if not _can_review(user, dossier, metadata, moment):
            continue
        entries.append(
            ReviewQueueEntryDTO(
                dossier_id=dossier.id,
                dossier_name=dossier.name,
                dossier_status=dossier.status,
                created_at=dossier.created_at,
                is_owner=metadata.get("created_by") == user.user_id,
                grant_expires_at=_grant_expiry(user, dossier, metadata, moment),
                open_review_items=int(row.open_items),
                pending_conflicts=int(row.conflicts),
                p1=int(row.p1),
                p2=int(row.p2),
                p3=int(row.p3),
            )
        )
    # Dossiers with more P1 items first; among equals, the one waiting longest.
    entries.sort(key=lambda entry: (-entry.p1, entry.created_at, entry.dossier_id))
    return entries[offset : offset + limit], len(entries)
