"""Pydantic schemas for inbound AI1 / AI2 webhook payloads."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AI1SnapshotPayload(BaseModel):
    """OCR snapshot contract delivered by AI1 after document processing."""

    model_config = ConfigDict(extra="ignore")

    snapshot_id: str
    version: str
    digest: str
    quality_state: dict[str, Any] = Field(default_factory=dict)
    pages: list[Any] = Field(default_factory=list)
    nodes: list[Any] = Field(default_factory=list)
    tables: list[Any] = Field(default_factory=list)
    source_files: list[Any] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class AI2FindingsPayload(BaseModel):
    """Candidate findings contract delivered by AI2 after semantics processing."""

    model_config = ConfigDict(extra="ignore")

    run_id: str
    facts: list[Any] = Field(default_factory=list)
    findings: list[Any] = Field(default_factory=list)
    index_contribution: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "AI1SnapshotPayload",
    "AI2FindingsPayload",
]
