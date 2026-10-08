"""Kafka messages leave the backend as compact UTF-8 and with an ``event_id``."""

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
    message = {"event_id": "evt_1", "event": "x", "text": "Điều 1. Hợp đồng mua bán hàng hoá"}

    await _publish_event("topic", message, key="k")

    (_topic, payload), kwargs = producer.send_and_wait.await_args
    assert b"\u" not in payload
    assert "Điều 1. Hợp đồng".encode() in payload
    assert json.loads(payload.decode("utf-8")) == message
    assert len(payload) < len(json.dumps(message).encode())
    assert kwargs["key"] == b"k"


@pytest.mark.asyncio
async def test_publish_event_gives_each_event_its_own_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two dossier events at the same offset of a recreated topic stay distinct."""
    producer = AsyncMock()
    monkeypatch.setattr(messaging, "_producer", producer)
    message = {"event": "dossier.uploaded", "dossier_id": "dos_1"}

    await _publish_event("dossier_events", message)
    await _publish_event("dossier_events", message)

    first, second = (
        json.loads(call.args[1].decode("utf-8")) for call in producer.send_and_wait.await_args_list
    )
    assert first["event_id"].startswith("evt_")
    assert first["event_id"] != second["event_id"]
    assert "event_id" not in message


@pytest.mark.asyncio
async def test_publish_event_keeps_an_existing_event_id(monkeypatch: pytest.MonkeyPatch) -> None:
    producer = AsyncMock()
    monkeypatch.setattr(messaging, "_producer", producer)

    await _publish_event("ci.ai1.ocr.commands", {"event_id": "evt_ai1", "event_type": "x"})

    payload = producer.send_and_wait.await_args.args[1]
    assert json.loads(payload.decode("utf-8"))["event_id"] == "evt_ai1"
