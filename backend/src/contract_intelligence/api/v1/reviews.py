"""HITL review-item actions — optimistic concurrency + revision log.

Tutorial / orchestration surface under ``api/v1``. Uses an in-process store to
simulate DB versioning when a review item has not been seeded yet.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, status

from contract_intelligence.schemas.reviews import ReviewActionRequest
from contract_intelligence.shared.base import new_ulid, utcnow

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/review-items", tags=["Reviews"])

# Simulated persistence: item_id → {version, status, revisions[]}
_REVIEW_STORE: dict[str, dict[str, Any]] = {}


def _get_or_create_item(item_id: str) -> dict[str, Any]:
    item = _REVIEW_STORE.get(item_id)
    if item is None:
        item = {
            "id": item_id,
            "version": 1,  # align with ReviewItemORM server_default
            "status": "open",
            "revisions": [],
        }
        _REVIEW_STORE[item_id] = item
    return item


def list_unresolved_simulated(dossier_id: str) -> list[str]:
    """Return simulated review-item ids still open for ``dossier_id``."""
    open_statuses = frozenset({"open", "needs_review", "pending"})
    unresolved: list[str] = []
    for item_id, item in _REVIEW_STORE.items():
        item_dossier = item.get("dossier_id")
        belongs = item_dossier == dossier_id or item_id.startswith(f"{dossier_id}:")
        if belongs and item.get("status") in open_statuses:
            unresolved.append(item_id)
    return unresolved


def reset_review_store() -> None:
    """Test helper — clear simulated review state."""
    _REVIEW_STORE.clear()


@router.post(
    "/{id}/actions",
    status_code=status.HTTP_200_OK,
    summary="Submit review action (optimistic concurrency via base_version)",
    responses={
        409: {"description": "Version conflict — base_version mismatch"},
        422: {"description": "Invalid action payload"},
    },
)
async def submit_review_action(
    id: str,  # noqa: A002 — path param name per API contract
    body: ReviewActionRequest,
) -> dict[str, Any]:
    """Apply confirm / correct / reject / needs_more_evidence with OCC.

    If ``base_version`` does not match the current simulated version → **409**.
    On success, bumps version and appends a ReviewRevision log entry.
    """
    item = _get_or_create_item(id)
    current_version = int(item["version"])

    if body.base_version != current_version:
        logger.warning(
            "reviews.version_conflict",
            review_item_id=id,
            base_version=body.base_version,
            current_version=current_version,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "VERSION_CONFLICT",
                "message": (
                    f"base_version {body.base_version} does not match "
                    f"current version {current_version}"
                ),
                "current_state": {
                    "review_item_id": id,
                    "version": current_version,
                    "status": item["status"],
                },
            },
        )

    new_version = current_version + 1
    status_map = {
        "confirm": "confirmed",
        "correct": "corrected",
        "reject": "rejected",
        "needs_more_evidence": "needs_more_evidence",
    }
    new_status = status_map[body.action.value]
    now: datetime = utcnow()
    revision = {
        "revision_id": new_ulid("rev_"),
        "revision_number": len(item["revisions"]) + 1,
        "action": body.action.value,
        "reason": body.reason,
        "previous_version": current_version,
        "new_version": new_version,
        "created_at": now.isoformat(),
    }
    item["version"] = new_version
    item["status"] = new_status
    item["revisions"].append(revision)

    logger.info(
        "reviews.action_applied",
        review_item_id=id,
        action=body.action.value,
        new_version=new_version,
        status=new_status,
    )
    return {
        "status": "ok",
        "message": f"Review action {body.action.value} applied successfully",
        "review_item_id": id,
        "item_status": new_status,
        "new_version": new_version,
        "revision": revision,
    }
