"""Unit tests for Phase 3 HITL Review endpoints.

Mocks ReviewService at DI boundary — covers list/get/revisions/actions + 409 conflict.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from contract_intelligence.main import app
from contract_intelligence.review.application.dtos.review_dtos import (
    ReviewActionResponseDTO,
    ReviewItemDTO,
    ReviewItemRevisionDTO,
)
from contract_intelligence.review.application.services.review_service import ReviewService
from contract_intelligence.shared.auth.schemas import AuthenticatedUser
from contract_intelligence.shared.exceptions import NotFoundError, ReviewVersionConflict

pytestmark = pytest.mark.asyncio


def _reviewer() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="usr_rev",
        tenant_id="tenant_test",
        email="rev@test.com",
        display_name="Reviewer",
        role="REVIEWER",
    )


def _operator() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="usr_op",
        tenant_id="tenant_test",
        email="op@test.com",
        display_name="Operator",
        role="OPERATOR",
    )


def _item(**overrides: object) -> ReviewItemDTO:
    base: dict[str, object] = {
        "id": "ri_1",
        "dossier_id": "dos_1",
        "run_id": "run_1",
        "target_type": "fact",
        "target_id": "fct_1",
        "reason": "low confidence",
        "priority": "P1",
        "status": "open",
        "version": 3,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    base.update(overrides)
    return ReviewItemDTO.model_validate(base)


@pytest_asyncio.fixture
async def mock_svc() -> AsyncMock:
    return AsyncMock(spec=ReviewService)


@pytest_asyncio.fixture
async def client(mock_svc: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    from contract_intelligence.review.interfaces.api.dependencies import (
        get_review_service,
        require_review_dossier_access,
        require_review_item_access,
        require_review_item_mutation_access,
    )
    from contract_intelligence.shared.auth import get_current_user
    from contract_intelligence.shared.auth.tenant import get_tenant_id

    app.dependency_overrides[get_review_service] = lambda: mock_svc
    app.dependency_overrides[require_review_dossier_access] = lambda: None
    app.dependency_overrides[require_review_item_access] = lambda: None
    app.dependency_overrides[require_review_item_mutation_access] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: _reviewer()
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_test"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestListReviewItems:
    async def test_returns_200_with_meta(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.list_review_items.return_value = ([_item()], 1)
        resp = await client.get("/api/v1/dossiers/dos_1/review-items")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"][0]["id"] == "ri_1"
        assert body["data"][0]["version"] == 3
        assert body["meta"]["total"] == 1

    async def test_rbac_rejects_operator(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        from contract_intelligence.shared.auth import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _operator()
        resp = await client.get("/api/v1/dossiers/dos_1/review-items")
        assert resp.status_code == 403


class TestGetReviewItem:
    async def test_returns_detail(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.get_review_item.return_value = _item(id="ri_x")
        resp = await client.get("/api/v1/review-items/ri_x")
        assert resp.status_code == 200
        assert resp.json()["data"]["version"] == 3

    async def test_returns_404(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.get_review_item.side_effect = NotFoundError(
            entity_type="ReviewItem", entity_id="missing"
        )
        resp = await client.get("/api/v1/review-items/missing")
        assert resp.status_code == 404


class TestListRevisions:
    async def test_returns_append_only_trail(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.list_revisions.return_value = [
            ReviewItemRevisionDTO(
                revision_number=1,
                action="correct",
                author_user_id="usr_rev",
                previous_version=1,
                corrected_value={"amount": 120},
                created_at=datetime(2026, 1, 2, tzinfo=UTC),
            )
        ]
        resp = await client.get("/api/v1/review-items/ri_1/revisions")
        assert resp.status_code == 200
        rev = resp.json()["data"][0]
        assert rev["revision_number"] == 1
        assert rev["action"] == "correct"
        assert rev["previous_version"] == 1


class TestSubmitAction:
    """HITL orchestration API — confirm/correct/reject/needs_more_evidence with OCC."""

    async def test_returns_200_with_new_version(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.submit_action.return_value = ReviewActionResponseDTO(
            review_action_id="ra_1", item_status="confirmed", new_version=2
        )
        resp = await client.post(
            "/api/v1/review-items/ri_1/actions",
            json={"action": "confirm", "base_version": 1, "comment": "looks good"},
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["new_version"] == 2
        assert body["item_status"] == "confirmed"

    async def test_accepts_base_version_one(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        mock_svc.submit_action.return_value = ReviewActionResponseDTO(
            review_action_id="ra_2", item_status="needs_more_evidence", new_version=2
        )
        resp = await client.post(
            "/api/v1/review-items/ri_zero/actions",
            json={"action": "needs_more_evidence", "base_version": 1},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["new_version"] == 2
        assert resp.json()["data"]["item_status"] == "needs_more_evidence"

    async def test_returns_409_on_version_conflict(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.submit_action.side_effect = ReviewVersionConflict(
            "ri_conflict", 1, 2, current_state={"version": 2}
        )
        # Seed version 1 → apply once → version becomes 2
        resp = await client.post(
            "/api/v1/review-items/ri_conflict/actions",
            json={"action": "confirm", "base_version": 1},  # stale
        )
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"]["code"] == "VERSION_CONFLICT"
        assert body["current_state"]["version"] == 2

    async def test_invalid_action_returns_422(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/review-items/ri_1/actions",
            json={"action": "noop", "base_version": 1},
        )
        assert resp.status_code == 422
