"""Kafka orchestrator — dossier → AI1 OCR → AI2 IDP (DOC-05d / DOC-05e).

Run as a standalone process::

    uv run python -m contract_intelligence.worker

See ``docs/DOC-05d-kafka-ai1-ocr-contract.md`` and
``docs/DOC-05e-kafka-ai2-idp-contract.md``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
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
from contract_intelligence.infrastructure import messaging, storage
from contract_intelligence.shared.ai.ai1_adapter import adapt_ai1_snapshot_result
from contract_intelligence.shared.ai.ai2_handoff import (
    EVENT_AI2_IDP_COMPLETED,
    EVENT_AI2_IDP_FAILED,
    apply_ai2_wire_result,
    extract_ai1_v1_snapshot,
    publish_ai2_idp_after_ocr,
)
from contract_intelligence.shared.ai.persistence import persist_ai1_snapshot
from contract_intelligence.shared.base import new_ulid

logger = structlog.get_logger(__name__)

SCHEMA_VERSION = "ci.kafka.v1"
EVENT_OCR_COMMAND = "ai1.ocr.command"
EVENT_OCR_COMPLETED = "ai1.ocr.completed"
EVENT_OCR_FAILED = "ai1.ocr.failed"

# Idempotency for result events (event_id / job_id).
_seen_result_ids: set[str] = set()
_seen_ai2_result_ids: set[str] = set()


def _utcnow_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _task_id_from(document_id: str) -> int:
    return int(hashlib.sha256(document_id.encode()).hexdigest()[:8], 16) % 10_000_000


async def _mark_processing(session: AsyncSession, dossier_id: str) -> str | None:
    """Set dossier + latest job to PROCESSING. Returns ``current_run_id``."""
    now = datetime.now(tz=UTC)
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


async def _mark_status(
    session: AsyncSession,
    *,
    status_value: str,
    dossier_id: str | None,
    run_id: str | None,
    error_code: str | None = None,
    error_detail: str | None = None,
) -> None:
    now = datetime.now(tz=UTC)
    job: JobORM | None = None
    if run_id:
        result = await session.execute(
            select(JobORM).where(JobORM.current_run_id == run_id).limit(1)
        )
        job = result.scalar_one_or_none()
    if job is None and dossier_id:
        result = await session.execute(
            select(JobORM)
            .where(JobORM.dossier_id == dossier_id)
            .order_by(JobORM.created_at.desc())
            .limit(1)
        )
        job = result.scalar_one_or_none()
    if job is None:
        logger.warning(
            "worker.status_job_missing",
            dossier_id=dossier_id,
            run_id=run_id,
            status=status_value,
        )
        return
    job.status = status_value
    job.updated_at = now
    if error_code is not None:
        job.error_code = error_code
    if error_detail is not None:
        job.error_detail = error_detail
    resolved = job.dossier_id
    await session.execute(
        update(DossierORM)
        .where(DossierORM.id == resolved)
        .values(status=status_value, updated_at=now)
    )
    await session.flush()


async def _load_contract_document(session: AsyncSession, dossier_id: str) -> DocumentORM | None:
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


async def _build_ocr_command_payload(
    *,
    document: DocumentORM,
    dossier: DossierORM,
    run_id: str,
) -> dict[str, Any]:
    settings = get_settings()
    page_count = int(document.page_count or 0)
    pages = list(range(1, page_count + 1)) if page_count > 0 else [1]

    if not document.blob_uri:
        msg = f"Document {document.id} has no blob_uri"
        raise ValueError(msg)
    get_url = await storage.generate_presigned_get_url(document.blob_uri)
    put_urls: dict[str, str] = {}
    for page_no in pages:
        put_key = f"{document.id}/page-{page_no:03d}.png"
        put_urls[str(page_no)] = await storage.generate_presigned_put_url(key=put_key)

    task_id = _task_id_from(document.id)
    engine = (settings.ai1_ocr_engine or "mistral").strip().lower()
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": new_ulid("evt_"),
        "event_type": EVENT_OCR_COMMAND,
        "occurred_at": _utcnow_iso(),
        "trace_id": run_id,
        "tenant_id": document.tenant_id or dossier.tenant_id,
        "correlation": {
            "dossier_id": dossier.id,
            "document_id": document.id,
            "task_id": task_id,
            "attempt_id": 1,
            "run_id": run_id,
        },
        "payload": {
            "task_id": task_id,
            "attempt_id": 1,
            "tenant_id": document.tenant_id or dossier.tenant_id,
            "document_id": document.id,
            "source_blob_get_url": get_url,
            "source_sha256": document.sha256,
            "pages_to_process": pages,
            "render_target": {
                "dpi": 150,
                "format": "PNG",
                "presigned_put_urls": put_urls,
            },
            "options": {
                "engine": engine,
                "dpi": 150,
                "language": document.lang_detected or "vi",
                "document_role": document.role.lower(),
                "filename": document.filename,
            },
        },
    }


async def handle_dossier_uploaded(session: AsyncSession, event: dict[str, Any]) -> None:
    """Process ``dossier.uploaded``: mark PROCESSING and publish AI1 OCR command."""
    settings = get_settings()
    dossier_id = str(event.get("dossier_id") or "")
    if not dossier_id:
        logger.error("worker.dossier_uploaded.missing_dossier_id", event=event)
        return

    run_id = await _mark_processing(session, dossier_id)
    await session.commit()

    document = await _load_contract_document(session, dossier_id)
    if document is None:
        logger.error("worker.dossier_uploaded.no_contract_document", dossier_id=dossier_id)
        return

    dossier = await session.get(DossierORM, dossier_id)
    if dossier is None:
        logger.error("worker.dossier_uploaded.dossier_missing", dossier_id=dossier_id)
        return

    envelope = await _build_ocr_command_payload(
        document=document,
        dossier=dossier,
        run_id=run_id or new_ulid("run_"),
    )
    await messaging.publish_event(
        settings.kafka_ai1_ocr_commands_topic,
        envelope,
        key=document.id,
    )
    logger.info(
        "worker.dossier_uploaded.ocr_command_published",
        dossier_id=dossier_id,
        document_id=document.id,
        run_id=envelope["correlation"]["run_id"],
        event_id=envelope["event_id"],
    )


async def handle_ai1_result(session: AsyncSession, message: dict[str, Any]) -> None:
    """Persist AI1 OCR result and update job/dossier status."""
    event_id = str(message.get("event_id") or "")
    raw_payload = message.get("payload")
    payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
    job_id = str(payload.get("job_id") or "")
    dedupe_key = event_id or job_id
    if dedupe_key and dedupe_key in _seen_result_ids:
        logger.info("worker.ai1_result.duplicate", event_id=event_id, job_id=job_id)
        return

    raw_correlation = message.get("correlation")
    correlation: dict[str, Any] = raw_correlation if isinstance(raw_correlation, dict) else {}
    dossier_id = correlation.get("dossier_id")
    run_id = correlation.get("run_id")
    tenant_id = str(message.get("tenant_id") or correlation.get("tenant_id") or "")
    event_type = message.get("event_type")

    if event_type == EVENT_OCR_FAILED or str(payload.get("status")) == "failed":
        raw_error = payload.get("error")
        error: dict[str, Any] = raw_error if isinstance(raw_error, dict) else {}
        await _mark_status(
            session,
            status_value=JobStatus.FAILED.value,
            dossier_id=str(dossier_id) if dossier_id else None,
            run_id=str(run_id) if run_id else None,
            error_code=str(error.get("code") or "AI1_OCR_FAILED"),
            error_detail=str(error.get("message") or "OCR failed"),
        )
        await session.commit()
        if dedupe_key:
            _seen_result_ids.add(dedupe_key)
        logger.warning(
            "worker.ai1_result.failed",
            dossier_id=dossier_id,
            run_id=run_id,
            error=error,
        )
        return

    if event_type not in (EVENT_OCR_COMPLETED, None) and str(payload.get("status")) != "completed":
        logger.debug("worker.ai1_result.ignored", event_type=event_type)
        return

    result = payload.get("result")
    if not isinstance(result, dict):
        logger.error("worker.ai1_result.missing_result", event_id=event_id)
        return

    if not tenant_id:
        tenant_id = "unknown"

    try:
        snapshot = adapt_ai1_snapshot_result(result)
        await persist_ai1_snapshot(
            session,
            tenant_id=tenant_id,
            snapshot=snapshot,
            run_id=str(run_id) if run_id else None,
        )
        await _mark_status(
            session,
            status_value=JobStatus.EXTRACTED.value,
            dossier_id=str(dossier_id) if dossier_id else None,
            run_id=str(run_id) if run_id else None,
        )
        await session.commit()
        if dedupe_key:
            _seen_result_ids.add(dedupe_key)
        logger.info(
            "worker.ai1_result.persisted",
            dossier_id=dossier_id,
            document_id=correlation.get("document_id"),
            run_id=run_id,
            job_id=job_id,
        )

        # DOC-05e: publish body-only AI2 IDP command (Kafka; no HTTP poll).
        raw_snapshot = extract_ai1_v1_snapshot(result)
        document_id = str(
            correlation.get("document_id")
            or (raw_snapshot.get("document_id") if raw_snapshot else "")
            or ""
        )
        if raw_snapshot and dossier_id and document_id:
            source_digest = str(raw_snapshot.get("source_digest") or "")
            task_raw = correlation.get("task_id")
            task_id: int | None = None
            if isinstance(task_raw, int):
                task_id = task_raw
            elif isinstance(task_raw, str) and task_raw.isdigit():
                task_id = int(task_raw)
            try:
                await publish_ai2_idp_after_ocr(
                    tenant_id=tenant_id,
                    dossier_id=str(dossier_id),
                    document_id=document_id,
                    run_id=str(run_id) if run_id else None,
                    snapshot=raw_snapshot,
                    source_digest=source_digest,
                    event_id=event_id or None,
                    task_id=task_id,
                )
            except Exception:
                logger.exception(
                    "worker.ai1_result.ai2_command_failed",
                    dossier_id=dossier_id,
                    run_id=run_id,
                )
        else:
            logger.warning(
                "worker.ai1_result.ai2_skipped_missing_snapshot",
                dossier_id=dossier_id,
                document_id=document_id or correlation.get("document_id"),
            )
    except Exception:
        await session.rollback()
        logger.exception(
            "worker.ai1_result.persist_failed",
            dossier_id=dossier_id,
            run_id=run_id,
        )
        raise


async def handle_dossier_event(session: AsyncSession, message: dict[str, Any]) -> None:
    event_type = message.get("event")
    if event_type == "dossier.uploaded":
        await handle_dossier_uploaded(session, message)
        return
    logger.debug("worker.event.ignored", event_type=event_type)


async def run_dossier_events_consumer(session_factory: async_sessionmaker[AsyncSession]) -> None:
    settings = get_settings()
    consumer = AIOKafkaConsumer(
        settings.kafka_dossier_events_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_orchestrator_group_id,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    await consumer.start()
    logger.info(
        "worker.dossier_events.started",
        topic=settings.kafka_dossier_events_topic,
        group_id=settings.kafka_orchestrator_group_id,
    )
    try:
        async for record in consumer:
            message = record.value
            if not isinstance(message, dict):
                logger.warning("worker.invalid_message", raw=message)
                continue
            try:
                async with session_factory() as session:
                    await handle_dossier_event(session, message)
            except Exception:
                logger.exception(
                    "worker.dossier_event_failed",
                    event_type=message.get("event"),
                    dossier_id=message.get("dossier_id"),
                )
    finally:
        await consumer.stop()


async def run_ai1_results_consumer(session_factory: async_sessionmaker[AsyncSession]) -> None:
    settings = get_settings()
    consumer = AIOKafkaConsumer(
        settings.kafka_ai1_ocr_results_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_backend_ai1_results_group_id,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        # Match broker message.max.bytes so large OCR snapshots (~1.6MB+) can be fetched.
        max_partition_fetch_bytes=10_485_760,
        fetch_max_bytes=10_485_760,
    )
    await consumer.start()
    logger.info(
        "worker.ai1_results.started",
        topic=settings.kafka_ai1_ocr_results_topic,
        group_id=settings.kafka_backend_ai1_results_group_id,
    )
    try:
        async for record in consumer:
            message = record.value
            if not isinstance(message, dict):
                logger.warning("worker.ai1_results.invalid_message", raw=message)
                continue
            try:
                async with session_factory() as session:
                    await handle_ai1_result(session, message)
            except Exception:
                logger.exception(
                    "worker.ai1_result_failed",
                    event_type=message.get("event_type"),
                    event_id=message.get("event_id"),
                )
    finally:
        await consumer.stop()


async def handle_ai2_result(session: AsyncSession, message: dict[str, Any]) -> None:
    """Persist AI2 IDP result and advance dossier to PENDING_REVIEW (DOC-05e)."""
    event_id = str(message.get("event_id") or "")
    raw_payload = message.get("payload")
    payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
    job_id = str(payload.get("job_id") or "")
    dedupe_key = event_id or job_id
    if dedupe_key and dedupe_key in _seen_ai2_result_ids:
        logger.info("worker.ai2_result.duplicate", event_id=event_id, job_id=job_id)
        return

    raw_correlation = message.get("correlation")
    correlation: dict[str, Any] = raw_correlation if isinstance(raw_correlation, dict) else {}
    dossier_id = str(correlation.get("dossier_id") or payload.get("dossier_id") or "")
    run_id = str(correlation.get("run_id") or "")
    tenant_id = str(message.get("tenant_id") or correlation.get("tenant_id") or "unknown")
    event_type = message.get("event_type")

    if not dossier_id:
        logger.error("worker.ai2_result.missing_dossier_id", event_id=event_id)
        return

    is_failed = event_type == EVENT_AI2_IDP_FAILED or str(payload.get("status") or "").upper() in {
        "FAILED",
        "CANCELLED",
    }

    if is_failed and not (
        payload.get("schema_version") == "ai2.be.processing.result.v1"
        or "result" in payload
        or "errors" in payload
    ):
        # Minimal fail payload: { error: { code, message } }
        raw_error = payload.get("error")
        error: dict[str, Any] = raw_error if isinstance(raw_error, dict) else {}
        await _mark_status(
            session,
            status_value=JobStatus.PENDING_REVIEW.value,
            dossier_id=dossier_id,
            run_id=run_id or None,
            error_code=str(error.get("code") or "AI2_IDP_FAILED"),
            error_detail=str(error.get("message") or "AI2 IDP failed"),
        )
        await session.commit()
        if dedupe_key:
            _seen_ai2_result_ids.add(dedupe_key)
        logger.warning(
            "worker.ai2_result.failed_minimal",
            dossier_id=dossier_id,
            run_id=run_id,
            error=error,
        )
        return

    if event_type not in (EVENT_AI2_IDP_COMPLETED, EVENT_AI2_IDP_FAILED, None) and not payload.get(
        "schema_version"
    ):
        logger.debug("worker.ai2_result.ignored", event_type=event_type)
        return

    wire = payload
    if wire.get("schema_version") != "ai2.be.processing.result.v1" and not is_failed:
        # Wrap bare result if producer only sent the wire object under payload.
        if isinstance(payload.get("result"), dict) and payload.get("status"):
            wire = payload
        else:
            logger.error("worker.ai2_result.invalid_wire", event_id=event_id)
            return

    try:
        summary = await apply_ai2_wire_result(
            session,
            tenant_id=tenant_id,
            dossier_id=dossier_id,
            run_id=run_id or new_ulid("run_"),
            wire=wire,
        )
        await session.commit()
        if dedupe_key:
            _seen_ai2_result_ids.add(dedupe_key)
        logger.info(
            "worker.ai2_result.persisted",
            dossier_id=dossier_id,
            run_id=run_id,
            job_id=job_id,
            event_type=event_type,
            **summary,
        )
    except Exception:
        await session.rollback()
        logger.exception(
            "worker.ai2_result.persist_failed",
            dossier_id=dossier_id,
            run_id=run_id,
        )
        raise


async def run_ai2_results_consumer(session_factory: async_sessionmaker[AsyncSession]) -> None:
    settings = get_settings()
    consumer = AIOKafkaConsumer(
        settings.kafka_ai2_idp_results_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_backend_ai2_results_group_id,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        max_partition_fetch_bytes=10_485_760,
        fetch_max_bytes=10_485_760,
    )
    await consumer.start()
    logger.info(
        "worker.ai2_results.started",
        topic=settings.kafka_ai2_idp_results_topic,
        group_id=settings.kafka_backend_ai2_results_group_id,
    )
    try:
        async for record in consumer:
            message = record.value
            if not isinstance(message, dict):
                logger.warning("worker.ai2_results.invalid_message", raw=message)
                continue
            try:
                async with session_factory() as session:
                    await handle_ai2_result(session, message)
            except Exception:
                logger.exception(
                    "worker.ai2_result_failed",
                    event_type=message.get("event_type"),
                    event_id=message.get("event_id"),
                )
    finally:
        await consumer.stop()


async def run_consumer() -> None:
    """Start producer + dossier_events, AI1 results, and AI2 results consumers."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    await messaging.start_producer()
    logger.info(
        "worker.started",
        bootstrap_servers=settings.kafka_bootstrap_servers,
        ai1_commands_topic=settings.kafka_ai1_ocr_commands_topic,
        ai1_results_topic=settings.kafka_ai1_ocr_results_topic,
        ai2_commands_topic=settings.kafka_ai2_idp_commands_topic,
        ai2_results_topic=settings.kafka_ai2_idp_results_topic,
    )
    try:
        await asyncio.gather(
            run_dossier_events_consumer(session_factory),
            run_ai1_results_consumer(session_factory),
            run_ai2_results_consumer(session_factory),
        )
    finally:
        await messaging.stop_producer()
        await engine.dispose()
        logger.info("worker.stopped")


def main() -> None:
    """CLI entrypoint."""
    asyncio.run(run_consumer())


if __name__ == "__main__":
    main()
