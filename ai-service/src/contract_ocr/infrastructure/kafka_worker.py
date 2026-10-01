"""Kafka worker — consume AI1 OCR commands, run existing OCR, publish results.

Run::

    uv run --extra kafka python -m contract_ocr.infrastructure.kafka_worker

See ``docs/DOC-05d-kafka-ai1-ocr-contract.md``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from contract_ocr.infrastructure.backend_ocr_job import (
    BackendOcrJobRequest,
    align_pages_to_pdf,
    get_backend_job,
    new_backend_job,
    run_backend_ocr,
)
from contract_ocr.infrastructure.observability import flush_langfuse

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "ci.kafka.v1"
EVENT_COMMAND = "ai1.ocr.command"
EVENT_COMPLETED = "ai1.ocr.completed"
EVENT_FAILED = "ai1.ocr.failed"

# The producer's cap, and the largest result still sent inline when the upload to
# the backend's result_target fails (an inline OCR result costs ~71 KiB per page).
MAX_MESSAGE_BYTES = 10_485_760  # 10 MiB
# Room left in a message for the envelope around an inline result.
_ENVELOPE_ALLOWANCE = 64 * 1024

# In-process idempotency for at-least-once redelivery (event_id → result envelope).
_processed: dict[str, dict[str, Any]] = {}


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip() or default


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _build_result_envelope(
    *,
    event_type: str,
    command: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": command.get("event_id") or f"evt_result_{payload.get('job_id', '')}",
        "event_type": event_type,
        "occurred_at": _now(),
        "trace_id": command.get("trace_id"),
        "tenant_id": command.get("tenant_id"),
        "correlation": command.get("correlation") or {},
        "payload": payload,
    }


def _encode(value: Any) -> bytes:
    # UTF-8, not \uXXXX escapes: Vietnamese text would take ~20% more bytes.
    return json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")


def _put_result(put_url: str, body: bytes, content_type: str) -> None:
    request = Request(put_url, data=body, method="PUT", headers={"Content-Type": content_type})
    with urlopen(request, timeout=120):  # noqa: S310 - backend supplies a presigned URL
        pass


def _deliver_result(
    result: dict[str, Any], result_target: Any
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    """Upload ``result`` to the backend's target (DOC-05d); return (inline, ref, error).

    Without a target the result stays inline. When the upload fails, a result
    that still fits a Kafka message is sent inline; a larger one fails the job
    here instead of breaking on the producer's size limit.
    """
    if not isinstance(result_target, dict):
        return result, None, None
    put_url = str(result_target.get("put_url") or "")
    uri = str(result_target.get("uri") or "")
    if not put_url or not uri:
        return result, None, None
    body = _encode(result)
    try:
        _put_result(put_url, body, str(result_target.get("content_type") or "application/json"))
    except (OSError, URLError) as exc:
        logger.warning(
            "ai1.kafka.result_upload_failed bytes=%d error=%s", len(body), type(exc).__name__
        )
        if len(body) <= MAX_MESSAGE_BYTES - _ENVELOPE_ALLOWANCE:
            return result, None, None
        return (
            None,
            None,
            {
                "code": "AI1_RESULT_UPLOAD_FAILED",
                "message": f"result of {len(body)} bytes could not be uploaded: {exc}"[:500],
            },
        )
    ref = {"uri": uri, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
    return None, ref, None


def _handle_command(message: dict[str, Any]) -> dict[str, Any]:
    """Synchronously process one OCR command; return the result envelope."""
    event_id = str(message.get("event_id") or "")
    if event_id and event_id in _processed:
        logger.info("ai1.kafka.duplicate_event", extra={"event_id": event_id})
        return _processed[event_id]

    if message.get("event_type") != EVENT_COMMAND:
        raise ValueError(f"unexpected event_type: {message.get('event_type')!r}")

    raw_payload = message.get("payload")
    if not isinstance(raw_payload, dict):
        raise ValueError("command payload must be an object")

    request = BackendOcrJobRequest.model_validate(raw_payload)
    request = align_pages_to_pdf(request)
    job_id, _job = new_backend_job("ocr")
    run_backend_ocr(
        job_id,
        request,
        trace_seed=str(message.get("trace_id") or event_id or job_id),
    )
    job = get_backend_job(job_id)
    if job is None:
        raise RuntimeError(f"OCR job disappeared: {job_id}")

    status = str(job.get("status") or "failed")
    engine = str(request.options.get("engine", "pymupdf"))
    pages = len(request.pages_to_process)
    result, result_ref, error = job.get("result"), None, job.get("error")
    if status == "completed" and isinstance(result, dict):
        result, result_ref, upload_error = _deliver_result(
            result, request.options.get("result_target")
        )
        if upload_error is not None:
            status, error = "failed", upload_error
    result_payload = {
        "job_id": job["job_id"],
        "kind": job.get("kind", "ocr"),
        "status": status,
        "progress_pct": job.get("progress_pct", 100),
        "current_stage": job.get("current_stage"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        "finished_at": job.get("finished_at"),
        "result": result,
        "error": error,
        "usage": {"engine": engine, "pages": pages},
    }
    if result_ref is not None:
        result_payload["result_ref"] = result_ref
    event_type = EVENT_COMPLETED if status == "completed" else EVENT_FAILED
    envelope = _build_result_envelope(
        event_type=event_type,
        command=message,
        payload=result_payload,
    )
    if event_id:
        _processed[event_id] = envelope
    return envelope


async def run_worker() -> None:
    bootstrap = _env("KAFKA_BOOTSTRAP_SERVERS", "localhost:9093")
    commands_topic = _env("KAFKA_AI1_OCR_COMMANDS_TOPIC", "ci.ai1.ocr.commands")
    results_topic = _env("KAFKA_AI1_OCR_RESULTS_TOPIC", "ci.ai1.ocr.results")
    group_id = _env("KAFKA_AI1_OCR_GROUP_ID", "ci-ai1-ocr")

    consumer = AIOKafkaConsumer(
        commands_topic,
        bootstrap_servers=bootstrap,
        group_id=group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap,
        # Inline OCR results can exceed the default 1 MiB broker/client limit;
        # larger ones go to MinIO by reference (_deliver_result).
        max_request_size=MAX_MESSAGE_BYTES,
    )
    await consumer.start()
    await producer.start()
    logger.info(
        "ai1.kafka.worker.started bootstrap=%s commands=%s results=%s group=%s",
        bootstrap,
        commands_topic,
        results_topic,
        group_id,
    )
    try:
        async for record in consumer:
            message = record.value
            if not isinstance(message, dict):
                logger.warning("ai1.kafka.invalid_message raw=%r", message)
                await consumer.commit()
                continue
            document_id = None
            correlation = message.get("correlation")
            if isinstance(correlation, dict):
                document_id = correlation.get("document_id")
            if not document_id and isinstance(message.get("payload"), dict):
                document_id = message["payload"].get("document_id")
            key = str(document_id or "").encode("utf-8") or None
            try:
                envelope = await asyncio.to_thread(_handle_command, message)
                await producer.send_and_wait(
                    results_topic,
                    _encode(envelope),
                    key=key,
                )
                await consumer.commit()
                logger.info(
                    "ai1.kafka.result_published event_type=%s job_id=%s",
                    envelope.get("event_type"),
                    (envelope.get("payload") or {}).get("job_id"),
                )
            except Exception:
                # Permanent validation / OCR failures are published as failed;
                # unexpected errors leave the offset uncommitted for retry.
                logger.exception(
                    "ai1.kafka.command_failed event_id=%s",
                    message.get("event_id"),
                )
                try:
                    failed = _build_result_envelope(
                        event_type=EVENT_FAILED,
                        command=message,
                        payload={
                            "job_id": None,
                            "kind": "ocr",
                            "status": "failed",
                            "progress_pct": 100,
                            "current_stage": "failed",
                            "result": None,
                            "error": {
                                "code": "AI1_OCR_FAILED",
                                "message": "unhandled worker exception — see AI1 logs",
                            },
                        },
                    )
                    # Only commit after publishing failed for permanent errors
                    # that _handle_command already wraps; for transport issues
                    # re-raise. Here we treat as permanent after publish.
                    await producer.send_and_wait(
                        results_topic,
                        _encode(failed),
                        key=key,
                    )
                    await consumer.commit()
                except Exception:
                    logger.exception("ai1.kafka.failed_publish_also_failed")
    finally:
        await consumer.stop()
        await producer.stop()
        flush_langfuse()
        logger.info("ai1.kafka.worker.stopped")


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
