"""PipelineRun — 1 lần chạy pipeline (checkpoint + trace).

Tương ứng bảng ``pipeline_run`` (xem ``DOC-04c`` §4.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from contract_intelligence.shared.base import BaseEntity, new_ulid


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Backwards-compat alias — extraction service uses PipelineRunStatus
PipelineRunStatus = RunStatus


@dataclass(eq=False)
class PipelineRun(BaseEntity[str]):
    id: str = field(default_factory=lambda: new_ulid("run_"))
    job_id: str = ""
    dossier_id: str = ""
    status: RunStatus = RunStatus.QUEUED
    config_snapshot: dict[str, object] = field(default_factory=dict)
    pipeline_version: str = ""
    git_sha: str = ""
    trace_id: str | None = None
    requested_by_pseudo_id: str | None = None
    finished_at: str | None = None  # ISO timestamp
    tenant_id: str = ""
