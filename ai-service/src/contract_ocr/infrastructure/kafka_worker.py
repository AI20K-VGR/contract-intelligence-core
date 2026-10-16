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
import time
from collections.abc import Callable
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
    pop_backend_job,
    run_backend_ocr,
)
from contract_ocr.infrastructure.memory import release_memory
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
# Advisory pages-done report while a document is read (DOC-05d, issue #115).
EVENT_PROGRESS = "ai1.ocr.progress"
# At most one progress report a second per document; the last page always goes.
PROGRESS_MIN_INTERVAL_SECONDS = 1.0
# A snapshot is usable when at least one page was read (DOC-05d §5).
READABLE_PAGE_STATUSES = frozenset({"SUCCESS", "PARTIAL"})

# The producer's cap, and the largest result still sent inline when the upload to
# the backend's result_target fails (an inline OCR result costs ~71 KiB per page).
MAX_MESSAGE_BYTES = 10_485_760  # 10 MiB
# Room left in a message for the envelope around an inline result.
_ENVELOPE_ALLOWANCE = 64 * 1024

# In-process idempotency for at-least-once redelivery (event_id → result envelope).
# A redelivery follows its original closely, so only the most recent envelopes
# are kept: an envelope can carry a whole inline OCR result (up to 10 MiB).
_processed: dict[str, dict[str, Any]] = {}


def _processed_kept() -> int:
    try:
        return max(1, int(os.environ.get("AI1_PROCESSED_EVENTS_KEPT", "32")))
    except ValueError:
        return 32


def _remember_processed(event_id: str, envelope: dict[str, Any]) -> None:
    _processed.pop(event_id, None)
    _processed[event_id] = envelope
    excess = len(_processed) - _processed_kept()
    for oldest in list(_processed)[: max(0, excess)]:
        del _processed[oldest]


# Set by run_worker: hands an encoded progress envelope to the producer from the
# OCR thread without waiting for Kafka. None (tests, HTTP API) = no reports.
_progress_sink: Callable[[bytes, bytes | None], None] | None = None


def _message_key(message: dict[str, Any]) -> bytes | None:
    """Partition key of a command's results: its document, so a document's
    progress reports and its result share a partition and keep their order."""
    document_id = None
    correlation = message.get("correlation")
    if isinstance(correlation, dict):
        document_id = correlation.get("document_id")
    if not document_id and isinstance(message.get("payload"), dict):
        document_id = message["payload"].get("document_id")
    return str(document_id or "").encode("utf-8") or None


def _progress_reporter(
    message: dict[str, Any],
    job_id: str,
    *,
    clock: Callable[[], float] = time.monotonic,
) -> Callable[[int, int], None] | None:
    """``on_progress`` for one command: ``ai1.ocr.progress`` at most once a
    second, plus the last page, each with an ``event_id`` of its own.

    The backend skips any results-topic message whose ``event_id`` it has already
    handled, and ``ai1.ocr.completed`` carries the command's ``event_id``: a
    progress report must never reuse it, or the result itself would be dropped.
    """
    sink = _progress_sink
    if sink is None:
        return None
    key = _message_key(message)
    base_event_id = str(message.get("event_id") or f"evt_{job_id}")
    last = {"done": 0, "at": float("-inf")}

    def report(done: int, total: int) -> None:
        now = clock()
        if done <= last["done"]:
            return
        if done < total and now - last["at"] < PROGRESS_MIN_INTERVAL_SECONDS:
            return
        last["done"], last["at"] = done, now
        envelope = _build_result_envelope(
            event_type=EVENT_PROGRESS,
            command=message,
            payload={
                "job_id": job_id,
                "kind": "ocr",
                "status": "processing",
                "progress": {"done": done, "total": total, "unit": "page"},
            },
        )
        envelope["event_id"] = f"{base_event_id}:progress:{done}"
        sink(_encode(envelope), key)

    return report


def _no_readable_page(result: Any) -> str | None:
    """``error.message`` for AI1_NO_READABLE_PAGE, or None when the snapshot is usable.

    The backend's rule and wording (``worker._no_readable_page``, #117), so both
    sides fail exactly the same documents: every page has a status and none is
    SUCCESS/PARTIAL. A page without a status is not judged, and then nothing is
    concluded. The message names the page count and the first page error, cut to
    200 characters, as the run's ``error_detail`` shows it.
    """
    snapshot = result.get("snapshot") if isinstance(result, dict) else None
    raw_pages = snapshot.get("pages") if isinstance(snapshot, dict) else None
    pages = [p if isinstance(p, dict) else {} for p in raw_pages or []]
    statuses = {str(p.get("status") or "").upper() for p in pages}
    if not pages or "" in statuses or READABLE_PAGE_STATUSES & statuses:
        return None
    first_error = next((str(p["error"]) for p in pages if p.get("error")), "")
    detail = f"AI1 không đọc được trang nào ({len(pages)}/{len(pages)} trang lỗi)"
    return f"{detail}: {first_error[:200]}" if first_error else detail


def _make_progress_sink(
    producer: Any, topic: str, loop: asyncio.AbstractEventLoop
) -> Callable[[bytes, bytes | None], None]:
    """A sink the OCR thread calls: it queues the send on the worker's event
    loop and returns at once, so OCR never waits on Kafka for a progress report."""

    def send(value: bytes, key: bytes | None) -> None:
        future = asyncio.run_coroutine_threadsafe(producer.send(topic, value, key=key), loop)
        future.add_done_callback(_log_progress_failure)

    return send


def _log_progress_failure(future: Any) -> None:
    if not future.cancelled() and future.exception() is not None:
        # Advisory: a lost progress report only leaves the ring where it was.
        logger.warning("ai1.kafka.progress_send_failed error=%r", future.exception())


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
    try:
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
        if event_id:
            _remember_processed(event_id, envelope)
        return envelope
    finally:
        # Page renders and the snapshot are garbage now: hand the pages back
        # instead of holding the job's peak until the worker restarts.
        release_memory()


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
    request = align_pages_to_pdf(request)
    job_id, _job = new_backend_job("ocr")
    run_backend_ocr(
        job_id,
        request,
        trace_seed=str(message.get("trace_id") or message.get("event_id") or job_id),
        on_progress=_progress_reporter(message, job_id),
    )
    job = get_backend_job(job_id)
    # The worker is this job's only reader: drop it from the registry, which
    # otherwise keeps every document's full snapshot for the process's life.
    pop_backend_job(job_id)
    if job is None:
        raise RuntimeError(f"OCR job disappeared: {job_id}")

    status = str(job.get("status") or "failed")
    engine = str(request.options.get("engine", "pymupdf"))
    pages = len(request.pages_to_process)
    result, result_ref, error = job.get("result"), None, job.get("error")
    unreadable = _no_readable_page(result) if status == "completed" else None
    if unreadable is not None:
        # Every page FAILED (e.g. "SKIPPED: OpenAI vision unavailable" when a key is
        # missing): an empty dossier must not reach AI2. The message is built from
        # the snapshot above, before it is dropped here and never uploaded.
        status, result = "failed", None
        error = {"code": "AI1_NO_READABLE_PAGE", "message": unreadable}
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
    global _progress_sink  # noqa: PLW0603
    _progress_sink = _make_progress_sink(producer, results_topic, asyncio.get_running_loop())
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
            key = _message_key(message)
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
        _progress_sink = None
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
