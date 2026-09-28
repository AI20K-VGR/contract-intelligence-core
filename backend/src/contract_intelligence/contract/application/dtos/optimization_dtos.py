"""DTOs for Optimization Studio — Phase 5 OpenAPI alignment."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

TargetMetric = Literal["f1_score", "precision", "latency", "cost"]
CampaignStatus = Literal["active", "completed", "archived"]
ExperimentStatus = Literal["configured", "running", "completed", "failed"]


class CreateCampaignRequestDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    target_metric: TargetMetric
    baseline_score: float


class OptimizationCampaignDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_id: str
    name: str
    description: str | None = None
    target_metric: str
    baseline_score: float = 0.0
    current_best_score: float | None = None
    status: str
    created_at: datetime | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> OptimizationCampaignDTO:
        created = row.get("created_at")
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                created = None
        return cls(
            campaign_id=str(row.get("campaign_id") or row.get("id") or ""),
            name=str(row.get("name") or ""),
            description=row.get("description") or row.get("goal"),
            target_metric=str(row.get("target_metric") or "f1_score"),
            baseline_score=float(row.get("baseline_score") or 0.0),
            current_best_score=(
                float(row["current_best_score"])
                if row.get("current_best_score") is not None
                else None
            ),
            status=_map_campaign_status(str(row.get("status") or "active")),
            created_at=created if isinstance(created, datetime) else None,
        )


class CreateCandidateRequestDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_id: str
    name: str = Field(..., min_length=1)
    prompt_template: str
    model_name: str
    temperature: float = 0.0


class OptimizationCandidateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    campaign_id: str
    name: str | None = None
    prompt_template: str
    model_name: str
    temperature: float = 0.0
    is_active_production: bool = False
    benchmark_f1: float | None = None
    created_at: datetime | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> OptimizationCandidateDTO:
        created = row.get("created_at")
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                created = None
        hyper = row.get("hyperparameters") or {}
        if isinstance(hyper, str):
            import json

            try:
                hyper = json.loads(hyper)
            except json.JSONDecodeError:
                hyper = {}

        if row.get("temperature") is not None:
            temperature = float(row["temperature"])
        else:
            temperature = float(hyper.get("temperature", 0.0))

        benchmark_f1 = None
        if row.get("benchmark_f1") is not None:
            benchmark_f1 = float(row["benchmark_f1"])
        elif isinstance(row.get("metrics"), dict) and row["metrics"].get("f1") is not None:
            benchmark_f1 = float(row["metrics"]["f1"])

        return cls(
            candidate_id=str(row.get("candidate_id") or row.get("id") or ""),
            campaign_id=str(row.get("campaign_id") or ""),
            name=row.get("name"),
            prompt_template=str(row.get("prompt_template") or row.get("prompt_version") or ""),
            model_name=str(row.get("model_name") or hyper.get("model_name") or "unknown"),
            temperature=temperature,
            is_active_production=bool(
                row.get("is_active_production")
                if row.get("is_active_production") is not None
                else row.get("is_promoted")
            ),
            benchmark_f1=benchmark_f1,
            created_at=created if isinstance(created, datetime) else None,
        )


class CreateExperimentRequestDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_id: str
    candidate_id: str
    golden_dataset_version: str
    sample_size: int = Field(default=100, ge=1)


class OptimizationExperimentDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_id: str
    campaign_id: str
    candidate_id: str
    golden_dataset_version: str
    status: str
    created_at: datetime | None = None
    completed_at: datetime | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> OptimizationExperimentDTO:
        created = row.get("created_at")
        completed = row.get("completed_at") or row.get("finished_at")
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                created = None
        if isinstance(completed, str):
            try:
                completed = datetime.fromisoformat(completed.replace("Z", "+00:00"))
            except ValueError:
                completed = None
        return cls(
            experiment_id=str(row.get("experiment_id") or row.get("id") or ""),
            campaign_id=str(row.get("campaign_id") or ""),
            candidate_id=str(row.get("candidate_id") or ""),
            golden_dataset_version=str(
                row.get("golden_dataset_version") or row.get("benchmark_set_name") or ""
            ),
            status=_map_experiment_status(str(row.get("status") or "configured")),
            created_at=created if isinstance(created, datetime) else None,
            completed_at=completed if isinstance(completed, datetime) else None,
        )


class ExperimentResultDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_id: str
    f1_score: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    avg_latency_ms: float = 0.0
    total_cost_usd: float = 0.0
    eval_items_count: int | None = None
    breakdown_by_clause_type: dict[str, float] = Field(default_factory=dict)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ExperimentResultDTO:
        results = row.get("results") or {}
        if isinstance(results, str):
            import json

            try:
                results = json.loads(results)
            except json.JSONDecodeError:
                results = {}
        return cls(
            experiment_id=str(row.get("experiment_id") or row.get("id") or ""),
            f1_score=float(results.get("f1_score") or results.get("f1") or 0.0),
            precision=float(results.get("precision") or 0.0),
            recall=float(results.get("recall") or 0.0),
            avg_latency_ms=float(results.get("avg_latency_ms") or results.get("latency_ms") or 0.0),
            total_cost_usd=float(results.get("total_cost_usd") or results.get("cost_usd") or 0.0),
            eval_items_count=results.get("eval_items_count"),
            breakdown_by_clause_type=dict(results.get("breakdown_by_clause_type") or {}),
        )


def _map_campaign_status(raw: str) -> str:
    return {
        "draft": "active",
        "active": "active",
        "running": "active",
        "completed": "completed",
        "archived": "archived",
    }.get(raw, raw)


def _map_experiment_status(raw: str) -> str:
    return {
        "queued": "configured",
        "configured": "configured",
        "running": "running",
        "succeeded": "completed",
        "completed": "completed",
        "failed": "failed",
    }.get(raw, raw)


__all__ = [
    "CampaignStatus",
    "CreateCampaignRequestDTO",
    "CreateCandidateRequestDTO",
    "CreateExperimentRequestDTO",
    "ExperimentResultDTO",
    "ExperimentStatus",
    "OptimizationCampaignDTO",
    "OptimizationCandidateDTO",
    "OptimizationExperimentDTO",
    "TargetMetric",
]
