"""Kafka worker — consume AI2 IDP commands, run IDP, publish results (DOC-05e).

Run::

    uv run --extra web --extra kafka python -m app.transport.kafka_idp_worker

HTTP ``POST /jobs/idp`` remains demo-only; this module is the runtime path.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from app.contracts.wire import job_result_to_wire
from app.llm.client import NineRouterClient
from app.pipeline.ai1_snapshot_adapter import (
    SnapshotContractError,
    adapt_be_ai2_processing_request,
)
from app.pipeline.idp import run_idp
from app.pipeline.runtime import ProcessingRuntime
from app.tools.query_store import save_query_snapshot
from app.tools.store import DossierRecord, InMemorySnapshotStore

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "ci.kafka.v1"
EVENT_COMMAND = "ai2.idp.command"
EVENT_COMPLETED = "ai2.idp.completed"
EVENT_FAILED = "ai2.idp.failed"

# In-process idempotency for at-least-once redelivery (event_id → result envelope).
_processed: dict[str, dict[str, Any]] = {}


class RetryableAI2Error(RuntimeError):
    """A transient AI2 failure that must be redelivered by Kafka."""


_RETRYABLE_EXCEPTION_NAMES = frozenset(
    {
        "APIConnectionError",
        "APITimeoutError",
        "InternalServerError",
        "RateLimitError",
        "ServiceUnavailableError",
    }
)


def _is_retryable_exception(exc: BaseException) -> bool:
    """Classify provider/transport failures without hiding contract failures."""
    if isinstance(exc, RetryableAI2Error):
        return True
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    if bool(getattr(exc, "retryable", False)):
        return True
    if type(exc).__name__ in _RETRYABLE_EXCEPTION_NAMES:
        return True
    status_code = getattr(exc, "status_code", None)
    return isinstance(status_code, int) and status_code in {408, 425, 429, 500, 502, 503, 504}


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


def _failed_wire(
    *,
    request_meta: dict[str, Any],
    job_id: str,
    code: str,
    message: str,
    retryable: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": "ai2.be.processing.result.v1",
        "request_id": request_meta.get("request_id") or "",
        "idempotency_key": request_meta.get("idempotency_key") or "",
        "attempt": int(request_meta.get("attempt") or 1),
        "job_id": job_id,
        "status": "FAILED",
        "review_state": "BLOCKED",
        "input_snapshots": list(request_meta.get("snapshot_identities") or []),
        "result": None,
        "errors": [{"code": code, "message": message, "retryable": retryable}],
    }


def _handle_command(message: dict[str, Any]) -> dict[str, Any]:
    """Synchronously process one IDP command; return the result envelope."""
    event_id = str(message.get("event_id") or "")
    if event_id and event_id in _processed:
        logger.info("ai2.kafka.duplicate_event event_id=%s", event_id)
        return _processed[event_id]

    if message.get("event_type") != EVENT_COMMAND:
        raise ValueError(f"unexpected event_type: {message.get('event_type')!r}")

    raw_payload = message.get("payload")
    if not isinstance(raw_payload, dict):
        raise ValueError("command payload must be an object")

    job_id = f"job_{uuid4().hex[:24]}"
    tenant_id = str(
        message.get("tenant_id")
        or (raw_payload.get("service_envelope") or {}).get("tenant_id")
        or "unknown"
    )
    actor_id = str((raw_payload.get("service_envelope") or {}).get("actor_id") or "backend")

    try:
        # Kafka path: trust internal cluster — do not require HMAC verify.
        request, adapted = adapt_be_ai2_processing_request(
            raw_payload,
            tenant_id=tenant_id,
            actor_id=actor_id,
        )
        # MVP body-only: exactly one body member (also enforced by wire model).
        bodies = [m for m in request.dossier_members if m.role == "body"]
        if len(bodies) != 1 or len(request.dossier_members) != 1:
            raise SnapshotContractError(
                "MVP body-only requires exactly one dossier member with role=body",
                code="MVP_BODY_ONLY_VIOLATION",
            )

        llm = None
        if request.policy_flags.egress_allowed:
            candidate = NineRouterClient()
            if candidate.configured():
                llm = candidate
        runtime = ProcessingRuntime(
            egress_allowed=request.policy_flags.egress_allowed,
            use_vector=request.policy_flags.use_vector,
            max_processing_seconds=request.policy_flags.budget_limits.max_processing_seconds,
            max_llm_calls=request.policy_flags.budget_limits.max_llm_calls,
            max_embedding_tokens=request.policy_flags.budget_limits.max_embedding_tokens,
        )
        store = InMemorySnapshotStore()
        # The HTTP query API is a separate process. Preserve the adapted
        # citation-bearing snapshot before the in-memory IDP run is discarded.
        if isinstance(adapted.record, DossierRecord):
            save_query_snapshot(adapted.record, adapted.envelope)
        result = run_idp(
            adapted.record,
            adapted.envelope,
            llm=llm,
            store=store,
            job_id=job_id,
            runtime=runtime,
        )
        wire = job_result_to_wire(result, request)
        wire["job_id"] = job_id
        event_type = (
            EVENT_COMPLETED
            if str(wire.get("status") or "").upper() == "SUCCEEDED"
            else EVENT_FAILED
        )
        envelope = _build_result_envelope(
            event_type=event_type,
            command=message,
            payload=wire,
        )
    except SnapshotContractError as exc:
        wire = _failed_wire(
            request_meta=raw_payload,
            job_id=job_id,
            code=exc.code,
            message=str(exc),
            retryable=False,
        )
        # Preserve snapshot identities shape if present as pydantic dumps.
        identities = raw_payload.get("snapshot_identities")
        if isinstance(identities, list):
            wire["input_snapshots"] = identities
        envelope = _build_result_envelope(
            event_type=EVENT_FAILED,
            command=message,
            payload=wire,
        )
    except Exception as exc:
        logger.exception("ai2.kafka.pipeline_failed event_id=%s", event_id)
        if _is_retryable_exception(exc):
            raise RetryableAI2Error(str(exc)) from exc
        envelope = _build_result_envelope(
            event_type=EVENT_FAILED,
            command=message,
            payload=_failed_wire(
                request_meta=raw_payload,
                job_id=job_id,
                code="AI2_WORKER_FAILED",
                message=str(exc),
                retryable=False,
            ),
        )

    if event_id:
        _processed[event_id] = envelope
    return envelope


async def run_worker() -> None:
    bootstrap = _env("KAFKA_BOOTSTRAP_SERVERS", "localhost:9093")
    commands_topic = _env("KAFKA_AI2_IDP_COMMANDS_TOPIC", "ci.ai2.idp.commands")
    results_topic = _env("KAFKA_AI2_IDP_RESULTS_TOPIC", "ci.ai2.idp.results")
    group_id = _env("KAFKA_AI2_IDP_GROUP_ID", "ci-ai2-idp")

    consumer = AIOKafkaConsumer(
        commands_topic,
        bootstrap_servers=bootstrap,
        group_id=group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        max_partition_fetch_bytes=10_485_760,
        fetch_max_bytes=10_485_760,
    )
    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap,
        max_request_size=10_485_760,
    )
    await consumer.start()
    await producer.start()
    logger.info(
        "ai2.kafka.worker.started bootstrap=%s commands=%s results=%s group=%s",
        bootstrap,
        commands_topic,
        results_topic,
        group_id,
    )
    try:
        async for record in consumer:
            message = record.value
            if not isinstance(message, dict):
                logger.warning("ai2.kafka.invalid_message raw=%r", message)
                await consumer.commit()
                continue
            dossier_id = None
            correlation = message.get("correlation")
            if isinstance(correlation, dict):
                dossier_id = correlation.get("dossier_id")
            if not dossier_id and isinstance(message.get("payload"), dict):
                dossier_id = message["payload"].get("dossier_id")
            key = str(dossier_id or "").encode("utf-8") or None
            try:
                envelope = await asyncio.to_thread(_handle_command, message)
                await producer.send_and_wait(
                    results_topic,
                    json.dumps(envelope, default=str).encode("utf-8"),
                    key=key,
                )
                await consumer.commit()
                logger.info(
                    "ai2.kafka.result_published event_type=%s job_id=%s",
                    envelope.get("event_type"),
                    (envelope.get("payload") or {}).get("job_id"),
                )
            except RetryableAI2Error:
                # Do not publish a terminal result or commit the offset. Kafka
                # will redeliver the command after a transient AI2/provider
                # failure.
                logger.warning(
                    "ai2.kafka.retryable_failure event_id=%s",
                    message.get("event_id"),
                    exc_info=True,
                )
                continue
            except Exception as exc:
                if _is_retryable_exception(exc):
                    # A failed result publish is also retryable: without a
                    # committed offset Kafka will redeliver the command.
                    logger.warning(
                        "ai2.kafka.retryable_publish_failure event_id=%s",
                        message.get("event_id"),
                        exc_info=True,
                    )
                    continue
                logger.exception(
                    "ai2.kafka.command_failed event_id=%s",
                    message.get("event_id"),
                )
                try:
                    failed = _build_result_envelope(
                        event_type=EVENT_FAILED,
                        command=message,
                        payload={
                            "error": {
                                "code": "AI2_IDP_FAILED",
                                "message": "unhandled worker exception — see AI2 logs",
                                "retryable": False,
                            }
                        },
                    )
                    await producer.send_and_wait(
                        results_topic,
                        json.dumps(failed, default=str).encode("utf-8"),
                        key=key,
                    )
                    await consumer.commit()
                except Exception:
                    logger.exception("ai2.kafka.failed_publish_also_failed")
    finally:
        await consumer.stop()
        await producer.stop()
        logger.info("ai2.kafka.worker.stopped")


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
