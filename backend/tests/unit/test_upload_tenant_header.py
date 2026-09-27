"""ST-035: POST /dossiers resolves the tenant from X-Tenant-Id and checks it against the JWT."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from contract_intelligence.main import app
from contract_intelligence.shared.auth import get_current_user
from contract_intelligence.shared.auth.schemas import AuthenticatedUser
from contract_intelligence.shared.persistence.session import get_async_session

OPERATOR = AuthenticatedUser(
    user_id="usr_op_01",
    tenant_id="tenant_test",
    email="operator@test.com",
    display_name="Operator",
    role="OPERATOR",
)
PDF = b"%PDF-1.4\n%%EOF\n"


async def _unused_session() -> AsyncGenerator[MagicMock, None]:
    yield MagicMock()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_current_user] = lambda: OPERATOR
    app.dependency_overrides[get_async_session] = _unused_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _upload(client: AsyncClient, headers: dict[str, str]) -> tuple[int, dict]:
    response = await client.post(
        "/api/v1/dossiers",
        files={"contract": ("c.pdf", PDF, "application/pdf"), "metadata": (None, "{}")},
        headers=headers,
    )
    return response.status_code, response.json()


@pytest.mark.asyncio
async def test_upload_without_tenant_header_is_rejected(client: AsyncClient) -> None:
    status, body = await _upload(client, {})
    assert status == 400
    assert body["detail"] == "X-Tenant-Id header is required"


@pytest.mark.asyncio
async def test_upload_with_foreign_tenant_header_is_rejected(client: AsyncClient) -> None:
    status, body = await _upload(client, {"X-Tenant-Id": "tenant_other"})
    assert status == 403
    assert body["error"]["code"] == "TENANT_MISMATCH"
