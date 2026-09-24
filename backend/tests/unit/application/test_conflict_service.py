"""Unit tests for ConflictService Phase 2 (in-memory fake finding repo)."""

from __future__ import annotations

from typing import Any

import pytest

from contract_intelligence.conflict.application.services.conflict_service import (
    ConflictService,
)

pytestmark = pytest.mark.asyncio


class FakeFindingRepo:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    async def get(self, finding_id: str) -> dict[str, Any] | None:
        return next((r for r in self.rows if r["id"] == finding_id), None)

    async def list_by_dossier(
        self,
        dossier_id: str,
        *,
        disposition: str | None = None,
        scope: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        items = [r for r in self.rows if r["dossier_id"] == dossier_id]
        if disposition:
            items = [r for r in items if r["disposition"] == disposition]
        if scope:
            items = [r for r in items if r["scope"] == scope]
        total = len(items)
        return items[offset : offset + limit], total

    async def list_conflicts_for_review(
        self,
        dossier_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        conflict_disp = {
            "comparable_difference",
            "candidate_amendment",
            "insufficient_evidence",
        }
        items = [
            r
            for r in self.rows
            if r["dossier_id"] == dossier_id
            and (r["disposition"] in conflict_disp or float(r["confidence"]) < 0.6)
        ]
        return items[offset : offset + limit], len(items)

    async def add(self, finding: object) -> None:
        return


class FakeAnnexRepo:
    async def list_by_dossier(self, dossier_id: str) -> list[dict[str, Any]]:
        return []


@pytest.fixture
def svc() -> ConflictService:
    rows = [
        {
            "id": "f1",
            "dossier_id": "dos_1",
            "run_id": "run_1",
            "finding_type": "structured",
            "scope": "contract_annex",
            "key_or_topic": "price",
            "disposition": "comparable_difference",
            "severity": "high",
            "confidence": 0.3,
            "rationale": "diff",
            "method": "rule",
            "sides": [],
        },
        {
            "id": "f2",
            "dossier_id": "dos_1",
            "run_id": "run_1",
            "finding_type": "structured",
            "scope": "contract_annex",
            "key_or_topic": "party",
            "disposition": "comparable_match",
            "severity": "low",
            "confidence": 0.95,
            "rationale": "ok",
            "method": "rule",
            "sides": [],
        },
    ]
    return ConflictService(
        finding_repo=FakeFindingRepo(rows),  # type: ignore[arg-type]
        annex_link_repo=FakeAnnexRepo(),  # type: ignore[arg-type]
        tenant_id="t",
    )


class TestConflictService:
    async def test_list_findings_all(self, svc: ConflictService) -> None:
        items, total = await svc.list_findings("dos_1")
        assert total == 2
        assert len(items) == 2

    async def test_list_findings_filter_disposition(self, svc: ConflictService) -> None:
        items, total = await svc.list_findings("dos_1", disposition="comparable_match")
        assert total == 1
        assert items[0].id == "f2"

    async def test_list_conflicts_excludes_high_confidence_match(
        self, svc: ConflictService
    ) -> None:
        items, total = await svc.list_conflicts("dos_1")
        assert total == 1
        assert items[0].id == "f1"
