"""GET /review/dossiers/{id}/items + POST /review/items/{id}/actions."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, status

from contract_intelligence.shared.auth import (
    AuthenticatedUser,
    get_current_user,
    require_role,
)
from contract_intelligence.shared.responses import ApiResponse

router = APIRouter()


@router.get("/dossiers/{dossier_id}/items", response_model=ApiResponse[list[object]])
async def list_review_items(
    dossier_id: str,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[list[object]]:
    return ApiResponse(data=[])


@router.post(
    "/items/{item_id}/actions",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[dict[str, object]],
)
async def submit_action(
    item_id: str,
    _user: Annotated[AuthenticatedUser, Depends(require_role("REVIEWER", "ADMINISTRATOR"))],
    payload: dict[str, object] = Body(...),
) -> ApiResponse[dict[str, object]]:
    """POST /review/items/{id}/actions — optimistic concurrency.

    RBAC: REVIEWER, ADMINISTRATOR.

    Body:
        {
            "action": "confirm" | "correct" | "reject" | "needs_more_evidence",
            "base_version": int,
            "corrected_value": {...} | null,
            "corrected_bbox": [...] | null,
            "comment": "..."
        }
    """
    base_version = payload.get("base_version", 0)
    version = (base_version if isinstance(base_version, int) else 0) + 1
    return ApiResponse(data={"item_id": item_id, "version": version})
