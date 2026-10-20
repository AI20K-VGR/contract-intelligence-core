"""Unit tests for Phase 5 Optimization endpoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from contract_intelligence.contract.infrastructure.persistence.optimization_service import (
    OptimizationService,
)
from contract_intelligence.main import app
from contract_intelligence.shared.auth.schemas import AuthenticatedUser
from contract_intelligence.shared.exceptions import InvalidStateTransition

# asyncio mode=AUTO


def _admin() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="usr_admin",
        tenant_id="tenant_test",
        email="admin@test.com",
        display_name="Admin",
        role="ADMINISTRATOR",
    )


@pytest_asyncio.fixture
async def mock_svc() -> AsyncMock:
    return AsyncMock(spec=OptimizationService)


@pytest_asyncio.fixture
async def client(mock_svc: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    from contract_intelligence.contract.interfaces.api.dependencies_admin import (
        get_optimization_service,
    )
    from contract_intelligence.shared.auth import get_current_user
    from contract_intelligence.shared.auth.tenant import get_tenant_id

    app.dependency_overrides[get_optimization_service] = lambda: mock_svc
    app.dependency_overrides[get_current_user] = lambda: _admin()
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_test"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestCampaigns:
    async def test_create_campaign(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.create_campaign.return_value = {
            "campaign_id": "cmp_1",
            "name": "F1 boost",
            "description": "Improve F1",
            "target_metric": "f1_score",
            "baseline_score": 0.82,
            "status": "active",
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        }
        resp = await client.post(
            "/api/v1/optimization/campaigns",
            json={
                "name": "F1 boost",
                "description": "Improve F1",
                "target_metric": "f1_score",
                "baseline_score": 0.82,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["campaign_id"] == "cmp_1"
        assert resp.json()["data"]["target_metric"] == "f1_score"


class TestCandidates:
    async def test_create_and_get(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        row = {
            "candidate_id": "cnd_1",
            "campaign_id": "cmp_1",
            "name": "v2",
            "prompt_template": "Extract...",
            "model_name": "gpt-4o",
            "temperature": 0.0,
            "is_active_production": False,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        }
        mock_svc.create_candidate.return_value = row
        mock_svc.get_candidate.return_value = row
        create = await client.post(
            "/api/v1/optimization/candidates",
            json={
                "campaign_id": "cmp_1",
                "name": "v2",
                "prompt_template": "Extract...",
                "model_name": "gpt-4o",
            },
        )
        assert create.status_code == 201
        assert create.json()["data"]["candidate_id"] == "cnd_1"

        get = await client.get("/api/v1/optimization/candidates/cnd_1")
        assert get.status_code == 200
        assert get.json()["data"]["prompt_template"] == "Extract..."

    async def test_promote_409(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.promote_candidate.side_effect = InvalidStateTransition(
            from_state="active_production",
            to_state="active_production",
            entity="OptimizationCandidate",
        )
        resp = await client.post("/api/v1/optimization/candidates/cnd_1/promote")
        assert resp.status_code == 409


class TestExperiments:
    async def test_run_202(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.run_experiment.return_value = {
            "experiment_id": "exp_1",
            "campaign_id": "cmp_1",
            "candidate_id": "cnd_1",
            "golden_dataset_version": "gd_v1",
            "status": "running",
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        }
        resp = await client.post("/api/v1/optimization/experiments/exp_1/run")
        assert resp.status_code == 202
        assert resp.json()["data"]["status"] == "running"

    async def test_run_409(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.run_experiment.side_effect = InvalidStateTransition(
            from_state="running", to_state="running", entity="OptimizationExperiment"
        )
        resp = await client.post("/api/v1/optimization/experiments/exp_1/run")
        assert resp.status_code == 409

    async def test_results(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.get_experiment_results.return_value = {
            "experiment_id": "exp_1",
            "results": {
                "f1_score": 0.91,
                "precision": 0.9,
                "recall": 0.92,
                "avg_latency_ms": 120.5,
                "total_cost_usd": 1.25,
            },
        }
        resp = await client.get("/api/v1/optimization/experiments/exp_1/results")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["f1_score"] == 0.91
        assert data["total_cost_usd"] == 1.25
