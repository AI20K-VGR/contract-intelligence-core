"""Kafka records the worker has already handled (DOC-11 §4.2 #8).

The worker commits a Kafka offset only after the handler finished, so a crash
or restart in between redelivers the record. Handlers are idempotent against
the DB, but a redelivered ``dossier.uploaded`` or AI1 result still costs work
(and AI1 money when it re-dispatches OCR). One row per handled record lets the
worker skip it outright.

The key is the message ``event_id``. ``messaging.publish_event`` gives every
backend event one; a message without one (published before that) falls back to
the Kafka coordinates, which a redelivery keeps but a recreated topic reuses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, Text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from contract_intelligence.shared.base import utcnow
from contract_intelligence.shared.persistence.base import Base


class ProcessedEventORM(Base):
    __tablename__ = "processed_event"

    consumer: Mapped[str] = mapped_column(Text, primary_key=True)
    event_key: Mapped[str] = mapped_column(Text, primary_key=True)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    partition: Mapped[int] = mapped_column(Integer, nullable=False)
    offset: Mapped[int] = mapped_column(Integer, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )


def event_key(record: Any, message: dict[str, Any]) -> str:
    """``event_id`` if the message has one, else ``topic:partition:offset``."""
    event_id = message.get("event_id")
    if isinstance(event_id, str) and event_id:
        return event_id
    return f"{record.topic}:{record.partition}:{record.offset}"


async def already_processed(session: AsyncSession, consumer: str, key: str) -> bool:
    found = await session.scalar(
        select(ProcessedEventORM.event_key).where(
            ProcessedEventORM.consumer == consumer, ProcessedEventORM.event_key == key
        )
    )
    return found is not None


def mark_processed(session: AsyncSession, consumer: str, key: str, record: Any) -> None:
    """Stage the marker; the caller commits it."""
    session.add(
        ProcessedEventORM(
            consumer=consumer,
            event_key=key,
            topic=str(record.topic),
            partition=int(record.partition),
            offset=int(record.offset),
        )
    )


__all__ = ["ProcessedEventORM", "already_processed", "event_key", "mark_processed"]
