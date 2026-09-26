"""Tenant activity feed and storage usage for the admin overview.

Historical rows come from tables that already record the fact (dossier,
document, review, approval, manifest, pipeline). Invites, lock, unlock,
role change, and login are appended to ``activity_event`` with the admin
who performed them. A member row is not an invite: only an administrator
can add someone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Text, case, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.schema import Table

from contract_intelligence.contract.infrastructure.persistence.orm import (
    DocumentORM,
    DossierORM,
    ManifestORM,
)
from contract_intelligence.extraction.infrastructure.persistence.orm import PipelineRunORM
from contract_intelligence.identity.infrastructure.persistence.orm import AppUserORM
from contract_intelligence.review.infrastructure.persistence.orm import (
    ReviewActionORM,
    ReviewItemORM,
)
from contract_intelligence.review.infrastructure.persistence.orm_approval import DossierApprovalORM
from contract_intelligence.shared.base import new_ulid, utcnow
from contract_intelligence.shared.persistence.base import Base


def _blank() -> Any:
    return literal(None, type_=Text())


def _as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; the feed contract is timezone-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class ActivityEventORM(Base):
    """Append-only events that are not already a row in another table."""

    __tablename__ = "activity_event"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)


@dataclass(frozen=True)
class ActivityEvent:
    id: str
    occurred_at: datetime
    actor_display_name: str | None
    title: str
    detail: str | None


@dataclass(frozen=True)
class ActivityPage:
    items: list[ActivityEvent]
    total: int


@dataclass(frozen=True)
class StorageUsage:
    used_bytes: int
    quota_bytes: None = None


def _actor_email(actor_id_column: object) -> Any:
    """Email for a user id, ``usr_<sub>`` id, or Keycloak sub stored on another row."""
    return (
        select(AppUserORM.email)
        .where(
            or_(
                AppUserORM.id == actor_id_column,
                AppUserORM.keycloak_sub == actor_id_column,
                AppUserORM.id == func.concat("usr_", actor_id_column),
                AppUserORM.keycloak_sub == func.replace(actor_id_column, "usr_", ""),
            )
        )
        .limit(1)
        .scalar_subquery()
    )


def _creator_email() -> Any:
    """Email of the user id saved on the dossier when it was created."""
    return _actor_email(DossierORM.metadata_json["created_by"].as_string())


def _sources(tenant_id: str) -> Any:
    dossier = select(
        func.concat("dossier:", DossierORM.id).label("id"),
        DossierORM.created_at.label("occurred_at"),
        _creator_email().label("actor_display_name"),
        func.concat("Tạo hồ sơ ", DossierORM.name).label("title"),
        _blank().label("detail"),
    ).where(
        DossierORM.tenant_id == tenant_id,
        DossierORM.deleted_at.is_(None),
    )

    document = (
        select(
            func.concat("document:", DocumentORM.id).label("id"),
            DocumentORM.created_at.label("occurred_at"),
            _creator_email().label("actor_display_name"),
            func.concat("Tải lên ", DocumentORM.filename).label("title"),
            func.concat("Hồ sơ ", DossierORM.name).label("detail"),
        )
        .join(DossierORM, DossierORM.id == DocumentORM.dossier_id)
        .where(
            DocumentORM.tenant_id == tenant_id,
            DossierORM.deleted_at.is_(None),
        )
    )

    review_title = case(
        (ReviewActionORM.action == "confirm", "Xác nhận mục rà soát"),
        (ReviewActionORM.action == "correct", "Sửa nội dung rà soát"),
        (ReviewActionORM.action == "reject", "Từ chối mục rà soát"),
        (ReviewActionORM.action == "needs_more_evidence", "Yêu cầu thêm căn cứ"),
        else_="Cập nhật rà soát",
    )
    review = (
        select(
            func.concat("review:", ReviewActionORM.id).label("id"),
            ReviewActionORM.created_at.label("occurred_at"),
            func.coalesce(
                _actor_email(ReviewActionORM.reviewer_id),
                _creator_email(),
            ).label("actor_display_name"),
            review_title.label("title"),
            func.concat("Hồ sơ ", DossierORM.name).label("detail"),
        )
        .join(ReviewItemORM, ReviewItemORM.id == ReviewActionORM.review_item_id)
        .outerjoin(DossierORM, DossierORM.id == ReviewItemORM.dossier_id)
        .where(ReviewActionORM.tenant_id == tenant_id)
    )

    approval = (
        select(
            func.concat("approval:", DossierApprovalORM.id).label("id"),
            DossierApprovalORM.approved_at.label("occurred_at"),
            _actor_email(DossierApprovalORM.approved_by).label("actor_display_name"),
            func.concat("Phê duyệt hồ sơ ", DossierORM.name).label("title"),
            _blank().label("detail"),
        )
        .join(DossierORM, DossierORM.id == DossierApprovalORM.dossier_id)
        .where(DossierApprovalORM.tenant_id == tenant_id)
    )

    manifest = (
        select(
            func.concat("manifest:", ManifestORM.id).label("id"),
            ManifestORM.confirmed_at.label("occurred_at"),
            _actor_email(ManifestORM.confirmed_by).label("actor_display_name"),
            literal("Xác nhận cấu trúc hồ sơ", type_=Text()).label("title"),
            func.concat("Hồ sơ ", DossierORM.name).label("detail"),
        )
        .join(DossierORM, DossierORM.id == ManifestORM.dossier_id)
        .where(
            ManifestORM.tenant_id == tenant_id,
            ManifestORM.confirmed_at.is_not(None),
        )
    )

    pipeline_title = case(
        (PipelineRunORM.status == "succeeded", "Phân tích hồ sơ hoàn tất"),
        else_="Phân tích hồ sơ thất bại",
    )
    pipeline = (
        select(
            func.concat("run:", PipelineRunORM.id).label("id"),
            PipelineRunORM.finished_at.label("occurred_at"),
            _creator_email().label("actor_display_name"),
            pipeline_title.label("title"),
            func.concat("Hồ sơ ", DossierORM.name).label("detail"),
        )
        .outerjoin(DossierORM, DossierORM.id == PipelineRunORM.dossier_id)
        .where(
            PipelineRunORM.tenant_id == tenant_id,
            PipelineRunORM.finished_at.is_not(None),
            PipelineRunORM.status.in_(("succeeded", "failed")),
        )
    )

    delete_title = case(
        (DossierORM.name == "[deleted]", literal("Xóa hồ sơ", type_=Text())),
        else_=func.concat("Xóa hồ sơ ", DossierORM.name),
    )
    deletion = select(
        func.concat("deleted:", DossierORM.id).label("id"),
        DossierORM.deleted_at.label("occurred_at"),
        _actor_email(DossierORM.deleted_by).label("actor_display_name"),
        delete_title.label("title"),
        _blank().label("detail"),
    ).where(
        DossierORM.tenant_id == tenant_id,
        DossierORM.deleted_at.is_not(None),
    )

    recorded = select(
        ActivityEventORM.id.label("id"),
        ActivityEventORM.occurred_at.label("occurred_at"),
        ActivityEventORM.actor_display_name.label("actor_display_name"),
        ActivityEventORM.title.label("title"),
        ActivityEventORM.detail.label("detail"),
    ).where(
        ActivityEventORM.tenant_id == tenant_id,
        ~ActivityEventORM.kind.like("dossier.deleted:%"),
    )

    return union_all(
        dossier,
        document,
        review,
        approval,
        manifest,
        pipeline,
        deletion,
        recorded,
    )


async def ensure_activity_table(session: AsyncSession) -> None:
    """Create ``activity_event`` when the image's Alembic copy is still behind."""
    connection = await session.connection()
    table = ActivityEventORM.__table__
    assert isinstance(table, Table)
    await connection.run_sync(table.create, checkfirst=True)


async def record_activity(
    session: AsyncSession,
    *,
    tenant_id: str,
    title: str,
    actor_display_name: str | None,
    detail: str | None = None,
    kind: str,
) -> None:
    """Append one overview event. Caller owns the transaction."""
    await ensure_activity_table(session)
    session.add(
        ActivityEventORM(
            id=new_ulid("act_"),
            tenant_id=tenant_id,
            occurred_at=utcnow(),
            actor_display_name=actor_display_name,
            title=title,
            detail=detail,
            kind=kind,
        )
    )
    await session.flush()


async def list_activity(
    session: AsyncSession,
    *,
    tenant_id: str,
    limit: int,
    offset: int,
    actors: list[str] | None = None,
) -> ActivityPage:
    """Newest tenant events. ``actors`` limits the feed to those names."""
    await ensure_activity_table(session)
    events = _sources(tenant_id).subquery("activity")
    actor = func.trim(events.c.actor_display_name)
    clauses = [actor.is_not(None), func.length(actor) > 0]
    if actors is not None:
        wanted = [name.strip().lower() for name in actors if name and name.strip()]
        clauses.append(func.lower(actor).in_(wanted or [""]))
    visible = select(events).where(*clauses).subquery("activity_with_actor")
    total = await session.scalar(select(func.count()).select_from(visible))
    rows = (
        await session.execute(
            select(visible).order_by(visible.c.occurred_at.desc()).limit(limit).offset(offset)
        )
    ).all()
    items = [
        ActivityEvent(
            id=str(row.id),
            occurred_at=_as_utc(row.occurred_at),
            actor_display_name=row.actor_display_name,
            title=str(row.title),
            detail=row.detail,
        )
        for row in rows
    ]
    return ActivityPage(items=items, total=int(total or 0))


async def storage_usage(session: AsyncSession, *, tenant_id: str) -> StorageUsage:
    """Bytes stored for the tenant. No quota is configured yet."""
    used = await session.scalar(
        select(func.coalesce(func.sum(DocumentORM.file_size_bytes), 0)).where(
            DocumentORM.tenant_id == tenant_id
        )
    )
    return StorageUsage(used_bytes=int(used or 0))
