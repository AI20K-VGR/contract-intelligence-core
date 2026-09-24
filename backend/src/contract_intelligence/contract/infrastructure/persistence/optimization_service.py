"""Optimization service — pure ORM CRUD wrapper, lives in infrastructure.

Layer: infrastructure/persistence (returns dicts, no domain entities).
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.infrastructure.persistence.orm_others import (
    OptimizationCampaignORM,
    OptimizationCandidateORM,
    OptimizationExperimentORM,
)
from contract_intelligence.shared.base import new_ulid, utcnow
from contract_intelligence.shared.exceptions import InvalidStateTransition, NotFoundError


class OptimizationService:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    # ----- Campaigns ---------------------------------------------------------

    async def list_campaigns(self) -> list[dict[str, Any]]:
        stmt = (
            select(OptimizationCampaignORM)
            .where(OptimizationCampaignORM.tenant_id == self._tenant_id)
            .order_by(OptimizationCampaignORM.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._campaign_to_dict(c) for c in result.scalars().all()]

    async def get_campaign(self, campaign_id: str) -> dict[str, Any]:
        orm = await self._get_campaign_orm(campaign_id)
        return self._campaign_to_dict(orm)

    async def create_campaign(
        self,
        *,
        name: str,
        target_metric: str,
        baseline_score: float,
        created_by: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        orm = OptimizationCampaignORM(
            id=new_ulid("cmp_"),
            tenant_id=self._tenant_id,
            name=name,
            goal=description or "",
            target_metric=target_metric,
            status="active",
            created_by=created_by,
        )
        self._session.add(orm)
        await self._session.flush()
        data = self._campaign_to_dict(orm)
        data["baseline_score"] = baseline_score
        data["description"] = description
        return data

    # ----- Candidates --------------------------------------------------------

    async def list_candidates(self, campaign_id: str | None = None) -> list[dict[str, Any]]:
        stmt = select(OptimizationCandidateORM).where(
            OptimizationCandidateORM.tenant_id == self._tenant_id
        )
        if campaign_id:
            stmt = stmt.where(OptimizationCandidateORM.campaign_id == campaign_id)
        result = await self._session.execute(stmt)
        return [self._candidate_to_dict(c) for c in result.scalars().all()]

    async def get_candidate(self, candidate_id: str) -> dict[str, Any]:
        orm = await self._get_candidate_orm(candidate_id)
        return self._candidate_to_dict(orm)

    async def create_candidate(
        self,
        *,
        campaign_id: str,
        name: str,
        prompt_template: str,
        model_name: str,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        # Ensure campaign exists
        await self._get_campaign_orm(campaign_id)
        hyper = {"model_name": model_name, "temperature": temperature}
        orm = OptimizationCandidateORM(
            id=new_ulid("cnd_"),
            tenant_id=self._tenant_id,
            campaign_id=campaign_id,
            name=name,
            prompt_version=prompt_template,
            hyperparameters=json.dumps(hyper),
            is_promoted=False,
        )
        self._session.add(orm)
        await self._session.flush()
        return self._candidate_to_dict(orm)

    async def promote_candidate(self, candidate_id: str) -> dict[str, Any]:
        orm = await self._get_candidate_orm(candidate_id)
        already = orm.is_promoted is True or str(orm.is_promoted).lower() == "true"
        if already:
            raise InvalidStateTransition(
                from_state="active_production",
                to_state="active_production",
                entity="OptimizationCandidate",
            )
        orm.is_promoted = True
        await self._session.flush()
        return self._candidate_to_dict(orm)

    # ----- Experiments -------------------------------------------------------

    async def list_experiments(self, campaign_id: str | None = None) -> list[dict[str, Any]]:
        stmt = select(OptimizationExperimentORM).where(
            OptimizationExperimentORM.tenant_id == self._tenant_id
        )
        if campaign_id:
            stmt = stmt.where(OptimizationExperimentORM.campaign_id == campaign_id)
        result = await self._session.execute(stmt)
        return [self._experiment_to_dict(e) for e in result.scalars().all()]

    async def create_experiment(
        self,
        *,
        campaign_id: str,
        candidate_id: str,
        golden_dataset_version: str,
        sample_size: int = 100,
    ) -> dict[str, Any]:
        await self._get_campaign_orm(campaign_id)
        await self._get_candidate_orm(candidate_id)
        orm = OptimizationExperimentORM(
            id=new_ulid("exp_"),
            tenant_id=self._tenant_id,
            campaign_id=campaign_id,
            candidate_id=candidate_id,
            benchmark_set_name=golden_dataset_version,
            status="queued",
            results=json.dumps({"sample_size": sample_size}),
        )
        self._session.add(orm)
        await self._session.flush()
        return self._experiment_to_dict(orm)

    async def run_experiment(self, experiment_id: str) -> dict[str, Any]:
        orm = await self._get_experiment_orm(experiment_id)
        if orm.status in ("running", "succeeded", "completed", "failed"):
            raise InvalidStateTransition(
                from_state=orm.status,
                to_state="running",
                entity="OptimizationExperiment",
            )
        orm.status = "running"
        orm.started_at = utcnow()
        # Stub results for demo — filled when experiment completes
        if not orm.results:
            orm.results = json.dumps(
                {
                    "f1_score": 0.0,
                    "precision": 0.0,
                    "recall": 0.0,
                    "avg_latency_ms": 0.0,
                    "total_cost_usd": 0.0,
                }
            )
        await self._session.flush()
        return self._experiment_to_dict(orm)

    async def get_experiment_results(self, experiment_id: str) -> dict[str, Any]:
        orm = await self._get_experiment_orm(experiment_id)
        data = self._experiment_to_dict(orm)
        data["results"] = json.loads(orm.results) if orm.results else {}
        return data

    # ----- Helpers -----------------------------------------------------------

    async def _get_campaign_orm(self, campaign_id: str) -> OptimizationCampaignORM:
        stmt = select(OptimizationCampaignORM).where(
            OptimizationCampaignORM.id == campaign_id,
            OptimizationCampaignORM.tenant_id == self._tenant_id,
        )
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            raise NotFoundError(entity_type="OptimizationCampaign", entity_id=campaign_id)
        return orm

    async def _get_candidate_orm(self, candidate_id: str) -> OptimizationCandidateORM:
        stmt = select(OptimizationCandidateORM).where(
            OptimizationCandidateORM.id == candidate_id,
            OptimizationCandidateORM.tenant_id == self._tenant_id,
        )
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            raise NotFoundError(entity_type="OptimizationCandidate", entity_id=candidate_id)
        return orm

    async def _get_experiment_orm(self, experiment_id: str) -> OptimizationExperimentORM:
        stmt = select(OptimizationExperimentORM).where(
            OptimizationExperimentORM.id == experiment_id,
            OptimizationExperimentORM.tenant_id == self._tenant_id,
        )
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            raise NotFoundError(entity_type="OptimizationExperiment", entity_id=experiment_id)
        return orm

    @staticmethod
    def _campaign_to_dict(c: OptimizationCampaignORM) -> dict[str, Any]:
        return {
            "id": c.id,
            "campaign_id": c.id,
            "name": c.name,
            "goal": c.goal,
            "description": c.goal,
            "target_metric": c.target_metric,
            "baseline_score": 0.0,
            "current_best_score": None,
            "status": c.status,
            "created_at": c.created_at,
        }

    @staticmethod
    def _candidate_to_dict(c: OptimizationCandidateORM) -> dict[str, Any]:
        hyper: dict[str, Any] = {}
        if c.hyperparameters:
            try:
                hyper = json.loads(c.hyperparameters)
            except json.JSONDecodeError:
                hyper = {}
        metrics: dict[str, Any] = {}
        if c.metrics:
            try:
                metrics = json.loads(c.metrics)
            except json.JSONDecodeError:
                metrics = {}
        promoted = c.is_promoted is True or str(c.is_promoted).lower() == "true"
        return {
            "id": c.id,
            "candidate_id": c.id,
            "campaign_id": c.campaign_id,
            "name": c.name,
            "prompt_version": c.prompt_version,
            "prompt_template": c.prompt_version,
            "hyperparameters": hyper,
            "model_name": hyper.get("model_name", "unknown"),
            "temperature": float(hyper.get("temperature", 0.0)),
            "is_promoted": promoted,
            "is_active_production": promoted,
            "metrics": metrics,
            "benchmark_f1": metrics.get("f1"),
            "created_at": c.created_at,
        }

    @staticmethod
    def _experiment_to_dict(e: OptimizationExperimentORM) -> dict[str, Any]:
        return {
            "id": e.id,
            "experiment_id": e.id,
            "campaign_id": e.campaign_id,
            "candidate_id": e.candidate_id,
            "benchmark_set_name": e.benchmark_set_name,
            "golden_dataset_version": e.benchmark_set_name,
            "status": e.status,
            "results": json.loads(e.results) if e.results else {},
            "started_at": e.started_at,
            "finished_at": e.finished_at,
            "completed_at": e.finished_at,
            "created_at": e.created_at,
        }


__all__ = ["OptimizationService"]
