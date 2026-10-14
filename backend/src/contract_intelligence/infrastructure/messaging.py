"""Async Kafka producer singleton via aiokafka."""

from __future__ import annotations

import json
from typing import Any

import structlog
from aiokafka import AIOKafkaProducer

from contract_intelligence.config.settings import get_settings
from contract_intelligence.shared.base import new_ulid

logger = structlog.get_logger(__name__)

_producer: AIOKafkaProducer | None = None


async def start_producer() -> None:
    """Initialize the shared AIOKafkaProducer and open the broker connection."""
    global _producer  # noqa: PLW0603
    if _producer is not None:
        return

    settings = get_settings()
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda v: v,  # publish_event already encodes JSON bytes
        # AI1 OCR results / AI2 IDP commands can exceed the default 1 MiB limit.
        max_request_size=settings.kafka_max_message_bytes,
    )
    await producer.start()
    _producer = producer
    logger.info(
        "kafka.producer.started",
        bootstrap_servers=settings.kafka_bootstrap_servers,
    )


async def stop_producer() -> None:
    """Flush and close the shared producer connection."""
    global _producer  # noqa: PLW0603
    if _producer is None:
        return
    await _producer.stop()
    _producer = None
    logger.info("kafka.producer.stopped")


async def publish_event(
    topic: str,
    message: dict[str, Any],
    *,
    key: str | None = None,
) -> None:
    """Serialize ``message`` to JSON bytes and send it to ``topic``.

    A message without ``event_id`` gets one. The worker skips records whose
    ``event_id`` it has already handled; without one it falls back to
    ``topic:partition:offset``, and Kafka has no volume on prod: after a broker
    restart offsets start again at 0, so new ``dossier_events`` matched old
    rows in ``processed_event`` and were dropped.

    In ``env=test`` (or when the producer was never started) this is a no-op so
    unit/integration suites do not require a live Kafka broker.
    """
    if not message.get("event_id"):
        message = {"event_id": new_ulid("evt_"), **message}
    settings = get_settings()
    if _producer is None:
        if settings.env == "test":
            logger.debug(
                "kafka.event.skipped",
                topic=topic,
                event_type=message.get("event_type") or message.get("event"),
                reason="producer_not_started",
            )
            return
        msg = "Kafka producer is not started — call start_producer() first"
        raise RuntimeError(msg)

    # ensure_ascii=False: Vietnamese text goes out as UTF-8 instead of ASCII
    # escapes, which roughly double its size on the wire.
    payload = json.dumps(message, default=str, ensure_ascii=False).encode("utf-8")
    kafka_key = key.encode("utf-8") if key else None
    await _producer.send_and_wait(topic, payload, key=kafka_key)
    logger.info(
        "kafka.event.published",
        topic=topic,
        event_type=message.get("event_type") or message.get("event"),
        key=key,
    )


def get_producer() -> AIOKafkaProducer | None:
    """Return the live producer instance (or None if not started)."""
    return _producer
