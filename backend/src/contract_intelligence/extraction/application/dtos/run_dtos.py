"""DTOs for pipeline runs — Phase 4 OpenAPI alignment."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CreateRunConfigOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ocr_profile: Literal["standard", "high_res_binarize", "table_optimized"] | None = None
    prompt_candidate_id: str | None = None
    confidence_threshold: float | None = Field(default=None, ge=0, le=1)


class CreateRunRequestDTO(BaseModel):
    """Optional body for POST /dossiers/{id}/runs."""

    model_config = ConfigDict(extra="forbid")

    config_override: CreateRunConfigOverride | None = None


class PipelineRunSummaryDTO(BaseModel):
    """openapi.yaml: PipelineRunSummary."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    dossier_id: str
    status: str
    triggered_by: str | None = None
    duration_seconds: float | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None

    @classmethod
    def from_domain(cls, run: Any, *, triggered_by: str | None = None) -> PipelineRunSummaryDTO:
        # Map internal ``succeeded`` → OpenAPI ``completed``
        status = getattr(run.status, "value", str(run.status))
        if status == "succeeded":
            status = "completed"

        created = getattr(run, "created_at", None)
        finished = getattr(run, "finished_at", None)
        if isinstance(finished, str):
            try:
                finished = datetime.fromisoformat(finished.replace("Z", "+00:00"))
            except ValueError:
                finished = None

        duration = None
        if created is not None and finished is not None and hasattr(created, "timestamp"):
            duration = max(0.0, finished.timestamp() - created.timestamp())

        return cls(
            run_id=run.id,
            dossier_id=run.dossier_id,
            status=status,
            triggered_by=triggered_by or getattr(run, "trace_id", None),
            duration_seconds=duration,
            created_at=created if isinstance(created, datetime) else None,
            finished_at=finished if isinstance(finished, datetime) else None,
        )


class ReprocessAcceptedDTO(BaseModel):
    """ApiEnvelopeDossierCreated.data for POST /dossiers/{id}/reprocess."""

    model_config = ConfigDict(extra="forbid")

    dossier_id: str
    job_id: str | None = None


__all__ = [
    "CreateRunConfigOverride",
    "CreateRunRequestDTO",
    "PipelineRunSummaryDTO",
    "ReprocessAcceptedDTO",
]
