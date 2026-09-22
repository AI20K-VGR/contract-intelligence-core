"""Shared infrastructure adapters — MinIO/S3 storage, Kafka messaging."""

from __future__ import annotations

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
    "upload_file",
]
