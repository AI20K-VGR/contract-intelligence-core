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
    ClauseReviewDTO,
    ClauseReviewEntryDTO,
    ReviewActionResponseDTO,
    ReviewItemDTO,
    ReviewItemRevisionDTO,
)
from contract_intelligence.review.application.services.review_service import (
    ReviewService,
    clause_snapshot,
)
from contract_intelligence.review.domain.entities.review_action import ReviewActionType
from contract_intelligence.shared.auth.schemas import AuthenticatedUser
from contract_intelligence.shared.exceptions import (
    InvariantViolation,
    NotFoundError,
    ReviewVersionConflict,
    ValidationError,
)

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


def _ctx(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "node_id": "cl_1",
        "document_id": "doc_1",
        "dossier_id": "dos_1",
        "dossier_tenant_id": "tenant_test",
        "dossier_metadata": {"created_by": "usr_rev"},
        "is_locked": False,
        "run_id": "run_1",
        "node_type": "article",
        "number": "Điều 2",
        "label": "ARTICLE_2",
        "ordinal": 0,
        "text": "Điều 2: Thực hiện",
    }
    base.update(overrides)
    return base


def _clause_state(version: int = 2) -> ClauseReviewDTO:
    entry = ClauseReviewEntryDTO(
        revision_number=1,
        review_action_id="ra_1",
        action="correct",
        comment="Điều 2 chỉ nói bàn giao, chưa nói nghiệm thu",
        corrected_value={"assessment": "Điều 2 chỉ nói bàn giao, chưa nói nghiệm thu"},
        reviewer_id="usr_rev",
        reviewer_name="Reviewer",
        base_version=1,
        created_at=datetime(2026, 9, 25, tzinfo=UTC),
    )
    return ClauseReviewDTO(
        node_id="cl_1",
        document_id="doc_1",
        dossier_id="dos_1",
        review_item_id="ri_1",
        run_id="run_1",
        version=version,
        status="resolved",
        latest=entry,
        history=[entry],
    )


class TestClauseReview:
    async def test_get_returns_latest_and_history(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.get_clause_context.return_value = _ctx()
        mock_svc.get_clause_review.return_value = _clause_state()
        resp = await client.get("/api/v1/clause-nodes/cl_1/review")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["version"] == 2
        assert data["latest"]["reviewer_name"] == "Reviewer"
        assert data["latest"]["action"] == "correct"
        assert len(data["history"]) == 1

    async def test_operator_with_share_can_read_prior_review(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        from contract_intelligence.shared.auth import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _operator()
        mock_svc.get_clause_context.return_value = _ctx(
            dossier_metadata={"created_by": "usr_owner", "shared_with": [{"id": "usr_op"}]}
        )
        mock_svc.get_clause_review.return_value = _clause_state()
        resp = await client.get("/api/v1/clause-nodes/cl_1/review")
        assert resp.status_code == 200

    async def test_get_forbidden_when_share_revoked(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.get_clause_context.return_value = _ctx(
            dossier_metadata={"created_by": "usr_owner", "access_scope": "mine"}
        )
        resp = await client.get("/api/v1/clause-nodes/cl_1/review")
        assert resp.status_code == 403
        mock_svc.get_clause_review.assert_not_called()

    async def test_get_forbidden_across_tenants(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.get_clause_context.return_value = _ctx(dossier_tenant_id="other")
        resp = await client.get("/api/v1/clause-nodes/cl_1/review")
        assert resp.status_code == 403

    async def test_post_records_reviewer_and_version(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.get_clause_context.return_value = _ctx()
        mock_svc.submit_clause_review.return_value = _clause_state()
        resp = await client.post(
            "/api/v1/clause-nodes/cl_1/review",
            json={
                "action": "correct",
                "base_version": 0,
                "comment": "Điều 2 chỉ nói bàn giao, chưa nói nghiệm thu",
            },
        )
        assert resp.status_code == 200
        kwargs = mock_svc.submit_clause_review.call_args.kwargs
        assert kwargs["reviewer_id"] == "usr_rev"
        assert kwargs["base_version"] == 0
        assert kwargs["action_type"] == ReviewActionType.CORRECT
        assert resp.json()["data"]["version"] == 2

    async def test_post_conflict_returns_current_state(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        mock_svc.get_clause_context.return_value = _ctx()
        mock_svc.submit_clause_review.side_effect = ReviewVersionConflict(
            review_item_id="ri_1",
            expected_version=1,
            current_version=2,
            current_state=_clause_state().model_dump(mode="json"),
        )
        resp = await client.post(
            "/api/v1/clause-nodes/cl_1/review",
            json={"action": "confirm", "base_version": 1},
        )
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"]["code"] == "VERSION_CONFLICT"
        assert body["current_state"]["latest"]["reviewer_id"] == "usr_rev"

    async def test_post_rejects_operator(self, client: AsyncClient, mock_svc: AsyncMock) -> None:
        from contract_intelligence.shared.auth import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _operator()
        resp = await client.post(
            "/api/v1/clause-nodes/cl_1/review",
            json={"action": "confirm", "base_version": 0},
        )
        assert resp.status_code == 403
        mock_svc.submit_clause_review.assert_not_called()

    async def test_post_rejects_unknown_action(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/clause-nodes/cl_1/review",
            json={"action": "needs_more_evidence", "base_version": 0},
        )
        assert resp.status_code == 422


class _FakeClauseRepo:
    def __init__(
        self,
        *,
        item: dict[str, object] | None = None,
        orphans: list[dict[str, object]] | None = None,
        orphan_rows: list[dict[str, object]] | None = None,
    ) -> None:
        self.item = item
        self.orphans = orphans or []
        self.orphan_rows = orphan_rows or []
        self.submitted: list[dict[str, object]] = []
        self.snapshots: list[dict[str, object]] = []
        self.anchor_lookup: dict[str, object] = {}

    async def find_item_for_target(self, **_: object) -> dict[str, object] | None:
        return self.item

    async def get_or_create_item_for_target(self, **kw: object) -> tuple[dict[str, object], bool]:
        self.item = {
            "id": "ri_new",
            "version": 1,
            "status": "open",
            "run_id": kw["run_id"],
            "target_snapshot": kw.get("target_snapshot"),
        }
        return self.item, True

    async def get_clause_context(self, _node_id: str) -> dict[str, object] | None:
        return None

    async def get_line_anchor_context(self, **kw: object) -> dict[str, object] | None:
        self.anchor_lookup = kw
        return {
            "node_id": "ln_anchor",
            "document_id": kw["document_id"],
            "dossier_id": "dos_1",
            "is_locked": False,
            "run_id": "job_1",
        }

    async def ensure_target_snapshot(self, _item_id: str, snap: dict[str, object]) -> None:
        self.snapshots.append(snap)

    async def list_orphan_clause_items(self, _dossier_id: str) -> list[dict[str, object]]:
        return self.orphans

    async def submit_action(self, **kw: object) -> dict[str, object]:
        assert self.item is not None
        version = int(str(self.item["version"]))
        if kw["base_version"] != version:
            raise ReviewVersionConflict(
                review_item_id=str(self.item["id"]),
                expected_version=int(str(kw["base_version"])),
                current_version=version,
            )
        self.submitted.append(kw)
        self.item = {**self.item, "version": version + 1, "status": "resolved"}
        return {"review_action_id": "ra_x", "new_version": version + 1}

    async def list_revisions_with_reviewer(self, item_id: str) -> list[dict[str, object]]:
        if item_id != (self.item or {}).get("id"):
            return self.orphan_rows
        return [
            {
                "id": f"ra_{i}",
                "action": str(s["action_type"]),
                "base_version": s["base_version"],
                "comment": s["comment"],
                "corrected_value": s["corrected_value"],
                "reviewer_id": s["reviewer_id"],
                "reviewer_name": "Reviewer",
            }
            for i, s in enumerate(self.submitted, start=1)
        ]


class TestClauseReviewService:
    async def test_first_review_creates_item_and_next_reviewer_builds_on_it(self) -> None:
        repo = _FakeClauseRepo()
        svc = ReviewService(repo=repo, tenant_id="t")  # type: ignore[arg-type]
        first = await svc.submit_clause_review(
            ctx=_ctx(),
            action_type=ReviewActionType.CORRECT,
            base_version=0,
            reviewer_id="usr_a",
            comment="  Chỉ nói bàn giao  ",
        )
        assert first.version == 2
        assert first.latest is not None
        assert first.latest.corrected_value == {"assessment": "Chỉ nói bàn giao"}

        second = await svc.submit_clause_review(
            ctx=_ctx(),
            action_type=ReviewActionType.CONFIRM,
            base_version=first.version,
            reviewer_id="usr_b",
        )
        assert second.version == 3
        assert [e.reviewer_id for e in second.history] == ["usr_a", "usr_b"]
        assert second.latest is not None and second.latest.reviewer_id == "usr_b"

    async def test_stale_version_raises_conflict_with_latest_state(self) -> None:
        repo = _FakeClauseRepo(item={"id": "ri_1", "version": 3, "status": "resolved"})
        svc = ReviewService(repo=repo, tenant_id="t")  # type: ignore[arg-type]
        with pytest.raises(ReviewVersionConflict) as exc:
            await svc.submit_clause_review(
                ctx=_ctx(),
                action_type=ReviewActionType.REJECT,
                base_version=2,
                reviewer_id="usr_b",
            )
        assert exc.value.current_state is not None
        assert exc.value.current_state["version"] == 3

    async def test_correct_without_note_is_rejected(self) -> None:
        svc = ReviewService(repo=_FakeClauseRepo(), tenant_id="t")  # type: ignore[arg-type]
        with pytest.raises(ValidationError):
            await svc.submit_clause_review(
                ctx=_ctx(),
                action_type=ReviewActionType.CORRECT,
                base_version=0,
                reviewer_id="usr_a",
                comment="   ",
            )

    async def test_first_review_stores_clause_snapshot(self) -> None:
        repo = _FakeClauseRepo()
        svc = ReviewService(repo=repo, tenant_id="t")  # type: ignore[arg-type]
        await svc.submit_clause_review(
            ctx=_ctx(),
            action_type=ReviewActionType.CONFIRM,
            base_version=0,
            reviewer_id="usr_a",
        )
        assert repo.item is not None
        snap = repo.item["target_snapshot"]
        assert isinstance(snap, dict)
        assert snap["label"] == "ARTICLE_2"
        assert snap["ordinal"] == 0
        assert snap["text"] == "Điều 2: Thực hiện"

    async def test_backfills_snapshot_on_item_without_one(self) -> None:
        repo = _FakeClauseRepo(item={"id": "ri_old", "version": 1, "status": "open"})
        svc = ReviewService(repo=repo, tenant_id="t")  # type: ignore[arg-type]
        await svc.submit_clause_review(
            ctx=_ctx(),
            action_type=ReviewActionType.CONFIRM,
            base_version=1,
            reviewer_id="usr_a",
        )
        assert repo.snapshots and repo.snapshots[0]["label"] == "ARTICLE_2"

    def _orphan(self, **snap_overrides: object) -> dict[str, object]:
        snap = clause_snapshot(_ctx(document_id="doc_1"))
        snap.update(snap_overrides)
        return {"id": "ri_prev", "run_id": "run_0", "version": 2, "target_snapshot": snap}

    def _prev_rows(self) -> list[dict[str, object]]:
        return [
            {
                "id": "ra_prev",
                "action": "correct",
                "base_version": 1,
                "comment": "Chỉ nói bàn giao",
                "corrected_value": {"assessment": "Chỉ nói bàn giao"},
                "reviewer_id": "usr_a",
                "reviewer_name": "Reviewer A",
            }
        ]

    async def test_rerun_shows_previous_review_as_stale_not_current(self) -> None:
        repo = _FakeClauseRepo(orphans=[self._orphan()], orphan_rows=self._prev_rows())
        svc = ReviewService(repo=repo, tenant_id="t")  # type: ignore[arg-type]
        state = await svc.get_clause_review(_ctx(node_id="cl_new"))
        assert state.status == "unreviewed"
        assert state.latest is None
        assert state.version == 0
        assert state.stale is not None
        assert state.stale.latest.reviewer_name == "Reviewer A"
        assert state.stale.text_changed is False

    async def test_stale_flags_changed_text(self) -> None:
        repo = _FakeClauseRepo(
            orphans=[self._orphan(text_sha256="different", text="Điều 2: Thuc hien")],
            orphan_rows=self._prev_rows(),
        )
        svc = ReviewService(repo=repo, tenant_id="t")  # type: ignore[arg-type]
        state = await svc.get_clause_review(_ctx(node_id="cl_new"))
        assert state.stale is not None
        assert state.stale.text_changed is True
        assert state.stale.reviewed_text == "Điều 2: Thuc hien"

    async def test_stale_requires_same_ordinal_for_repeated_labels(self) -> None:
        repo = _FakeClauseRepo(orphans=[self._orphan(ordinal=1)], orphan_rows=self._prev_rows())
        svc = ReviewService(repo=repo, tenant_id="t")  # type: ignore[arg-type]
        state = await svc.get_clause_review(_ctx(node_id="cl_new"))
        assert state.stale is None

    async def test_stale_hidden_once_current_clause_is_reviewed(self) -> None:
        repo = _FakeClauseRepo(orphans=[self._orphan()], orphan_rows=self._prev_rows())
        svc = ReviewService(repo=repo, tenant_id="t")  # type: ignore[arg-type]
        state = await svc.submit_clause_review(
            ctx=_ctx(node_id="cl_new"),
            action_type=ReviewActionType.CONFIRM,
            base_version=0,
            reviewer_id="usr_b",
        )
        assert state.stale is None
        assert state.latest is not None and state.latest.reviewer_id == "usr_b"

    async def test_frontend_line_node_anchors_on_ocr_line(self) -> None:
        repo = _FakeClauseRepo()
        svc = ReviewService(repo=repo, tenant_id="t")  # type: ignore[arg-type]
        ctx = await svc.get_clause_context(
            "n-6-2",
            document_id="doc_1",
            node={
                "node_type": "article",
                "number": "2",
                "label": "Điều 2",
                "ordinal": 0,
                "text": "Thực hiện",
            },
        )
        assert repo.anchor_lookup == {"document_id": "doc_1", "page_no": 6, "line_no": 2}
        assert ctx["node_id"] == "ln_anchor"
        state = await svc.submit_clause_review(
            ctx=ctx, action_type=ReviewActionType.CONFIRM, base_version=0, reviewer_id="usr_a"
        )
        assert repo.item is not None
        snap = repo.item["target_snapshot"]
        assert isinstance(snap, dict)
        assert snap["label"] == "Điều 2" and snap["text"] == "Thực hiện"
        assert state.latest is not None and state.latest.reviewer_id == "usr_a"

    async def test_frontend_line_node_needs_document_id(self) -> None:
        svc = ReviewService(repo=_FakeClauseRepo(), tenant_id="t")  # type: ignore[arg-type]
        with pytest.raises(ValidationError):
            await svc.get_clause_context("n-6-2")

    async def test_unknown_node_is_not_found(self) -> None:
        svc = ReviewService(repo=_FakeClauseRepo(), tenant_id="t")  # type: ignore[arg-type]
        with pytest.raises(NotFoundError):
            await svc.get_clause_context("cl_missing")

    async def test_get_matches_stale_by_client_text_hash(self) -> None:
        snap = clause_snapshot(_ctx(document_id="doc_1"))
        repo = _FakeClauseRepo(
            orphans=[{"id": "ri_prev", "run_id": "job_0", "version": 2, "target_snapshot": snap}],
            orphan_rows=self._prev_rows(),
        )
        svc = ReviewService(repo=repo, tenant_id="t")  # type: ignore[arg-type]
        ctx = await svc.get_clause_context(
            "n-6-2",
            document_id="doc_1",
            node={
                "node_type": snap["node_type"],
                "number": snap["number"],
                "label": snap["label"],
                "ordinal": 0,
                "text_sha256": snap["text_sha256"],
            },
        )
        state = await svc.get_clause_review(ctx)
        assert state.stale is not None
        assert state.stale.text_changed is False

    async def test_locked_dossier_is_rejected(self) -> None:
        svc = ReviewService(repo=_FakeClauseRepo(), tenant_id="t")  # type: ignore[arg-type]
        with pytest.raises(InvariantViolation):
            await svc.submit_clause_review(
                ctx=_ctx(is_locked=True),
                action_type=ReviewActionType.CONFIRM,
                base_version=0,
                reviewer_id="usr_a",
            )
