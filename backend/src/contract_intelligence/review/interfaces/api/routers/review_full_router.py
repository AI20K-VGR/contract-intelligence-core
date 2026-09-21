r"""Review bounded context router — Màn hình 7 (DOC-05b §5.7).

Endpoints:
    GET  /dossiers/{id}/review-items       — Queue ưu tiên P1 > P2 > P3
    GET  /review-items/{id}                — Item detail + version
    GET  /review-items/{id}/revisions      — Audit trail append-only
    POST /review-items/{id}/actions        — Submit action với optimistic locking

Optimistic locking (P0-05):
    Client gửi ``base_version``; nếu mismatch → 409 VERSION_CONFLICT.
    Frontend refetch item và thông báo reviewer.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field

from contract_intelligence.review.domain.entities.review_action import ReviewActionType
from contract_intelligence.review.domain.entities.review_item import (
    ReviewItemStatus,
    ReviewPriority,
)
from contract_intelligence.review.interfaces.api.dependencies import ReviewServiceDep
from contract_intelligence.shared.auth import (
    AuthenticatedUser,
    get_current_user,
    require_role,
)
from contract_intelligence.shared.responses import ApiResponse

router = APIRouter(tags=["Review"])


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------


class ReviewActionRequest(BaseModel):
    """Request body cho POST /review-items/{id}/actions.

    P0-05: bắt buộc có ``base_version``.
    """

    model_config = ConfigDict(extra="forbid")

    action: str = Field(..., description="confirm | correct | reject | needs_more_evidence")
    base_version: int = Field(..., ge=1, description="Phiên bản client đang xem")
    corrected_value: dict[str, Any] | None = None
    corrected_bbox: list[dict[str, Any]] | None = None
    comment: str | None = None


class ReviewActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str
    new_version: int
    current_version: int


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------


@router.get(
    "/dossiers/{dossier_id}/review-items",
    response_model=ApiResponse[dict[str, Any]],
    summary="Queue review items ưu tiên",
)
async def list_review_items(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ReviewServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    priority: Annotated[ReviewPriority | None, Query()] = None,
    status_filter: Annotated[ReviewItemStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[dict[str, Any]]:
    """Hàng đợi các mục cần chuyên viên xử lý theo P1 > P2 > P3.

    RBAC: REVIEWER, ADMINISTRATOR.
    """
    items, total = await svc.list_review_items(
        dossier_id,
        priority=priority,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(
        data={
            "items": items,
            "total": total,
            "page": (offset // limit) + 1,
            "page_size": limit,
            "total_pages": (total + limit - 1) // limit if total > 0 else 0,
        }
    )


@router.get(
    "/review-items/{item_id}",
    response_model=ApiResponse[dict[str, Any]],
    responses={404: {"description": "Review item not found"}},
)
async def get_review_item(
    item_id: Annotated[str, Path(min_length=1)],
    svc: ReviewServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await svc.get_review_item(item_id))


@router.get(
    "/review-items/{item_id}/revisions",
    response_model=ApiResponse[list[Any]],
    summary="Lịch sử thao tác của các reviewer (audit trail bất biến)",
)
async def list_revisions(
    item_id: Annotated[str, Path(min_length=1)],
    svc: ReviewServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[list[Any]]:
    return ApiResponse(data=await svc.list_revisions(item_id))


@router.post(
    "/review-items/{item_id}/actions",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[dict[str, Any]],
    summary="Submit review action (chống ghi đè với base_version)",
    responses={
        403: {"description": "Insufficient role"},
        409: {"description": "Version conflict — base_version mismatch"},
    },
)
async def submit_action(
    item_id: Annotated[str, Path(min_length=1)],
    body: Annotated[ReviewActionRequest, Body()],
    svc: ReviewServiceDep,
    user: Annotated[AuthenticatedUser, Depends(require_role("REVIEWER", "ADMINISTRATOR"))],
) -> ApiResponse[dict[str, Any]]:
    """Ghi nhận hành động review. RBAC: REVIEWER, ADMINISTRATOR.

    409 VERSION_CONFLICT nếu base_version không match current version.
    Frontend refetch item mới nhất.
    """
    try:
        action_type = ReviewActionType(body.action)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid action {body.action!r} — "
                "must be confirm/correct/reject/needs_more_evidence"
            ),
        ) from exc

    result = await svc.submit_action(
        item_id=item_id,
        action_type=action_type,
        base_version=body.base_version,
        reviewer_id=user.user_id,
        corrected_value=body.corrected_value,
        corrected_bbox=body.corrected_bbox,
        comment=body.comment,
    )
    return ApiResponse(
        data={
            "action_id": result["action_id"],
            "new_version": result["new_version"],
            "current_version": result["current_version"],
            "status": "recorded",
        }
    )
