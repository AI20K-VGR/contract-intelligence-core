"""SQLAlchemy ORM models cho Conflict bounded context.

Tables (DOC-04b/DOC-04c):
    finding       — 1 phát hiện xung đột giữa contract & annex
    finding_side  — 2 phía (side_a / side_b) của finding
    annex_link    — link phụ lục với hợp đồng chính
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from contract_intelligence.shared.persistence.base import Base


class FindingORM(Base):
    """ORM cho bảng ``finding``."""

    __tablename__ = "finding"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    dossier_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    run_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    finding_type: Mapped[str] = mapped_column(Text, nullable=False)  # structured | semantic
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    key_or_topic: Mapped[str] = mapped_column(Text, nullable=False)
    disposition: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(String, nullable=False, server_default="0.0")
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    trace_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FindingSideORM(Base):
    """ORM cho bảng ``finding_side``."""

    __tablename__ = "finding_side"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    finding_id: Mapped[str] = mapped_column(
        Text, ForeignKey("finding.id", ondelete="CASCADE"), nullable=False, index=True
    )
    side: Mapped[str] = mapped_column(Text, nullable=False)  # a | b
    document_id: Mapped[str] = mapped_column(Text, nullable=False)
    fact_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    clause_node_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    citation_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON

    __table_args__ = (
        Index("uq_finding_side_finding_side", "finding_id", "side", unique=True),
    )


class AnnexLinkORM(Base):
    """ORM cho bảng ``annex_link``."""

    __tablename__ = "annex_link"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    dossier_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    annex_document_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    contract_document_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    score: Mapped[float] = mapped_column(String, nullable=False)
    annex_sequence: Mapped[int] = mapped_column(String, nullable=False, server_default="1")
    effective_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)  # linked | candidate | rejected
    citation_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["AnnexLinkORM", "FindingORM", "FindingSideORM"]
