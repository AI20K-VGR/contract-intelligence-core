"""SQLAlchemy ORM models cho Re-OCR bounded context."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from contract_intelligence.shared.persistence.base import Base


class ReOcrRequestORM(Base):
    """Yêu cầu chạy lại OCR cho 1+ trang."""

    __tablename__ = "reocr_request"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(
        Text, ForeignKey("document.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_ids: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="queued"
    )  # queued | running | succeeded | failed
    job_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_reocr_doc_status", "document_id", "status"),
    )


__all__ = ["ReOcrRequestORM"]
