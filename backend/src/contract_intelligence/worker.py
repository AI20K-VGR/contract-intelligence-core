"""Kafka consumer worker — reacts to ``dossier.uploaded`` and dispatches AI1 OCR.

Run as a standalone process::

    uv run python -m contract_intelligence.worker
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from aiokafka import AIOKafkaConsumer
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from contract_intelligence.config.settings import get_settings
from contract_intelligence.contract.domain.entities.document import DocumentRole
from contract_intelligence.contract.domain.entities.job import JobStatus
from contract_intelligence.contract.infrastructure.persistence.orm import (
    DocumentORM,
    DossierORM,
    JobORM,
)
from contract_intelligence.infrastructure.ai_adapters import submit_to_ai1
from contract_intelligence.shared.base import new_ulid, utcnow

logger = structlog.get_logger(__name__)

DOSSIER_EVENTS_TOPIC = "dossier_events"
CONSUMER_GROUP = "ci-backend-orchestrator"


async def _mark_processing(session: AsyncSession, dossier_id: str) -> str | None:
    """Set dossier + latest job to PROCESSING. Returns ``current_run_id`` or a new one."""
    now = utcnow()
    await session.execute(
        update(DossierORM)
        .where(DossierORM.id == dossier_id)
        .values(status=JobStatus.PROCESSING.value, updated_at=now)
    )

    result = await session.execute(
        select(JobORM)
        .where(JobORM.dossier_id == dossier_id)
        .order_by(JobORM.created_at.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if job is None:
        logger.warning("worker.job_missing", dossier_id=dossier_id)
        return None

    run_id = job.current_run_id or new_ulid("run_")
    job.status = JobStatus.PROCESSING.value
    job.current_run_id = run_id
    job.updated_at = now
    await session.flush()
    return run_id


async def _load_contract_document(session: AsyncSession, dossier_id: str) -> DocumentORM | None:
    """Return the CONTRACT-role document for ``dossier_id`` (order_index=0 preferred)."""
    result = await session.execute(
        select(DocumentORM)
        .where(
            DocumentORM.dossier_id == dossier_id,
            DocumentORM.role == DocumentRole.CONTRACT.value,
        )
        .order_by(DocumentORM.order_index.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def handle_dossier_uploaded(
    session: AsyncSession,
    event: dict[str, Any],
) -> dict[str, Any] | None:
    """Process a ``dossier.uploaded`` event: mark PROCESSING then submit to AI1."""
    dossier_id = str(event.get("dossier_id") or "")
    if not dossier_id:
        logger.error("worker.dossier_uploaded.missing_dossier_id", event=event)
        return None

    run_id = await _mark_processing(session, dossier_id)
    await session.commit()

    document = await _load_contract_document(session, dossier_id)
    if document is None:
        logger.error("worker.dossier_uploaded.no_contract_document", dossier_id=dossier_id)
        return None

    file_ref = str(event.get("file_path") or document.blob_uri)
    ai1_payload: dict[str, Any] = {
        "dossier_id": dossier_id,
        "document_id": document.id,
        "file_ref": file_ref,
        "ocr_profile": str(event.get("ocr_profile") or "standard"),
        "run_id": run_id or new_ulid("run_"),
    }

    logger.info(
        "worker.dossier_uploaded.submit_ai1",
        dossier_id=dossier_id,
        document_id=document.id,
        run_id=ai1_payload["run_id"],
    )
    return await submit_to_ai1(ai1_payload)


async def handle_event(session: AsyncSession, message: dict[str, Any]) -> None:
    """Route a deserialized Kafka message to the appropriate handler."""
    event_type = message.get("event")
    if event_type == "dossier.uploaded":
        await handle_dossier_uploaded(session, message)
        return
    logger.debug("worker.event.ignored", event_type=event_type)


async def run_consumer() -> None:
    """Start the Kafka consumer loop for ``dossier_events``."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    consumer = AIOKafkaConsumer(
        DOSSIER_EVENTS_TOPIC,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=CONSUMER_GROUP,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    await consumer.start()
    logger.info(
        "worker.started",
        topic=DOSSIER_EVENTS_TOPIC,
        group_id=CONSUMER_GROUP,
        bootstrap_servers=settings.kafka_bootstrap_servers,
    )
    try:
        async for record in consumer:
            message = record.value
            if not isinstance(message, dict):
                logger.warning("worker.invalid_message", raw=message)
                continue
            try:
                async with session_factory() as session:
                    await handle_event(session, message)
            except Exception:
                logger.exception(
                    "worker.event_failed",
                    event_type=message.get("event"),
                    dossier_id=message.get("dossier_id"),
                )
    finally:
        await consumer.stop()
        await engine.dispose()
        logger.info("worker.stopped")


def main() -> None:
    """CLI entrypoint."""
    asyncio.run(run_consumer())


if __name__ == "__main__":
    main()
