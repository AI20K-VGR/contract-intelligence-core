"""Q&A history: the answer text next to the audit trail (Sprint 3 task 4).

``query_trace`` is the append-only audit of every query (question, state,
citations, ACL decision); a trigger forbids UPDATE/DELETE on it. The answer
is contract content, so it lives in ``query_answer`` instead — one row per
trace, written in the same transaction — and the dossier purge can delete it.
History is read by joining the two.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from contract_intelligence.shared.base import utcnow
from contract_intelligence.shared.persistence.base import Base
from contract_intelligence.shared.query_policy import QueryTraceORM

# Endpoints that produce an answer; /search returns hits, not an answer.
HISTORY_ENDPOINTS = ("query", "ask")


class QueryAnswerORM(Base):
    __tablename__ = "query_answer"

    trace_id: Mapped[str] = mapped_column(Text, ForeignKey("query_trace.id"), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    dossier_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


def record_query_answer(session: AsyncSession, trace: QueryTraceORM, answer: str) -> None:
    """Stage the answer next to its trace; the caller commits both together."""
    session.add(
        QueryAnswerORM(
            trace_id=trace.id,
            tenant_id=trace.tenant_id,
            dossier_id=trace.dossier_id,
            actor_id=trace.actor_id,
            answer=answer,
        )
    )


async def list_query_history(
    session: AsyncSession,
    *,
    tenant_id: str,
    dossier_id: str,
    actor_id: str | None,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    """Newest first. ``actor_id`` None = every asker (owner / administrator view)."""
    conditions = [
        QueryTraceORM.tenant_id == tenant_id,
        QueryTraceORM.dossier_id == dossier_id,
        QueryTraceORM.endpoint.in_(HISTORY_ENDPOINTS),
    ]
    if actor_id is not None:
        conditions.append(QueryTraceORM.actor_id == actor_id)
    total = int(
        await session.scalar(select(func.count()).select_from(QueryTraceORM).where(*conditions))
        or 0
    )
    rows = await session.execute(
        select(QueryTraceORM, QueryAnswerORM.answer)
        .outerjoin(QueryAnswerORM, QueryAnswerORM.trace_id == QueryTraceORM.id)
        .where(*conditions)
        .order_by(QueryTraceORM.created_at.desc(), QueryTraceORM.id.desc())
        .limit(limit)
        .offset(offset)
    )
    items = [
        {
            "trace_id": trace.id,
            "endpoint": trace.endpoint,
            "actor_id": trace.actor_id,
            "question": trace.query,
            "answer": answer,
            "state": trace.state,
            "citations": json.loads(trace.citations or "[]"),
            "error_code": trace.error_code,
            "created_at": trace.created_at,
        }
        for trace, answer in rows.all()
    ]
    return items, total


__all__ = [
    "HISTORY_ENDPOINTS",
    "QueryAnswerORM",
    "list_query_history",
    "record_query_answer",
]
