"""Shared infrastructure adapters — MinIO/S3 storage, Kafka messaging, AI HTTP."""

from __future__ import annotations

from contract_intelligence.infrastructure.ai_adapters import (
    submit_to_ai1,
    submit_to_ai2,
)
from contract_intelligence.infrastructure.messaging import (
    publish_event,
    start_producer,
    stop_producer,
)
from contract_intelligence.infrastructure.storage import upload_file

__all__ = [
    "publish_event",
    "start_producer",
    "stop_producer",
    "submit_to_ai1",
    "submit_to_ai2",
    "upload_file",
]
