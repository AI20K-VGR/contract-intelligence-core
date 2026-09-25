"""Phase 1 route registration and mutation authorization invariants."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient

from contract_intelligence.main import app
from contract_intelligence.review.application.services.approval_service import ApprovalService
from contract_intelligence.review.application.services.review_service import ReviewService
from contract_intelligence.review.interfaces.api.dependencies_approval import (
    require_external_approval_access,
    require_external_approval_read_access,
    require_lock_access,
)
from contract_intelligence.shared.auth import get_current_user
from contract_intelligence.shared.auth.schemas import AuthenticatedUser


def _registered_routes() -> list[tuple[str, APIRoute]]:
    """Expand FastAPI's lazy included-router nodes for registration assertions."""
    registered: list[tuple[str, APIRoute]] = []
    for node in app.routes:
        router = getattr(node, "original_router", None)
        context = getattr(node, "include_context", None)
        if router is None or context is None:
            continue
        prefix = context.prefix
        for route in router.routes:
            if isinstance(route, APIRoute):
                registered.append((f"{prefix}{route.path}", route))
    return registered


def _routes(path: str, method: str) -> list[APIRoute]:
    return [
        route
        for registered_path, route in _registered_routes()
        if registered_path == path and method in route.methods
    ]


def _user(*, role: str, user_id: str = "usr_actor") -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user_id,
        tenant_id="tenant_test",
        email=f"{user_id}@test.com",
        display_name="Test Actor",
        role=role,
    )


def test_canonical_mutation_routes_are_not_shadowed_by_simulated_routes() -> None:
    review_routes = _routes("/api/v1/review-items/{item_id}/actions", "POST")
    approval_routes = _routes("/api/v1/dossiers/{dossier_id}/approve", "POST")

    assert review_routes
    assert approval_routes
    assert all(
        route.endpoint.__module__ != "contract_intelligence.api.v1.reviews"
        for route in review_routes
    )
    assert all(
        route.endpoint.__module__ != "contract_intelligence.api.v1.dossiers"
        for route in approval_routes
    )

    shadowing_routes = {
        route.endpoint.__module__
        for path, route in _registered_routes()
        if path
        in {
            "/api/v1/review-items/{item_id}/actions",
            "/api/v1/dossiers/{id}/approve",
        }
        and route.endpoint.__module__
        in {"contract_intelligence.api.v1.reviews", "contract_intelligence.api.v1.dossiers"}
    }
    assert shadowing_routes == set()


def _dependency_calls(route: APIRoute) -> set[object]:
    """Return direct and nested FastAPI dependency callables for a route."""
    calls: set[object] = set()

    def visit(dependant: object) -> None:
        call = getattr(dependant, "call", None)
        if call is not None:
            calls.add(call)
        for child in getattr(dependant, "dependencies", ()):
            visit(child)

    visit(route.dependant)
    return calls


def test_dossier_lock_and_external_approval_routes_have_dossier_acl_dependencies() -> None:
    lock_route = _routes("/api/v1/dossiers/{dossier_id}/lock", "POST")
    create_external_route = _routes(
        "/api/v1/dossiers/{dossier_id}/external-approvals", "POST"
    )
    list_external_route = _routes(
        "/api/v1/dossiers/{dossier_id}/external-approvals", "GET"
    )

    assert lock_route and create_external_route and list_external_route
    assert require_lock_access in _dependency_calls(lock_route[0])
    assert require_external_approval_access in _dependency_calls(create_external_route[0])
    assert require_external_approval_read_access in _dependency_calls(list_external_route[0])


@pytest_asyncio.fixture
async def authz_client() -> AsyncGenerator[AsyncClient, None]:
    from contract_intelligence.review.interfaces.api.dependencies import get_review_service
    from contract_intelligence.review.interfaces.api.dependencies_approval import (
        get_approval_service,
    )
    from contract_intelligence.shared.auth.tenant import get_tenant_id

    review_service = AsyncMock(spec=ReviewService)
    approval_service = AsyncMock(spec=ApprovalService)
    app.dependency_overrides[get_review_service] = lambda: review_service
    app.dependency_overrides[get_approval_service] = lambda: approval_service
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_test"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_anonymous_review_mutation_is_401_and_does_not_call_service(
    authz_client: AsyncClient,
) -> None:
    response = await authz_client.post(
        "/api/v1/review-items/ri_unauth/actions",
        json={"action": "confirm", "base_version": 1},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_wrong_role_review_mutation_is_403_and_does_not_call_service(
    authz_client: AsyncClient,
) -> None:
    app.dependency_overrides[get_current_user] = lambda: _user(role="OPERATOR")
    response = await authz_client.post(
        "/api/v1/review-items/ri_wrong_role/actions",
        json={"action": "confirm", "base_version": 1},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_wrong_role_approval_is_403(
    authz_client: AsyncClient,
) -> None:
    app.dependency_overrides[get_current_user] = lambda: _user(role="REVIEWER")
    response = await authz_client.post("/api/v1/dossiers/dos_wrong_role/approve", json={})

    assert response.status_code == 403
