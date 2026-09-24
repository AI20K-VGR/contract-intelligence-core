"""Deletion ledger — evidence that a dossier was tombstoned and purged.

The row outlives the dossier. It stores ids and counts only, never contract text.
A restored backup that brings the dossier back is purged again from this ledger.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from contract_intelligence.shared.persistence.base import Base


class DeletionLedgerORM(Base):
    """One row per dossier a user asked to delete."""

    __tablename__ = "deletion_ledger"
    __table_args__ = (
        UniqueConstraint("tenant_id", "dossier_id", name="uq_deletion_ledger_dossier"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    dossier_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(Text, nullable=False)
    tombstoned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    purge_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence: Mapped[dict[str, int] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
