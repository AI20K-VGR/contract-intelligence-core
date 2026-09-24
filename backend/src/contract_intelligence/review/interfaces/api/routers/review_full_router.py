r"""Review bounded context router — Phase 3 HITL (DOC-05 § review-items).

Endpoints:
    GET  /dossiers/{id}/review-items       — Queue ưu tiên P1 > P2 > P3
    GET  /review-items/{id}                — Item detail + version
    GET  /review-items/{id}/revisions      — Append-only audit trail
    POST /review-items/{id}/actions        — Submit action (optimistic locking)

Optimistic locking (P0-05 / openapi.yaml):
    Client sends ``base_version`` (``current_version`` previously read, or ``0``).
    On mismatch → **409 Conflict** with ``ReviewConflictResponse`` + current_state.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Path, Query, status
from fastapi.responses import JSONResponse

from contract_intelligence.review.application.dtos.review_dtos import (
    ReviewActionRequestDTO,
    ReviewActionResponseDTO,
    ReviewConflictErrorDTO,
    ReviewConflictResponseDTO,
    ReviewItemDTO,
    ReviewItemRevisionDTO,
)
from contract_intelligence.review.domain.entities.review_action import ReviewActionType
from contract_intelligence.review.domain.entities.review_item import (
    ReviewItemStatus,
    ReviewPriority,
)
from contract_intelligence.review.interfaces.api.dependencies import ReviewServiceDep
from contract_intelligence.shared.auth import AuthenticatedUser, require_role
from contract_intelligence.shared.exceptions import ReviewVersionConflict
from contract_intelligence.shared.responses import ApiMeta, ApiResponse

router = APIRouter(tags=["Review"])

_REVIEWER_RBAC = Depends(require_role("REVIEWER", "ADMINISTRATOR"))


@router.get(
    "/dossiers/{dossier_id}/review-items",
    response_model=ApiResponse[list[ReviewItemDTO]],
    summary="Queue review items ưu tiên",
)
async def list_review_items(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ReviewServiceDep,
    _user: Annotated[AuthenticatedUser, _REVIEWER_RBAC],
    priority: Annotated[ReviewPriority | None, Query()] = None,
    status_filter: Annotated[ReviewItemStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[list[ReviewItemDTO]]:
    """Hàng đợi review theo P1 > P2 > P3. RBAC: REVIEWER, ADMINISTRATOR."""
    items, total = await svc.list_review_items(
        dossier_id,
        priority=priority,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(
        data=items,
        meta=ApiMeta(
            total=total,
            page=(offset // limit) + 1,
            page_size=limit,
        ),
    )


@router.get(
    "/review-items/{item_id}",
    response_model=ApiResponse[ReviewItemDTO],
    responses={404: {"description": "Review item not found"}},
)
async def get_review_item(
    item_id: Annotated[str, Path(min_length=1)],
    svc: ReviewServiceDep,
    _user: Annotated[AuthenticatedUser, _REVIEWER_RBAC],
) -> ApiResponse[ReviewItemDTO]:
    """Chi tiết review item kèm ``version`` cho optimistic concurrency."""
    return ApiResponse(data=await svc.get_review_item(item_id))


@router.get(
    "/review-items/{item_id}/revisions",
    response_model=ApiResponse[list[ReviewItemRevisionDTO]],
    summary="Append-only review revisions trail",
    responses={404: {"description": "Review item not found"}},
)
async def list_revisions(
    item_id: Annotated[str, Path(min_length=1)],
    svc: ReviewServiceDep,
    _user: Annotated[AuthenticatedUser, _REVIEWER_RBAC],
) -> ApiResponse[list[ReviewItemRevisionDTO]]:
    """Lịch sử thao tác bất biến (confirm/correct/reject/…)."""
    return ApiResponse(data=await svc.list_revisions(item_id))


@router.post(
    "/review-items/{item_id}/actions",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[ReviewActionResponseDTO],
    summary="Submit review action (optimistic concurrency via base_version)",
    responses={
        403: {"description": "Insufficient role"},
        404: {"description": "Review item not found"},
        409: {"description": "Version conflict — base_version mismatch"},
        422: {"description": "Invalid action or missing corrected_value"},
    },
)
async def submit_action(
    item_id: Annotated[str, Path(min_length=1)],
    body: Annotated[ReviewActionRequestDTO, Body()],
    svc: ReviewServiceDep,
    user: Annotated[AuthenticatedUser, Depends(require_role("REVIEWER", "ADMINISTRATOR"))],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ApiResponse[ReviewActionResponseDTO] | JSONResponse:
    """Ghi nhận hành động review. RBAC: REVIEWER, ADMINISTRATOR.

    ``base_version`` must match DB ``version`` or API returns **409** with current_state.
    ``Idempotency-Key`` accepted (replay window reserved for later hardening).
    """
    _ = idempotency_key  # reserved — Phase 3 accepts header without replay store yet
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

    try:
        result = await svc.submit_action(
            item_id=item_id,
            action_type=action_type,
            base_version=body.base_version,
            reviewer_id=user.user_id,
            corrected_value=body.corrected_value,
            corrected_bbox=body.corrected_bbox,
            comment=body.comment,
        )
    except ReviewVersionConflict as exc:
        conflict = ReviewConflictResponseDTO(
            error=ReviewConflictErrorDTO(
                code="VERSION_CONFLICT",
                message=exc.message,
            ),
            current_state=exc.current_state
            or {
                "review_item_id": exc.details.get("review_item_id"),
                "version": exc.details.get("current_version"),
            },
            your_submitted_action=None,
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=conflict.model_dump(mode="json"),
        )

    return ApiResponse(data=result)
