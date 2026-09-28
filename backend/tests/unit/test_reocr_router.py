"""Unit tests for Phase 4 Re-OCR endpoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from contract_intelligence.extraction.application.dtos.reocr_dtos import ReOcrRequestRecordDTO
from contract_intelligence.extraction.application.services.reocr_service import ReOcrService
from contract_intelligence.main import app
from contract_intelligence.shared.auth.schemas import AuthenticatedUser

pytestmark = pytest.mark.asyncio


def _operator() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="usr_op",
        tenant_id="tenant_test",
        email="op@test.com",
        display_name="Op",
        role="OPERATOR",
    )


def _record(**overrides: object) -> ReOcrRequestRecordDTO:
    base: dict[str, object] = {
        "id": "req_1",
        "document_id": "doc_1",
        "profile": "high_res_binarize",
        "page_numbers": [1, 2],
        "status": "processing",
        "requested_by": "usr_op",
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "job_id": "ai_job_1",
        "reason": "blurry",
    }
    base.update(overrides)
    return ReOcrRequestRecordDTO.model_validate(base)


@pytest_asyncio.fixture
async def mock_svc() -> AsyncMock:
    return AsyncMock(spec=ReOcrService)


@pytest_asyncio.fixture
async def client(mock_svc: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    from contract_intelligence.extraction.interfaces.api.dependencies_reocr import (
        get_reocr_service,
    )
    from contract_intelligence.shared.auth import get_current_user
    from contract_intelligence.shared.auth.tenant import get_tenant_id

    app.dependency_overrides[get_reocr_service] = lambda: mock_svc
    app.dependency_overrides[get_current_user] = lambda: _operator()
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_test"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestCreateReOcr:
    async def test_returns_202(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.create_request.return_value = _record()
        resp = await client.post(
            "/api/v1/documents/doc_1/re-ocr",
            json={
                "profile": "high_res_binarize",
                "page_numbers": [1, 2],
                "reason": "blurry",
            },
        )
        assert resp.status_code == 202
        body = resp.json()["data"]
        assert body["profile"] == "high_res_binarize"
        assert body["page_numbers"] == [1, 2]
        assert body["status"] == "processing"
        kwargs = mock_svc.create_request.call_args.kwargs
        assert kwargs["profile"] == "high_res_binarize"
        assert kwargs["page_numbers"] == [1, 2]

    async def test_rejects_invalid_profile(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        resp = await client.post(
            "/api/v1/documents/doc_1/re-ocr",
            json={"profile": "unknown_engine", "page_numbers": [1]},
        )
        assert resp.status_code == 422


class TestListReOcr:
    async def test_list_returns_records(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.list_requests.return_value = [_record(status="completed")]
        resp = await client.get("/api/v1/documents/doc_1/re-ocr-requests")
        assert resp.status_code == 200
        assert resp.json()["data"][0]["status"] == "completed"
