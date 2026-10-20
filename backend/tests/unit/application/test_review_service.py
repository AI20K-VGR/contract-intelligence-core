"""Unit tests for ReviewService — optimistic concurrency + revisions."""

from __future__ import annotations

from typing import Any

import pytest

from contract_intelligence.review.application.services.review_service import ReviewService
from contract_intelligence.review.domain.entities.review_action import ReviewActionType
from contract_intelligence.shared.exceptions import (
    NotFoundError,
    ReviewVersionConflict,
    ValidationError,
)

pytestmark = pytest.mark.asyncio


class FakeReviewRepo:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {
            "ri_1": {
                "id": "ri_1",
                "dossier_id": "dos_1",
                "run_id": "run_1",
                "target_type": "fact",
                "target_id": "fct_1",
                "reason": "check",
                "priority": "P1",
                "status": "open",
                "version": 2,
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        }
        self.actions: list[dict[str, Any]] = []

    async def list_by_dossier(
        self,
        dossier_id: str,
        *,
        priority: Any = None,
        status_filter: Any = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [i for i in self.items.values() if i["dossier_id"] == dossier_id]
        if priority is not None:
            rows = [r for r in rows if r["priority"] == priority.value]
        if status_filter is not None:
            rows = [r for r in rows if r["status"] == status_filter.value]
        return rows[offset : offset + limit], len(rows)

    async def get_item(self, item_id: str) -> dict[str, Any] | None:
        return self.items.get(item_id)

    async def list_revisions(self, item_id: str) -> list[dict[str, Any]]:
        return [a for a in self.actions if a["review_item_id"] == item_id]

    async def submit_action(
        self,
        *,
        item_id: str,
        action_type: ReviewActionType,
        base_version: int,
        reviewer_id: str,
        corrected_value: dict[str, Any] | None = None,
        corrected_bbox: list[Any] | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        item = self.items.get(item_id)
        if item is None:
            raise NotFoundError(entity_type="ReviewItem", entity_id=item_id)
        if item["version"] != base_version:
            raise ReviewVersionConflict(
                review_item_id=item_id,
                expected_version=base_version,
                current_version=int(item["version"]),
                current_state=dict(item),
            )
        new_version = int(item["version"]) + 1
        item["version"] = new_version
        if action_type in (
            ReviewActionType.CONFIRM,
            ReviewActionType.CORRECT,
            ReviewActionType.REJECT,
        ):
            item["status"] = "resolved"
        elif action_type == ReviewActionType.NEEDS_MORE_EVIDENCE:
            item["status"] = "awaiting_evidence"
        action = {
            "id": f"ra_{len(self.actions) + 1}",
            "review_item_id": item_id,
            "action": action_type.value,
            "base_version": base_version,
            "corrected_value": corrected_value,
            "corrected_bbox": corrected_bbox,
            "comment": comment,
            "reviewer_id": reviewer_id,
            "created_at": "2026-01-02T00:00:00+00:00",
        }
        self.actions.append(action)
        return {
            "action_id": action["id"],
            "review_action_id": action["id"],
            "new_version": new_version,
            "item_status": item["status"],
            "effective_value": corrected_value,
            "open_items_remaining": 0,
        }


@pytest.fixture
def svc() -> ReviewService:
    return ReviewService(repo=FakeReviewRepo(), tenant_id="t")  # type: ignore[arg-type]


class TestReviewService:
    async def test_list_and_get(self, svc: ReviewService) -> None:
        items, total = await svc.list_review_items("dos_1")
        assert total == 1
        assert items[0].version == 2
        detail = await svc.get_review_item("ri_1")
        assert detail.id == "ri_1"

    async def test_submit_confirm_bumps_version(self, svc: ReviewService) -> None:
        result = await svc.submit_action(
            item_id="ri_1",
            action_type=ReviewActionType.CONFIRM,
            base_version=2,
            reviewer_id="usr_1",
        )
        assert result.new_version == 3
        assert result.item_status == "resolved"
        detail = await svc.get_review_item("ri_1")
        assert detail.version == 3

    async def test_submit_conflict_raises(self, svc: ReviewService) -> None:
        with pytest.raises(ReviewVersionConflict) as exc:
            await svc.submit_action(
                item_id="ri_1",
                action_type=ReviewActionType.CONFIRM,
                base_version=1,  # stale
                reviewer_id="usr_1",
            )
        assert exc.value.details["current_version"] == 2
        assert exc.value.current_state is not None

    async def test_correct_requires_payload(self, svc: ReviewService) -> None:
        with pytest.raises(ValidationError):
            await svc.submit_action(
                item_id="ri_1",
                action_type=ReviewActionType.CORRECT,
                base_version=2,
                reviewer_id="usr_1",
            )

    async def test_correct_with_value_and_revisions(self, svc: ReviewService) -> None:
        await svc.submit_action(
            item_id="ri_1",
            action_type=ReviewActionType.CORRECT,
            base_version=2,
            reviewer_id="usr_1",
            corrected_value={"amount": 120},
        )
        revs = await svc.list_revisions("ri_1")
        assert len(revs) == 1
        assert revs[0].revision_number == 1
        assert revs[0].action == "correct"
        assert revs[0].previous_version == 2
        assert revs[0].corrected_value == {"amount": 120}
