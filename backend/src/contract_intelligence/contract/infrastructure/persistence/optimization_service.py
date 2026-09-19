"""Optimization service — pure ORM CRUD wrapper, lives in infrastructure.

Layer: infrastructure/persistence (returns dicts, no domain entities).
Moved from contract.application.services để tuân thủ DDD dependency rule
(application layer KHÔNG được import infrastructure).
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
from contract_intelligence.shared.base import new_ulid
from contract_intelligence.shared.exceptions import NotFoundError


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
        return [
            {
                "id": c.id,
                "name": c.name,
                "goal": c.goal,
                "target_metric": c.target_metric,
                "status": c.status,
                "created_at": c.created_at.isoformat(),
            }
            for c in result.scalars().all()
        ]

    async def get_campaign(self, campaign_id: str) -> dict[str, Any]:
        stmt = select(OptimizationCampaignORM).where(
            OptimizationCampaignORM.id == campaign_id,
            OptimizationCampaignORM.tenant_id == self._tenant_id,
        )
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            raise NotFoundError(entity_type="OptimizationCampaign", entity_id=campaign_id)
        return {
            "id": orm.id,
            "name": orm.name,
            "goal": orm.goal,
            "target_metric": orm.target_metric,
            "status": orm.status,
            "created_at": orm.created_at.isoformat(),
        }

    async def create_campaign(
        self, *, name: str, goal: str, target_metric: str, created_by: str
    ) -> dict[str, Any]:
        orm = OptimizationCampaignORM(
            id=new_ulid("opc_"),
            tenant_id=self._tenant_id,
            name=name,
            goal=goal,
            target_metric=target_metric,
            created_by=created_by,
        )
        self._session.add(orm)
        await self._session.flush()
        return {
            "id": orm.id,
            "name": orm.name,
            "goal": orm.goal,
            "target_metric": orm.target_metric,
            "status": orm.status,
        }

    # ----- Candidates --------------------------------------------------------

    async def list_candidates(self, campaign_id: str) -> list[dict[str, Any]]:
        stmt = select(OptimizationCandidateORM).where(
            OptimizationCandidateORM.campaign_id == campaign_id,
            OptimizationCandidateORM.tenant_id == self._tenant_id,
        )
        result = await self._session.execute(stmt)
        return [
            {
                "id": c.id,
                "campaign_id": c.campaign_id,
                "name": c.name,
                "prompt_version": c.prompt_version,
                "hyperparameters": json.loads(c.hyperparameters) if c.hyperparameters else {},
                "is_promoted": c.is_promoted == "true",  # type: ignore[comparison-overlap]
                "metrics": json.loads(c.metrics) if c.metrics else {},
            }
            for c in result.scalars().all()
        ]

    async def create_candidate(
        self,
        *,
        campaign_id: str,
        name: str,
        prompt_version: str,
        hyperparameters: dict[str, Any],
    ) -> dict[str, Any]:
        orm = OptimizationCandidateORM(
            id=new_ulid("opcd_"),
            tenant_id=self._tenant_id,
            campaign_id=campaign_id,
            name=name,
            prompt_version=prompt_version,
            hyperparameters=json.dumps(hyperparameters),
        )
        self._session.add(orm)
        await self._session.flush()
        return {
            "id": orm.id,
            "campaign_id": orm.campaign_id,
            "name": orm.name,
            "prompt_version": orm.prompt_version,
        }

    async def promote_candidate(self, candidate_id: str) -> dict[str, Any]:
        stmt = select(OptimizationCandidateORM).where(
            OptimizationCandidateORM.id == candidate_id,
            OptimizationCandidateORM.tenant_id == self._tenant_id,
        )
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            raise NotFoundError(entity_type="OptimizationCandidate", entity_id=candidate_id)
        orm.is_promoted = True
        await self._session.flush()
        return {"id": orm.id, "is_promoted": True}

    # ----- Experiments -------------------------------------------------------

    async def list_experiments(self, campaign_id: str) -> list[dict[str, Any]]:
        stmt = select(OptimizationExperimentORM).where(
            OptimizationExperimentORM.campaign_id == campaign_id,
            OptimizationExperimentORM.tenant_id == self._tenant_id,
        )
        result = await self._session.execute(stmt)
        return [
            {
                "id": e.id,
                "campaign_id": e.campaign_id,
                "candidate_id": e.candidate_id,
                "benchmark_set_name": e.benchmark_set_name,
                "status": e.status,
                "results": json.loads(e.results) if e.results else {},
            }
            for e in result.scalars().all()
        ]

    async def create_experiment(
        self,
        *,
        campaign_id: str,
        candidate_id: str,
        benchmark_set_name: str,
    ) -> dict[str, Any]:
        orm = OptimizationExperimentORM(
            id=new_ulid("opex_"),
            tenant_id=self._tenant_id,
            campaign_id=campaign_id,
            candidate_id=candidate_id,
            benchmark_set_name=benchmark_set_name,
            status="queued",
        )
        self._session.add(orm)
        await self._session.flush()
        return {
            "id": orm.id,
            "campaign_id": orm.campaign_id,
            "candidate_id": orm.candidate_id,
            "status": orm.status,
        }

    async def run_experiment(self, experiment_id: str) -> dict[str, Any]:
        stmt = select(OptimizationExperimentORM).where(
            OptimizationExperimentORM.id == experiment_id,
            OptimizationExperimentORM.tenant_id == self._tenant_id,
        )
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            raise NotFoundError(entity_type="OptimizationExperiment", entity_id=experiment_id)
        orm.status = "running"
        await self._session.flush()
        return {"id": orm.id, "status": orm.status}

    async def get_experiment_results(self, experiment_id: str) -> dict[str, Any]:
        stmt = select(OptimizationExperimentORM).where(
            OptimizationExperimentORM.id == experiment_id,
            OptimizationExperimentORM.tenant_id == self._tenant_id,
        )
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            raise NotFoundError(entity_type="OptimizationExperiment", entity_id=experiment_id)
        return {
            "id": orm.id,
            "status": orm.status,
            "results": json.loads(orm.results) if orm.results else {},
            "started_at": orm.started_at.isoformat() if orm.started_at else None,
            "finished_at": orm.finished_at.isoformat() if orm.finished_at else None,
        }


__all__ = ["OptimizationService"]
