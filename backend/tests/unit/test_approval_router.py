"""Unit tests for Phase 5 Approval endpoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from contract_intelligence.contract.application.dtos.dossier_dtos import DossierDetailDTO
from contract_intelligence.main import app
from contract_intelligence.review.application.dtos.approval_dtos import ExternalApprovalGrantDTO
from contract_intelligence.review.application.services.approval_service import ApprovalService
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


def _dossier(**overrides: object) -> DossierDetailDTO:
    base: dict[str, object] = {
        "id": "dos_1",
        "name": "Contract A",
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
        "latest_job_status": "reviewed",
    }
    base.update(overrides)
    return DossierDetailDTO.model_validate(base)


def _grant(**overrides: object) -> ExternalApprovalGrantDTO:
    base: dict[str, object] = {
        "id": "eag_1",
        "dossier_id": "dos_1",
        "provider": "docusign",
        "status": "pending",
        "approver_email": "boss@corp.com",
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    base.update(overrides)
    return ExternalApprovalGrantDTO.model_validate(base)


@pytest_asyncio.fixture
async def mock_svc() -> AsyncMock:
    return AsyncMock(spec=ApprovalService)


@pytest_asyncio.fixture
async def client(mock_svc: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    from contract_intelligence.review.interfaces.api.dependencies_approval import (
        get_approval_service,
        require_approval_access,
        require_external_approval_access,
        require_external_approval_read_access,
        require_lock_access,
    )
    from contract_intelligence.shared.auth import get_current_user
    from contract_intelligence.shared.auth.tenant import get_tenant_id

    app.dependency_overrides[get_approval_service] = lambda: mock_svc
    app.dependency_overrides[require_approval_access] = lambda: None
    app.dependency_overrides[require_lock_access] = lambda: None
    app.dependency_overrides[require_external_approval_access] = lambda: None
    app.dependency_overrides[require_external_approval_read_access] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: _admin()
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_test"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestLock:
    async def test_lock_ok(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.lock_dossier.return_value = _dossier()
        resp = await client.post("/api/v1/dossiers/dos_1/lock")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == "dos_1"

    async def test_lock_already_locked_409(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.lock_dossier.side_effect = InvalidStateTransition(
            from_state="locked", to_state="locked", entity="Dossier"
        )
        resp = await client.post("/api/v1/dossiers/dos_1/lock")
        assert resp.status_code == 409


class TestApprove:
    async def test_approve_ok(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.approve_dossier.return_value = _dossier(latest_job_status="approved")
        resp = await client.post("/api/v1/dossiers/dos_1/approve")

        assert resp.status_code == 200
        assert resp.json()["data"]["latest_job_status"] == "approved"
        mock_svc.approve_dossier.assert_awaited_once_with("dos_1", "usr_admin", comment=None)

    async def test_approve_precondition_409(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.approve_dossier.side_effect = InvalidStateTransition(
            from_state="pending_review", to_state="approved", entity="Dossier"
        )
        resp = await client.post("/api/v1/dossiers/dos_1/approve")

        assert resp.status_code == 409


class TestExternalApproval:
    async def test_create_201(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.create_external_approval.return_value = _grant()
        resp = await client.post(
            "/api/v1/dossiers/dos_1/external-approvals",
            json={
                "provider": "docusign",
                "approver_email": "boss@corp.com",
                "expires_in_hours": 48,
            },
        )
        assert resp.status_code == 201
        body = resp.json()["data"]
        assert body["provider"] == "docusign"
        assert body["approver_email"] == "boss@corp.com"
        assert "token" not in body

    async def test_create_409(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.create_external_approval.side_effect = InvalidStateTransition(
            from_state="unapproved", to_state="external_approval", entity="Dossier"
        )
        resp = await client.post(
            "/api/v1/dossiers/dos_1/external-approvals",
            json={"provider": "docusign", "approver_email": "a@b.com"},
        )
        assert resp.status_code == 409

    async def test_callback_by_grant_id(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.handle_external_callback.return_value = _grant(status="approved")
        resp = await client.post(
            "/api/v1/external-approvals/callback",
            json={
                "grant_id": "eag_1",
                "status": "approved",
                "external_reference_id": "ds_99",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "approved"
        kwargs = mock_svc.handle_external_callback.call_args.kwargs
        assert kwargs["grant_id"] == "eag_1"
