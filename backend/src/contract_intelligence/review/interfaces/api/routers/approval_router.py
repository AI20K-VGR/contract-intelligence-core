r"""Approval bounded context router — Màn hình 8 (DOC-05b §5.8).

Endpoints:
    POST /dossiers/{id}/lock                       — Khóa dossier
    POST /dossiers/{id}/approve                    — Ký duyệt nội bộ
    POST /dossiers/{id}/external-approvals         — Tạo token + URL gửi đối tác
    GET  /dossiers/{id}/external-approvals         — Danh sách external approvals
    POST /external-approvals/callback              — Webhook nhận response từ ngoài
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Path, status
from pydantic import BaseModel, ConfigDict, Field

from contract_intelligence.review.interfaces.api.dependencies_approval import (
    ApprovalServiceDep,
)
from contract_intelligence.shared.auth import (
    AuthenticatedUser,
    get_current_user,
    require_role,
)
from contract_intelligence.shared.responses import ApiResponse

router = APIRouter(tags=["Approval"])


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------


class ExternalApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient_email: str = Field(..., min_length=3, max_length=255)
    recipient_name: str | None = None
    expires_in_days: int = Field(default=7, ge=1, le=90)


class ExternalApprovalCallback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str
    status: str = Field(..., description="approved | rejected")
    payload: dict[str, Any] | None = None


# -----------------------------------------------------------------------------
# Lock + Approve
# -----------------------------------------------------------------------------


@router.post(
    "/dossiers/{dossier_id}/lock",
    response_model=ApiResponse[dict[str, Any]],
    summary="Khóa dossier — không cho sửa đổi",
    responses={
        403: {"description": "Insufficient role"},
        404: {"description": "Dossier not found"},
    },
)
async def lock_dossier(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ApprovalServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(require_role("REVIEWER", "ADMINISTRATOR"))],
) -> ApiResponse[dict[str, Any]]:
    """RBAC: REVIEWER, ADMINISTRATOR (ADMINISTRATOR inherits REVIEWER)."""
    return ApiResponse(data=await svc.lock_dossier(dossier_id))


@router.post(
    "/dossiers/{dossier_id}/approve",
    response_model=ApiResponse[dict[str, Any]],
    summary="Ký duyệt chính thức — tạo snapshot checksum",
    responses={
        403: {"description": "Insufficient role"},
        404: {"description": "Dossier not found"},
    },
)
async def approve_dossier(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ApprovalServiceDep,
    user: Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))],
) -> ApiResponse[dict[str, Any]]:
    """RBAC: ADMINISTRATOR only (top-level role)."""
    return ApiResponse(data=await svc.approve_dossier(dossier_id, user.user_id))


# -----------------------------------------------------------------------------
# External approvals
# -----------------------------------------------------------------------------


@router.post(
    "/dossiers/{dossier_id}/external-approvals",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[dict[str, Any]],
    summary="Tạo external approval token",
    responses={
        403: {"description": "Insufficient role"},
        404: {"description": "Dossier not found"},
    },
)
async def create_external_approval(
    dossier_id: Annotated[str, Path(min_length=1)],
    body: Annotated[ExternalApprovalRequest, Body()],
    svc: ApprovalServiceDep,
    user: Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))],
) -> ApiResponse[dict[str, Any]]:
    """RBAC: ADMINISTRATOR only (top-level role)."""
    return ApiResponse(
        data=await svc.create_external_approval(
            dossier_id=dossier_id,
            recipient_email=body.recipient_email,
            recipient_name=body.recipient_name,
            created_by=user.user_id,
            expires_in_days=body.expires_in_days,
        )
    )


@router.get(
    "/dossiers/{dossier_id}/external-approvals",
    response_model=ApiResponse[list[Any]],
    summary="List external approvals",
)
async def list_external_approvals(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ApprovalServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[list[Any]]:
    return ApiResponse(data=await svc.list_external_approvals(dossier_id))


@router.post(
    "/external-approvals/callback",
    response_model=ApiResponse[dict[str, Any]],
    summary="Webhook nhận response từ DocuSign/SAP/ERP",
)
async def external_approval_callback(
    body: Annotated[ExternalApprovalCallback, Body()],
    svc: ApprovalServiceDep,
) -> ApiResponse[dict[str, Any]]:
    """Public webhook — không cần auth (dùng X-Internal-Service-Key ở Sprint 4)."""
    return ApiResponse(
        data=await svc.handle_external_callback(
            token=body.token, status=body.status, payload=body.payload
        )
    )
