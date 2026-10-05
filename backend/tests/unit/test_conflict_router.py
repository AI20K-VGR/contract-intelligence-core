"""Unit tests for Phase 2 Conflict endpoints (findings + conflicts)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from contract_intelligence.conflict.application.dtos.finding_dtos import (
    FindingDTO,
    FindingSideSemanticDTO,
)
from contract_intelligence.conflict.application.services.conflict_service import (
    ConflictService,
)
from contract_intelligence.main import app
from contract_intelligence.shared.ai.schemas import (
    SemanticCitation,
    SemanticEvidence,
    SemanticFrame,
    SemanticKey,
    SemanticPair,
)
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


async def test_finding_side_semantic_accepts_v2_pair_diagnostics() -> None:
    evidence = SemanticEvidence(
        document_id="doc_1",
        snapshot_id="snap_1",
        source_ref="node_1",
        raw="30% payment",
        citation=SemanticCitation(
            node_id="node_1",
            page_revision_id="page_1",
            text_span="30% payment",
        ),
    )
    frame = SemanticFrame(
        frame_id="frame_1",
        family="PARAMETER",
        profile="SALES",
        document_id="doc_1",
        snapshot_id="snap_1",
        dossier_id="dos_1",
        evidence=[evidence],
        slots={},
        key=SemanticKey(
            key=["PAYMENT"],
            certainty="DEFINITE",
            reason="",
            method="CLOSED_SYMBOL",
            alias_digest=None,
            alias_version=None,
            alias_proposal_ids=[],
        ),
    )
    pair = SemanticPair(
        pair_id="pair_1",
        left_id="frame_1",
        right_id="frame_2",
        disposition="COMPARABLE_DIFFERENCE",
        reason="different amount",
        left_evidence=[evidence],
        right_evidence=[evidence],
        method="CLOSED_SYMBOL",
        candidate_sources=["SEMANTIC_ALIGNMENT"],
        conflict_kind="ARITHMETIC_INCONSISTENCY",
        slots_in_difference=["amount"],
    )
    parsed = FindingSideSemanticDTO.model_validate(
        {
            "frame": frame.model_dump(mode="json"),
            "pair": pair.model_dump(mode="json"),
            "profile_digest": "profile",
            "alias_version": 1,
            "alias_digest": None,
            "alignment_key": ["PAYMENT", "scope:shipping"],
            "conflict_kind": "ARITHMETIC_INCONSISTENCY",
            "slots_in_difference": ["amount"],
        }
    )
    assert parsed.alignment_key == ["PAYMENT", "scope:shipping"]
    assert parsed.conflict_kind == "ARITHMETIC_INCONSISTENCY"
    assert parsed.slots_in_difference == ["amount"]

    semantic_snapshot = {
        "frame": frame.model_dump(mode="json"),
        "pair": pair.model_dump(mode="json"),
        "profile_digest": "profile",
        "alias_version": 1,
        "alias_digest": None,
        "alignment_key": ["PAYMENT", "scope:shipping"],
        "conflict_kind": "ARITHMETIC_INCONSISTENCY",
        "slots_in_difference": ["amount"],
    }
    finding = FindingDTO.from_row(
        {
            "id": "fnd_semantic",
            "dossier_id": "dos_1",
            "finding_type": "semantic",
            "scope": "contract_annex",
            "key_or_topic": "pair_1",
            "disposition": "arithmetic_inconsistency",
            "severity": "high",
            "sides": [
                {
                    "side": "a",
                    "document_id": "doc_1",
                    "value_snapshot": {"semantic": semantic_snapshot},
                }
            ],
            "semantic": {
                "kind": "PAIR",
                "disposition": "COMPARABLE_DIFFERENCE",
                "reason": "different amount",
                "review_state": "NEEDS_REVIEW",
                "method": "CLOSED_SYMBOL",
                "profile_digest": "profile",
                "alias_version": 1,
                "alias_digest": None,
                "alignment_key": ["PAYMENT", "scope:shipping"],
                "conflict_kind": "ARITHMETIC_INCONSISTENCY",
                "slots_in_difference": ["amount"],
            },
        }
    )
    assert finding.semantic is not None
    assert finding.semantic.conflict_kind == "ARITHMETIC_INCONSISTENCY"
    assert finding.semantic.slots_in_difference == ["amount"]
    assert finding.sides[0].semantic is not None
    assert finding.sides[0].semantic.alignment_key == ["PAYMENT", "scope:shipping"]


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


class TestFindingReviewLatest:
    _LATEST_RAW = {
        "action": "confirm",
        "comment": None,
        "reviewer_id": "u1",
        "reviewer_name": "Admin",
        "reviewer_email": "a@ci.local",
        "reviewed_at": "2026-09-27T04:15:35Z",
        "action_count": 1,
    }

    def test_from_row_passes_latest_through(self) -> None:
        finding = _finding(
            review={
                "item_id": "ri_1",
                "status": "resolved",
                "current_version": 2,
                "latest": dict(self._LATEST_RAW),
            }
        )
        assert finding.review is not None
        assert finding.review.latest is not None
        assert finding.review.latest.action == "confirm"
        assert finding.review.latest.action_count == 1

    def test_from_row_latest_none_when_review_has_no_actions(self) -> None:
        finding = _finding(
            review={
                "item_id": "ri_1",
                "status": "open",
                "current_version": 1,
            }
        )
        assert finding.review is not None
        assert finding.review.latest is None

    async def test_endpoint_returns_latest_keys(
        self, client: AsyncClient, mock_svc: AsyncMock
    ) -> None:
        finding = _finding(
            review={
                "item_id": "ri_1",
                "status": "resolved",
                "current_version": 2,
                "latest": dict(self._LATEST_RAW),
            }
        )
        mock_svc.list_conflicts.return_value = ([finding], 1)
        resp = await client.get("/api/v1/dossiers/dos_1/conflicts")
        assert resp.status_code == 200
        latest = resp.json()["data"][0]["review"]["latest"]
        assert latest == self._LATEST_RAW
