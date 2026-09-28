"""Unit tests for Phase 4 runs / reprocess endpoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from contract_intelligence.extraction.application.dtos.run_dtos import (
    ReprocessAcceptedDTO,
)
from contract_intelligence.extraction.application.services.extraction_service import (
    ExtractionService,
)
from contract_intelligence.extraction.domain.entities.pipeline_run import (
    PipelineRun,
    PipelineRunStatus,
)
from contract_intelligence.main import app
from contract_intelligence.shared.auth.schemas import AuthenticatedUser
from contract_intelligence.shared.exceptions import InvalidStateTransition

pytestmark = pytest.mark.asyncio


def _operator() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="usr_op",
        tenant_id="tenant_test",
        email="op@test.com",
        display_name="Op",
        role="OPERATOR",
    )


def _run(**overrides: object) -> PipelineRun:
    base: dict[str, object] = {
        "id": "run_1",
        "tenant_id": "tenant_test",
        "dossier_id": "dos_1",
        "status": PipelineRunStatus.QUEUED,
        "pipeline_version": "v1.0.0",
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    base.update(overrides)
    return PipelineRun(**base)  # type: ignore[arg-type]


@pytest_asyncio.fixture
async def mock_svc() -> AsyncMock:
    return AsyncMock(spec=ExtractionService)


@pytest_asyncio.fixture
async def client(mock_svc: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    from contract_intelligence.extraction.interfaces.api.dependencies import (
        get_extraction_service,
    )
    from contract_intelligence.shared.auth import get_current_user
    from contract_intelligence.shared.auth.tenant import get_tenant_id

    mock_svc.to_summary = ExtractionService.to_summary
    app.dependency_overrides[get_extraction_service] = lambda: mock_svc
    app.dependency_overrides[get_current_user] = lambda: _operator()
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_test"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestTriggerRun:
    async def test_returns_202_summary(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.trigger_pipeline_run.return_value = _run()
        resp = await client.post(
            "/api/v1/dossiers/dos_1/runs",
            json={"config_override": {"ocr_profile": "standard"}},
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["data"]["run_id"] == "run_1"
        assert body["data"]["status"] == "queued"
        mock_svc.trigger_pipeline_run.assert_called_once()
        kwargs = mock_svc.trigger_pipeline_run.call_args.kwargs
        assert kwargs["config_override"] == {"ocr_profile": "standard"}

    async def test_active_run_returns_409(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.trigger_pipeline_run.side_effect = InvalidStateTransition(
            from_state="active_run",
            to_state="queued",
            entity="PipelineRun",
        )
        resp = await client.post("/api/v1/dossiers/dos_1/runs")
        assert resp.status_code == 409


class TestReprocess:
    async def test_returns_202(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.reprocess_dossier.return_value = ReprocessAcceptedDTO(
            dossier_id="dos_1", job_id="run_new"
        )
        resp = await client.post("/api/v1/dossiers/dos_1/reprocess")
        assert resp.status_code == 202
        assert resp.json()["data"]["job_id"] == "run_new"


class TestListRuns:
    async def test_maps_status_and_meta(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.list_pipeline_runs.return_value = (
            [_run(status=PipelineRunStatus.SUCCEEDED)],
            1,
        )
        resp = await client.get("/api/v1/runs", params={"status": "completed"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"][0]["status"] == "completed"
        assert body["meta"]["total"] == 1
        mock_svc.list_pipeline_runs.assert_called_once()
        assert mock_svc.list_pipeline_runs.call_args.kwargs["status"] == "completed"


class TestCancelRun:
    async def test_cancel_ok(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.cancel_pipeline_run.return_value = _run(status=PipelineRunStatus.CANCELLED)
        resp = await client.post("/api/v1/runs/run_1/cancel")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "cancelled"

    async def test_cancel_terminal_409(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.cancel_pipeline_run.side_effect = InvalidStateTransition(
            from_state="succeeded",
            to_state="cancelled",
            entity="PipelineRun",
        )
        resp = await client.post("/api/v1/runs/run_1/cancel")
        assert resp.status_code == 409
