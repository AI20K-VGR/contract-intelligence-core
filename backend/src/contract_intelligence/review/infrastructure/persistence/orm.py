"""SQLAlchemy ORM models cho Review bounded context.

Tables (DOC-04b/DOC-04c):
    review_item     — 1 item trong hàng đợi reviewer (với version tăng dần)
    review_action   — append-only audit trail (lịch sử thao tác)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from contract_intelligence.shared.persistence.base import Base


class ReviewItemORM(Base):
    """1 item trong hàng đợi reviewer.

    Optimistic concurrency: ``version`` tăng mỗi khi review_action được ghi
    (P0-05 theo DOC-04c). Conflict detection qua base_version.
    """

    __tablename__ = "review_item"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    dossier_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(Text, nullable=False, server_default="P3")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    source_trace_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_observation_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_review_item_priority", "tenant_id", "priority", "status"),
    )


class ReviewActionORM(Base):
    """Append-only audit log — không bao giờ UPDATE / DELETE."""

    __tablename__ = "review_action"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    review_item_id: Mapped[str] = mapped_column(
        Text, ForeignKey("review_item.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    base_version: Mapped[int] = mapped_column(Integer, nullable=False)
    corrected_value: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    corrected_bbox: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["ReviewActionORM", "ReviewItemORM"]
