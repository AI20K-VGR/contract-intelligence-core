"""SQLAlchemy ORM models cho Approval bounded context.

Tables (DOC-04b/DOC-04c):
    dossier_approval     — Snapshot khi ký duyệt nội bộ
    external_approval    — Token + callback cho phê duyệt ngoài
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from contract_intelligence.shared.persistence.base import Base


class DossierApprovalORM(Base):
    """Snapshot ký duyệt nội bộ — bất biến sau khi tạo."""

    __tablename__ = "dossier_approval"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    dossier_id: Mapped[str] = mapped_column(
        Text, ForeignKey("dossier.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    approved_by: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("uq_dossier_approval_dossier", "dossier_id", unique=True),
    )


class ExternalApprovalORM(Base):
    """External approval token — gửi cho đối tác / lãnh đạo ngoài."""

    __tablename__ = "external_approval"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    dossier_id: Mapped[str] = mapped_column(
        Text, ForeignKey("dossier.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    recipient_email: Mapped[str] = mapped_column(Text, nullable=False)
    recipient_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="pending"
    )  # pending | approved | rejected | expired
    callback_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    response_payload: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["DossierApprovalORM", "ExternalApprovalORM"]
