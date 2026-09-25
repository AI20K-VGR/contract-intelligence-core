r"""Review bounded context router — Phase 3 HITL (DOC-05 § review-items).

Endpoints:
    GET  /dossiers/{id}/review-items       — Queue ưu tiên P1 > P2 > P3
    GET  /review-items/{id}                — Item detail + version
    GET  /review-items/{id}/revisions      — Append-only audit trail
    POST /review-items/{id}/actions        — Submit action (optimistic locking)
    GET  /clause-nodes/{id}/review         — Thẩm định hiện hành + lịch sử của điều khoản
    POST /clause-nodes/{id}/review         — Lưu thẩm định trích dẫn (confirm/reject/correct)

Optimistic locking (P0-05 / openapi.yaml):
    Client sends ``base_version`` (``current_version`` previously read, or ``0``).
    On mismatch → **409 Conflict** with ``ReviewConflictResponse`` + current_state.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Path, Query, status
from fastapi.responses import JSONResponse

from contract_intelligence.review.application.dtos.review_dtos import (
    ClauseReviewDTO,
    ClauseReviewRequestDTO,
    ReviewActionRequestDTO,
    ReviewActionResponseDTO,
    ReviewConflictErrorDTO,
    ReviewConflictResponseDTO,
    ReviewItemDTO,
    ReviewItemRevisionDTO,
)
from contract_intelligence.review.application.services.review_service import ReviewService
from contract_intelligence.review.domain.entities.review_action import ReviewActionType
from contract_intelligence.review.domain.entities.review_item import (
    ReviewItemStatus,
    ReviewPriority,
)
from contract_intelligence.review.interfaces.api.dependencies import (
    ReviewServiceDep,
    require_review_dossier_access,
    require_review_item_access,
    require_review_item_mutation_access,
)
from contract_intelligence.shared.acl import AclAction, dossier_access_decision
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user, require_role
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
    _acl: Annotated[None, Depends(require_review_dossier_access)],
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
    _acl: Annotated[None, Depends(require_review_item_access)],
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
    _acl: Annotated[None, Depends(require_review_item_access)],
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
    _acl: Annotated[None, Depends(require_review_item_mutation_access)],
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


async def _clause_with_access(
    svc: ReviewService,
    node_id: str,
    user: AuthenticatedUser,
    action: AclAction,
    *,
    document_id: str | None,
    node: dict[str, Any] | None,
) -> dict[str, Any]:
    ctx = await svc.get_clause_context(node_id, document_id=document_id, node=node)
    if not dossier_access_decision(
        action=action,
        principal=user,
        dossier_id=ctx["dossier_id"],
        dossier_tenant_id=str(ctx.get("dossier_tenant_id") or ""),
        metadata=ctx.get("dossier_metadata"),
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACL_DENIED", "message": "Dossier access denied"},
        )
    return ctx


@router.get(
    "/clause-nodes/{node_id}/review",
    response_model=ApiResponse[ClauseReviewDTO],
    summary="Thẩm định hiện hành của điều khoản + lịch sử ai sửa, lúc nào",
    responses={404: {"description": "Clause node not found"}},
)
async def get_clause_review(
    node_id: Annotated[str, Path(min_length=1)],
    svc: ReviewServiceDep,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    document_id: Annotated[str | None, Query()] = None,
    node_type: Annotated[str | None, Query(max_length=64)] = None,
    number: Annotated[str | None, Query(max_length=64)] = None,
    label: Annotated[str | None, Query(max_length=256)] = None,
    ordinal: Annotated[int | None, Query(ge=0)] = None,
    text_sha256: Annotated[str | None, Query(pattern="^[0-9a-f]{64}$")] = None,
) -> ApiResponse[ClauseReviewDTO]:
    """``version`` trả về là ``base_version`` client gửi lại khi lưu (0 = chưa ai thẩm định).

    Nút dựng từ dòng OCR (``n-{trang}-{dòng}``) cần ``document_id`` và mô tả nút
    để tìm thẩm định của lần phân tích trước.
    """
    node = {
        "node_type": node_type,
        "number": number,
        "label": label,
        "ordinal": ordinal,
        "text_sha256": text_sha256,
    }
    ctx = await _clause_with_access(
        svc, node_id, user, AclAction.CITATION_READ, document_id=document_id, node=node
    )
    return ApiResponse(data=await svc.get_clause_review(ctx))


@router.post(
    "/clause-nodes/{node_id}/review",
    response_model=ApiResponse[ClauseReviewDTO],
    summary="Lưu thẩm định trích dẫn (append-only, optimistic concurrency)",
    responses={
        403: {"description": "Insufficient role or dossier access revoked"},
        404: {"description": "Clause node not found"},
        409: {"description": "Người khác đã lưu trước, hoặc hồ sơ đã khóa"},
        422: {"description": "Sửa nhận định thiếu nội dung"},
    },
)
async def submit_clause_review(
    node_id: Annotated[str, Path(min_length=1)],
    body: Annotated[ClauseReviewRequestDTO, Body()],
    svc: ReviewServiceDep,
    user: Annotated[AuthenticatedUser, _REVIEWER_RBAC],
    document_id: Annotated[str | None, Query()] = None,
) -> ApiResponse[ClauseReviewDTO] | JSONResponse:
    ctx = await _clause_with_access(
        svc,
        node_id,
        user,
        AclAction.REVIEW_MUTATE,
        document_id=document_id,
        node=body.node.model_dump() if body.node else None,
    )
    try:
        state = await svc.submit_clause_review(
            ctx=ctx,
            action_type=ReviewActionType(body.action),
            base_version=body.base_version,
            reviewer_id=user.user_id,
            comment=body.comment,
            corrected_value=body.corrected_value,
        )
    except ReviewVersionConflict as exc:
        conflict = ReviewConflictResponseDTO(
            error=ReviewConflictErrorDTO(
                code="VERSION_CONFLICT",
                message="Người khác vừa lưu thẩm định cho điều khoản này. Đã tải lại bản mới nhất.",
            ),
            current_state=exc.current_state,
            your_submitted_action=body.model_dump(mode="json"),
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=conflict.model_dump(mode="json"),
        )
    return ApiResponse(data=state)
