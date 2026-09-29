"""Kafka messages leave the backend as compact UTF-8, not ASCII escapes."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from contract_intelligence.infrastructure import messaging

# conftest's autouse fixture swaps publish_event for a mock; keep the real one.
_publish_event = messaging.publish_event


@pytest.mark.asyncio
async def test_publish_event_keeps_vietnamese_as_utf8(monkeypatch: pytest.MonkeyPatch) -> None:
    producer = AsyncMock()
    monkeypatch.setattr(messaging, "_producer", producer)
    message = {"event": "x", "text": "Điều 1. Hợp đồng mua bán hàng hoá"}

    await _publish_event("topic", message, key="k")

    (_topic, payload), kwargs = producer.send_and_wait.await_args
    assert b"\u" not in payload
    assert "Điều 1. Hợp đồng".encode() in payload
    assert json.loads(payload.decode("utf-8")) == message
    assert len(payload) < len(json.dumps(message).encode())
    assert kwargs["key"] == b"k"
