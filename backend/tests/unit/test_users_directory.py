"""GET /users/directory: who an operator may share a dossier with."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from contract_intelligence.infrastructure import keycloak_admin
from contract_intelligence.main import app
from contract_intelligence.shared.auth import get_current_user
from contract_intelligence.shared.auth.schemas import AuthenticatedUser

TENANT = "tenant_a"


def _kc_user(
    user_id: str,
    role: str,
    *,
    tenant: str | None = TENANT,
    enabled: bool = True,
    invited: bool = False,
) -> dict[str, Any]:
    return {
        "id": user_id,
        "email": f"{user_id}@example.com",
        "firstName": user_id.title(),
        "enabled": enabled,
        "requiredActions": ["UPDATE_PASSWORD"] if invited else [],
        "attributes": {"tenant_id": [tenant]} if tenant else {},
        "createdTimestamp": 1_760_000_000_000,
        "_role": role,
    }


class _FakeAdmin:
    def __init__(self) -> None:
        self.users = [
            _kc_user("olivia", "OPERATOR"),
            _kc_user("rita", "REVIEWER"),
            _kc_user("ray", "REVIEWER"),
            _kc_user("adam", "ADMINISTRATOR"),
            _kc_user("ivy", "REVIEWER", invited=True),
            _kc_user("dan", "REVIEWER", enabled=False),
            _kc_user("zoe", "REVIEWER", tenant="tenant_b"),
            _kc_user("nora", "REVIEWER", tenant=None),
        ]
        self.event_calls = 0

    def get_users(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        return self.users

    def get_realm_role_members(self, role: str, query: Any = None) -> list[dict[str, Any]]:
        return [user for user in self.users if user["_role"] == role]

    def get_realm_roles_of_user(self, user_id: str) -> list[dict[str, Any]]:
        return [{"name": next(u["_role"] for u in self.users if u["id"] == user_id)}]

    def get_events(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        self.event_calls += 1
        return []


def _principal(role: str, tenant: str = TENANT) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="caller",
        tenant_id=tenant,
        email="caller@example.com",
        display_name="Caller",
        role=role,
    )


@pytest.fixture
def admin(monkeypatch: pytest.MonkeyPatch) -> _FakeAdmin:
    fake = _FakeAdmin()
    monkeypatch.setattr(keycloak_admin, "_build_keycloak_admin", lambda: fake)
    return fake


@pytest_asyncio.fixture
async def client(admin: _FakeAdmin) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_current_user] = lambda: _principal("OPERATOR")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


def _as(role: str, tenant: str = TENANT) -> None:
    app.dependency_overrides[get_current_user] = lambda: _principal(role, tenant)


@pytest.mark.asyncio
async def test_operator_sees_active_members_of_their_tenant(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/directory")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["data"]] == ["adam", "olivia", "ray", "rita"]
    assert body["meta"]["total"] == 4


@pytest.mark.asyncio
async def test_entries_carry_no_admin_fields(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/directory")

    for item in response.json()["data"]:
        assert set(item) == {"id", "email", "display_name", "role"}


@pytest.mark.asyncio
async def test_other_tenant_invited_and_disabled_users_are_hidden(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/directory", params={"limit": 100})

    ids = {item["id"] for item in response.json()["data"]}
    assert ids.isdisjoint({"zoe", "ivy", "dan"})


@pytest.mark.asyncio
async def test_role_filter_lists_the_reviewers_to_assign(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/directory", params={"role": "REVIEWER"})

    data = response.json()["data"]
    assert [item["id"] for item in data] == ["ray", "rita"]
    assert {item["role"] for item in data} == {"REVIEWER"}


@pytest.mark.asyncio
async def test_search_and_pagination(client: AsyncClient) -> None:
    found = await client.get("/api/v1/users/directory", params={"q": "RITA"})
    paged = await client.get("/api/v1/users/directory", params={"limit": 2, "offset": 1})

    assert [item["id"] for item in found.json()["data"]] == ["rita"]
    assert [item["id"] for item in paged.json()["data"]] == ["olivia", "ray"]
    assert paged.json()["meta"]["total"] == 4


@pytest.mark.asyncio
async def test_other_tenant_caller_sees_only_their_own_members(client: AsyncClient) -> None:
    _as("OPERATOR", "tenant_b")

    response = await client.get("/api/v1/users/directory")

    assert [item["id"] for item in response.json()["data"]] == ["zoe"]


@pytest.mark.asyncio
async def test_user_without_a_tenant_is_listed_for_nobody(client: AsyncClient) -> None:
    own = await client.get("/api/v1/users/directory", params={"limit": 100})
    _as("OPERATOR", "tenant_b")
    other = await client.get("/api/v1/users/directory", params={"limit": 100})

    assert "nora" not in {item["id"] for item in own.json()["data"]}
    assert "nora" not in {item["id"] for item in other.json()["data"]}


@pytest.mark.asyncio
async def test_caller_without_a_tenant_sees_nobody(client: AsyncClient) -> None:
    _as("OPERATOR", "")

    response = await client.get("/api/v1/users/directory")

    assert response.status_code == 200
    assert response.json()["data"] == []
    assert response.json()["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_administrator_user_list_still_shows_users_without_a_tenant(
    client: AsyncClient,
) -> None:
    _as("ADMINISTRATOR")

    response = await client.get("/api/v1/users", params={"limit": 100})

    assert "nora" in {item["id"] for item in response.json()["data"]}


@pytest.mark.asyncio
async def test_administrator_may_call_it(client: AsyncClient) -> None:
    _as("ADMINISTRATOR")

    assert (await client.get("/api/v1/users/directory")).status_code == 200


@pytest.mark.asyncio
async def test_reviewer_is_refused(client: AsyncClient) -> None:
    _as("REVIEWER")

    assert (await client.get("/api/v1/users/directory")).status_code == 403


@pytest.mark.asyncio
async def test_directory_does_not_read_login_events(client: AsyncClient, admin: _FakeAdmin) -> None:
    await client.get("/api/v1/users/directory")

    assert admin.event_calls == 0


@pytest.mark.asyncio
async def test_full_user_list_stays_administrator_only(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/users")).status_code == 403
