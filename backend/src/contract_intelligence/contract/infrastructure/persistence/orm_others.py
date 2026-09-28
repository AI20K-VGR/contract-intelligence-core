"""SQLAlchemy ORM models cho Batches & Optimization bounded context."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from contract_intelligence.shared.persistence.base import Base

# ============================================================================
# Batch
# ============================================================================


class BatchORM(Base):
    """1 lô xử lý nhiều dossier cùng lúc."""

    __tablename__ = "batch"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="running"
    )  # running | paused | cancelled | completed
    total_dossiers: Mapped[int] = mapped_column(String, nullable=False, server_default="0")
    succeeded: Mapped[int] = mapped_column(String, nullable=False, server_default="0")
    failed: Mapped[int] = mapped_column(String, nullable=False, server_default="0")
    pending_review: Mapped[int] = mapped_column(String, nullable=False, server_default="0")
    total_cost_usd: Mapped[float] = mapped_column(String, nullable=False, server_default="0.0")
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ============================================================================
# Optimization Studio (Admin)
# ============================================================================


class OptimizationCampaignORM(Base):
    __tablename__ = "optimization_campaign"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    target_metric: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft")
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OptimizationCandidateORM(Base):
    __tablename__ = "optimization_candidate"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(
        Text, ForeignKey("optimization_campaign.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    hyperparameters: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    is_promoted: Mapped[bool] = mapped_column(String, nullable=False, server_default="false")
    metrics: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OptimizationExperimentORM(Base):
    __tablename__ = "optimization_experiment"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    campaign_id: Mapped[str] = mapped_column(
        Text, ForeignKey("optimization_campaign.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("optimization_candidate.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    benchmark_set_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="queued"
    )  # queued | running | succeeded | failed
    results: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON — f1, latency, cost
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = [
    "BatchORM",
    "OptimizationCampaignORM",
    "OptimizationCandidateORM",
    "OptimizationExperimentORM",
]
