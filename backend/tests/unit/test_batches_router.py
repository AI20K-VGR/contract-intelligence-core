"""Unit tests for Phase 4 Batches endpoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from contract_intelligence.contract.infrastructure.persistence.batch_service import (
    BatchService,
)
from contract_intelligence.main import app
from contract_intelligence.shared.auth.schemas import AuthenticatedUser
from contract_intelligence.shared.exceptions import InvalidStateTransition, NotFoundError

# asyncio mode=AUTO in pyproject — no module-level asyncio mark needed


def _operator() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="usr_op",
        tenant_id="tenant_test",
        email="op@test.com",
        display_name="Op",
        role="OPERATOR",
    )


@pytest_asyncio.fixture
async def mock_svc() -> AsyncMock:
    return AsyncMock(spec=BatchService)


@pytest_asyncio.fixture
async def client(mock_svc: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    from contract_intelligence.contract.interfaces.api.dependencies_admin import (
        get_batch_service,
    )
    from contract_intelligence.shared.auth import get_current_user
    from contract_intelligence.shared.auth.tenant import get_tenant_id

    app.dependency_overrides[get_batch_service] = lambda: mock_svc
    app.dependency_overrides[get_current_user] = lambda: _operator()
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_test"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestCreateBatch:
    async def test_multipart_returns_202(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.create_batch.return_value = {
            "batch_id": "bat_1",
            "dossier_count": 2,
            "dossier_ids": ["dos_a", "dos_b"],
            "job_ids": ["job_a", "job_b"],
        }
        manifest = b"dossier_name,file,role,order\nA,a.pdf,CONTRACT,1\nB,b.pdf,CONTRACT,1\n"
        resp = await client.post(
            "/api/v1/batches",
            files={
                "manifest": ("manifest.csv", manifest, "text/csv"),
                "archive": ("batch.zip", b"PK\x03\x04fake", "application/zip"),
            },
        )
        assert resp.status_code == 202
        body = resp.json()["data"]
        assert body["batch_id"] == "bat_1"
        assert body["dossier_count"] == 2


class TestListBatches:
    async def test_maps_running_to_processing(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.list_batches.return_value = (
            [
                {
                    "batch_id": "bat_1",
                    "status": "running",
                    "total_dossiers": 3,
                    "succeeded": 1,
                    "failed": 0,
                    "created_at": datetime(2026, 1, 1, tzinfo=UTC),
                }
            ],
            1,
        )
        resp = await client.get("/api/v1/batches")
        assert resp.status_code == 200
        assert resp.json()["data"][0]["status"] == "processing"
        assert resp.json()["meta"]["total"] == 1


class TestCancelBatch:
    async def test_cancel_ok(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.cancel_batch.return_value = {
            "batch_id": "bat_1",
            "status": "cancelled",
            "total_dossiers": 1,
            "succeeded": 0,
            "failed": 0,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "dossiers": [],
        }
        resp = await client.post("/api/v1/batches/bat_1/cancel")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "cancelled"
        # An OPERATOR changes only their own batch.
        mock_svc.cancel_batch.assert_awaited_once_with("bat_1", owner_id="usr_op")

    async def test_cancel_terminal_409(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.cancel_batch.side_effect = InvalidStateTransition(
            from_state="completed",
            to_state="cancelled",
            entity="Batch",
        )
        resp = await client.post("/api/v1/batches/bat_1/cancel")
        assert resp.status_code == 409


class TestBatchServiceParseManifest:
    def test_parse_unique_names(self) -> None:
        csv_bytes = (
            b"dossier_name,file,role,order\n"
            b"A,a.pdf,CONTRACT,1\n"
            b"A,b.pdf,APPENDIX,2\n"
            b"B,c.pdf,CONTRACT,1\n"
        )
        names = BatchService._parse_manifest(csv_bytes)
        assert names == ["A", "B"]

    def test_parse_missing_column(self) -> None:
        with pytest.raises(ValueError, match="dossier_name"):
            BatchService._parse_manifest(b"file,role\nx.pdf,CONTRACT\n")


_BATCH_ROW = {
    "batch_id": "bat_1",
    "status": "running",
    "total_dossiers": 1,
    "succeeded": 0,
    "failed": 0,
    "created_at": datetime(2026, 1, 1, tzinfo=UTC),
    "dossiers": [],
}


class TestBatchOwnership:
    async def test_operator_resume_is_limited_to_their_batches(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.resume_batch.return_value = _BATCH_ROW

        resp = await client.post("/api/v1/batches/bat_1/resume")

        assert resp.status_code == 200
        mock_svc.resume_batch.assert_awaited_once_with("bat_1", owner_id="usr_op")

    async def test_administrator_changes_any_batch(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        from contract_intelligence.shared.auth import get_current_user

        admin = AuthenticatedUser(
            user_id="usr_admin",
            tenant_id="tenant_test",
            email="admin@test.com",
            display_name="Admin",
            role="ADMINISTRATOR",
        )
        app.dependency_overrides[get_current_user] = lambda: admin
        mock_svc.cancel_batch.return_value = {**_BATCH_ROW, "status": "cancelled"}

        resp = await client.post("/api/v1/batches/bat_1/cancel")

        assert resp.status_code == 200
        mock_svc.cancel_batch.assert_awaited_once_with("bat_1", owner_id=None)

    @pytest.mark.parametrize("action", ["cancel_batch", "resume_batch"])
    async def test_service_hides_another_users_batch(self, action: str) -> None:
        batch = SimpleNamespace(created_by="usr_other", status="paused")
        svc = BatchService(session=AsyncMock(), tenant_id="tenant_test")
        svc._get_orm = AsyncMock(return_value=batch)  # type: ignore[method-assign]  # noqa: SLF001

        with pytest.raises(NotFoundError):
            await getattr(svc, action)("bat_1", owner_id="usr_op")
        assert batch.status == "paused"
