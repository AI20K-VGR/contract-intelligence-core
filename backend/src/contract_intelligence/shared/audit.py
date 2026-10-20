"""Append-only audit trail for pipeline state transitions.

Every Job/Dossier status change driven by the AI1/AI2 control plane writes one
``audit_event`` row in the same transaction as the change itself.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from contract_intelligence.shared.base import new_ulid, utcnow
from contract_intelligence.shared.persistence.base import Base

SYSTEM_WORKER = "system:worker"


class AuditEventORM(Base):
    __tablename__ = "audit_event"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    dossier_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    from_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


def add_audit_event(
    session: AsyncSession,
    *,
    tenant_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    actor_id: str = SYSTEM_WORKER,
    dossier_id: str | None = None,
    run_id: str | None = None,
    from_state: str | None = None,
    to_state: str | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditEventORM:
    """Stage one audit row on ``session``; the caller owns commit/rollback."""
    row = AuditEventORM(
        id=new_ulid("aud_"),
        tenant_id=tenant_id or "unknown",
        occurred_at=utcnow(),
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        dossier_id=dossier_id,
        run_id=run_id,
        from_state=from_state,
        to_state=to_state,
        detail=json.dumps(detail, ensure_ascii=False, sort_keys=True) if detail else None,
    )
    session.add(row)
    return row


__all__ = ["SYSTEM_WORKER", "AuditEventORM", "add_audit_event"]
