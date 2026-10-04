"""Durable, secret-safe receipts for cross-service E2E diagnostics."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from sqlalchemy import JSON, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from contract_intelligence.shared.persistence.base import Base


class ServiceLogEventORM(Base):
    """One normalized log line emitted by Backend, AI2, or Frontend."""

    __tablename__ = "service_log_event"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    service: Mapped[Literal["backend", "ai2", "frontend"]] = mapped_column(
        Text, nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(Text, nullable=False, default="docker")
    level: Mapped[str] = mapped_column(Text, nullable=False, default="INFO")
    event: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    dossier_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    job_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


__all__ = ["ServiceLogEventORM"]
