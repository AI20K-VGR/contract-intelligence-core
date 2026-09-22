"""Async Kafka producer singleton via aiokafka."""

from __future__ import annotations

import json
from typing import Any

import structlog
from aiokafka import AIOKafkaProducer

from contract_intelligence.config.settings import get_settings

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


async def publish_event(topic: str, message: dict[str, Any]) -> None:
    """Serialize ``message`` to JSON bytes and send it to ``topic``.

    In ``env=test`` (or when the producer was never started) this is a no-op so
    unit/integration suites do not require a live Kafka broker.
    """
    settings = get_settings()
    if _producer is None:
        if settings.env == "test":
            logger.debug(
                "kafka.event.skipped",
                topic=topic,
                event_type=message.get("event"),
                reason="producer_not_started",
            )
            return
        msg = "Kafka producer is not started — call start_producer() first"
        raise RuntimeError(msg)

    payload = json.dumps(message, default=str).encode("utf-8")
    await _producer.send_and_wait(topic, payload)
    logger.info(
        "kafka.event.published",
        topic=topic,
        event_type=message.get("event"),
    )


def get_producer() -> AIOKafkaProducer | None:
    """Return the live producer instance (or None if not started)."""
    return _producer
