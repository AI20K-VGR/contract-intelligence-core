"""Unit tests for Phase 2 Conflict endpoints (findings + conflicts)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from contract_intelligence.conflict.application.dtos.finding_dtos import FindingDTO
from contract_intelligence.conflict.application.services.conflict_service import (
    ConflictService,
)
from contract_intelligence.main import app
from contract_intelligence.shared.auth.schemas import AuthenticatedUser
from contract_intelligence.shared.exceptions import NotFoundError

pytestmark = pytest.mark.asyncio


def _reviewer() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="usr_rev",
        tenant_id="tenant_test",
        email="rev@test.com",
        display_name="Rev",
        role="REVIEWER",
    )


def _finding(**overrides: object) -> FindingDTO:
    base = {
        "id": "fnd_1",
        "dossier_id": "dos_1",
        "run_id": "run_1",
        "finding_type": "structured",
        "scope": "contract_annex",
        "key_or_topic": "price.total",
        "disposition": "comparable_difference",
        "severity": "high",
        "confidence": 0.4,
        "rationale": "Mismatch",
        "method": "rule",
        "sides": [
            {
                "side": "a",
                "document_id": "doc_c",
                "document_role": "contract",
                "fact_id": "fct_a",
            },
            {
                "side": "b",
                "document_id": "doc_a",
                "document_role": "annex",
                "fact_id": "fct_b",
            },
        ],
    }
    base.update(overrides)
    return FindingDTO.from_row(base)


@pytest_asyncio.fixture
async def mock_svc() -> AsyncMock:
    return AsyncMock(spec=ConflictService)


@pytest_asyncio.fixture
async def client(mock_svc: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    from contract_intelligence.conflict.interfaces.api.dependencies import (
        get_conflict_service,
    )
    from contract_intelligence.shared.auth import get_current_user
    from contract_intelligence.shared.auth.tenant import get_tenant_id

    app.dependency_overrides[get_conflict_service] = lambda: mock_svc
    app.dependency_overrides[get_current_user] = lambda: _reviewer()
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_test"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestListFindings:
    async def test_returns_200_with_envelope(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.list_findings.return_value = ([_finding()], 1)
        resp = await client.get("/api/v1/dossiers/dos_1/findings")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["disposition"] == "comparable_difference"
        assert len(body["data"][0]["sides"]) == 2
        assert body["meta"]["total"] == 1

    async def test_passes_filters(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.list_findings.return_value = ([], 0)
        await client.get(
            "/api/v1/dossiers/dos_1/findings",
            params={
                "disposition": "comparable_match",
                "scope": "within_document",
                "limit": 10,
            },
        )
        kwargs = mock_svc.list_findings.call_args.kwargs
        assert kwargs["disposition"] == "comparable_match"
        assert kwargs["scope"] == "within_document"
        assert kwargs["limit"] == 10


class TestListConflicts:
    async def test_returns_conflict_subset(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.list_conflicts.return_value = ([_finding()], 1)
        resp = await client.get("/api/v1/dossiers/dos_1/conflicts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"][0]["id"] == "fnd_1"
        assert body["meta"]["total"] == 1
        mock_svc.list_conflicts.assert_called_once()


class TestGetFinding:
    async def test_returns_detail(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.get_finding.return_value = _finding(id="fnd_x")
        resp = await client.get("/api/v1/findings/fnd_x")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == "fnd_x"

    async def test_returns_404(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.get_finding.side_effect = NotFoundError(entity_type="Finding", entity_id="missing")
        resp = await client.get("/api/v1/findings/missing")
        assert resp.status_code == 404
