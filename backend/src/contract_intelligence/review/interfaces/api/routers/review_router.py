"""GET /review/dossiers/{id}/items + POST /review/items/{id}/actions."""

from __future__ import annotations

from fastapi import APIRouter, Body, status

from contract_intelligence.shared.responses import ApiResponse

router = APIRouter()


@router.get("/dossiers/{dossier_id}/items", response_model=ApiResponse[list])
async def list_review_items(dossier_id: str) -> ApiResponse[list]:
    return ApiResponse(data=[])


@router.post(
    "/items/{item_id}/actions",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[dict],
)
async def submit_action(
    item_id: str,
    payload: dict = Body(...),
) -> ApiResponse[dict]:
    """POST /review/items/{id}/actions — optimistic concurrency.

    Body:
        {
            "action": "confirm" | "correct" | "reject" | "needs_more_evidence",
            "base_version": int,
            "corrected_value": {...} | null,
            "corrected_bbox": [...] | null,
            "comment": "..."
        }
    """
    return ApiResponse(data={"item_id": item_id, "version": payload.get("base_version", 0) + 1})
