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
import random
import time
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from contract_ocr.infrastructure.backend_ocr_job import (
    BackendOcrJobRequest,
    get_backend_job,
    new_backend_job,
    run_backend_ocr,
    update_backend_job,
)
from contract_ocr.infrastructure.observability import flush_langfuse
from contract_ocr.infrastructure.prometheus_metrics import (
    ocr_in_progress,
    record_ocr_job,
    start_metrics_server,
)

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

# Waits before each retry of a failed result upload (each gets ±20% jitter).
# A 200-page result (~14 MB) does not fit a Kafka message, so a single failed
# PUT used to fail the whole job.
_UPLOAD_RETRY_DELAYS = (1.0, 4.0, 16.0)

# Client errors a retry can fix: request timeout and rate limiting. Any other
# 4xx (403 expired URL, 400, 413 ...) fails the same way every time.
_RETRYABLE_CLIENT_ERRORS = frozenset({408, 429})

# Kafka's default (5 min) is far below one long document: past it the
# consumer leaves the group, the commit fails and the command is read again.
# Keep it above the longest OCR run; the backend gives a document
# AI1_DEADLINE_BASE_SECONDS + AI1_DEADLINE_PER_PAGE_SECONDS x pages.
DEFAULT_MAX_POLL_INTERVAL_MS = 3_600_000

# In-process idempotency for at-least-once redelivery (event_id → result envelope).
# Only a recent redelivery needs it, so the oldest entries are dropped, and an
# envelope carrying an inline result (up to ~10 MiB) is not kept at all.
MAX_REMEMBERED_EVENTS = 500
_processed: OrderedDict[str, dict[str, Any]] = OrderedDict()


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


def _put_result_with_retries(put_url: str, body: bytes, content_type: str) -> None:
    """``_put_result``, retried after each delay of ``_UPLOAD_RETRY_DELAYS``.

    Only failures a retry can fix are retried: 5xx, 408/429, timeouts and
    dropped connections. Any other 4xx is raised at once. The last error is
    raised once every attempt has failed.
    """
    attempts = len(_UPLOAD_RETRY_DELAYS) + 1
    for attempt in range(1, attempts + 1):
        try:
            _put_result(put_url, body, content_type)
            return
        except (OSError, URLError) as exc:
            permanent = (
                isinstance(exc, HTTPError)
                and 400 <= exc.code < 500
                and exc.code not in _RETRYABLE_CLIENT_ERRORS
            )
            logger.warning(
                "ai1.kafka.result_upload_failed bytes=%d attempt=%d/%d error=%s",
                len(body),
                attempt,
                attempts,
                type(exc).__name__,
            )
            if permanent or attempt == attempts:
                raise
            time.sleep(_UPLOAD_RETRY_DELAYS[attempt - 1] * random.uniform(0.8, 1.2))  # noqa: S311


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
        _put_result_with_retries(
            put_url, body, str(result_target.get("content_type") or "application/json")
        )
    except (OSError, URLError) as exc:
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


def _command_engine(message: dict[str, Any]) -> Any:
    payload = message.get("payload")
    options = payload.get("options") if isinstance(payload, dict) else None
    return options.get("engine", "pymupdf") if isinstance(options, dict) else None


def _handle_command(message: dict[str, Any]) -> dict[str, Any]:
    """Synchronously process one OCR command; return the result envelope."""
    event_id = str(message.get("event_id") or "")
    if event_id and event_id in _processed:
        logger.info("ai1.kafka.duplicate_event", extra={"event_id": event_id})
        return _processed[event_id]

    started = time.monotonic()
    with ocr_in_progress():
        envelope, snapshot_result = _process_command(message)
    payload = envelope["payload"]
    record_ocr_job(
        engine=_command_engine(message),
        status=str(payload.get("status")),
        error=payload.get("error"),
        duration_seconds=time.monotonic() - started,
        result=snapshot_result,
    )
    # A redelivered command is answered from here only when the envelope is small
    # (result by reference, or a failure). One with an inline result is not
    # kept: a redelivery of it reads the document again rather than holding it.
    if event_id and (envelope.get("payload") or {}).get("result") is None:
        _processed[event_id] = envelope
        while len(_processed) > MAX_REMEMBERED_EVENTS:
            _processed.popitem(last=False)
    return envelope


def _process_command(message: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    """Run the OCR job; return the result envelope and the job's own result.

    The job result is returned separately for page metrics: once uploaded by
    reference, the envelope no longer carries it.
    """
    if message.get("event_type") != EVENT_COMMAND:
        raise ValueError(f"unexpected event_type: {message.get('event_type')!r}")

    raw_payload = message.get("payload")
    if not isinstance(raw_payload, dict):
        raise ValueError("command payload must be an object")

    request = BackendOcrJobRequest.model_validate(raw_payload)
    job_id, _job = new_backend_job("ocr")
    # The run downloads the PDF once and reads every page of it (AI1 OCRs whole
    # documents), whatever range the command names.
    run_backend_ocr(
        job_id,
        request,
        trace_seed=str(message.get("trace_id") or message.get("event_id") or job_id),
        align_pages=True,
    )
    job = get_backend_job(job_id)
    if job is None:
        raise RuntimeError(f"OCR job disappeared: {job_id}")

    status = str(job.get("status") or "failed")
    engine = str(request.options.get("engine", "pymupdf"))
    pages = job.get("page_count") or len(request.pages_to_process)
    result, result_ref, error = job.get("result"), None, job.get("error")
    if status == "completed" and isinstance(result, dict):
        result, result_ref, upload_error = _deliver_result(
            result, request.options.get("result_target")
        )
        if upload_error is not None:
            status, error = "failed", upload_error
    # The result now lives in MinIO, or inline in the envelope: the job table
    # needs no copy of it (~71 KiB per page).
    update_backend_job(job_id, result=None)
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
    return envelope, job.get("result")


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
        # One command can take far longer than Kafka's 5-minute default.
        max_poll_interval_ms=int(
            _env("KAFKA_MAX_POLL_INTERVAL_MS", str(DEFAULT_MAX_POLL_INTERVAL_MS))
        ),
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap,
        # Inline OCR results can exceed the default 1 MiB broker/client limit;
        # larger ones go to MinIO by reference (_deliver_result).
        max_request_size=MAX_MESSAGE_BYTES,
    )
    start_metrics_server()
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
            # Set once a result (completed or failed) has been published; only
            # then is the offset committed.
            published = False
            try:
                envelope = await asyncio.to_thread(_handle_command, message)
                await producer.send_and_wait(
                    results_topic,
                    _encode(envelope),
                    key=key,
                )
                published = True
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
                record_ocr_job(engine=_command_engine(message), status="failed")
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
                    # Treated as permanent once the failure is published; if that
                    # publish fails too, the offset stays uncommitted for retry.
                    await producer.send_and_wait(
                        results_topic,
                        _encode(failed),
                        key=key,
                    )
                    published = True
                except Exception:
                    logger.exception("ai1.kafka.failed_publish_also_failed")
            if published:
                # Outside the processing try: a rejected commit (e.g. the group
                # rebalanced) must not publish ai1.ocr.failed for a document whose
                # result was already sent. The command may be read again; the
                # backend drops a result for a run that is no longer current.
                try:
                    await consumer.commit()
                except Exception:
                    logger.exception("ai1.kafka.commit_failed event_id=%s", message.get("event_id"))
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
