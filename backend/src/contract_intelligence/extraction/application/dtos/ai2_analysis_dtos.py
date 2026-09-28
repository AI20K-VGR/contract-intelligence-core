"""DTOs for the persisted AI2 analysis read model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Ai2AnalysisDTO(BaseModel):
    """Canonical AI2 projection used by Facts/Findings screens."""

    model_config = ConfigDict(extra="forbid")

    dossier_id: str
    run_id: str | None = None
    available: bool = False
    pipeline_status: str | None = None
    job_status: str = "NOT_AVAILABLE"
    review_state: str = "UNKNOWN"
    completeness_state: str = "NOT_AVAILABLE"
    reason_code: str | None = None
    evidence_ready: bool = False
    input_counts: dict[str, int] = Field(default_factory=dict)
    output_counts: dict[str, int] = Field(default_factory=dict)
    coverage: dict[str, Any] = Field(default_factory=dict)
    dropped_records: int = 0
    evidence_issue_count: int = 0
    context_findings: list[dict[str, Any]] = Field(default_factory=list)
    evidence_issues: list[dict[str, Any]] = Field(default_factory=list)


__all__ = ["Ai2AnalysisDTO"]
