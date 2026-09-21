r"""Approval bounded context router — Màn hình 8 (DOC-05b §5.8) / Phase 5 OpenAPI.

Endpoints:
    POST /dossiers/{id}/lock                       — Khóa dossier
    POST /dossiers/{id}/approve                    — Ký duyệt nội bộ
    POST /dossiers/{id}/external-approvals         — Tạo grant gửi đối tác
    GET  /dossiers/{id}/external-approvals         — Danh sách external approvals
    POST /external-approvals/callback              — Webhook nhận response từ ngoài
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, status

from contract_intelligence.contract.application.dtos.dossier_dtos import DossierDetailDTO
from contract_intelligence.review.application.dtos.approval_dtos import (
    ApproveRequestDTO,
    ExternalApprovalCallbackDTO,
    ExternalApprovalGrantDTO,
    ExternalApprovalRequestDTO,
)
from contract_intelligence.review.interfaces.api.dependencies_approval import (
    ApprovalServiceDep,
)
from contract_intelligence.shared.auth import (
    AuthenticatedUser,
    require_role,
)
from contract_intelligence.shared.responses import ApiResponse

router = APIRouter(tags=["Approval"])


@router.post(
    "/dossiers/{dossier_id}/lock",
    response_model=ApiResponse[DossierDetailDTO],
    summary="Khóa dossier — không cho sửa đổi",
    responses={
        403: {"description": "Insufficient role"},
        404: {"description": "Dossier not found"},
        409: {"description": "Already locked"},
    },
)
async def lock_dossier(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ApprovalServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(require_role("REVIEWER", "ADMINISTRATOR"))],
) -> ApiResponse[DossierDetailDTO]:
    """RBAC: REVIEWER, ADMINISTRATOR."""
    return ApiResponse(data=await svc.lock_dossier(dossier_id))


@router.post(
    "/dossiers/{dossier_id}/approve",
    response_model=ApiResponse[DossierDetailDTO],
    summary="Ký duyệt chính thức — tạo snapshot checksum",
    responses={
        403: {"description": "Insufficient role"},
        404: {"description": "Dossier not found"},
        409: {"description": "Preconditions not met"},
    },
)
async def approve_dossier(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ApprovalServiceDep,
    user: Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))],
    body: Annotated[ApproveRequestDTO | None, Body()] = None,
) -> ApiResponse[DossierDetailDTO]:
    """RBAC: ADMINISTRATOR only."""
    comment = body.comment if body else None
    return ApiResponse(data=await svc.approve_dossier(dossier_id, user.user_id, comment=comment))


@router.post(
    "/dossiers/{dossier_id}/external-approvals",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[ExternalApprovalGrantDTO],
    summary="Tạo external approval grant",
    responses={
        403: {"description": "Insufficient role"},
        404: {"description": "Dossier not found"},
        409: {"description": "Not approved or pending grant exists"},
    },
)
async def create_external_approval(
    dossier_id: Annotated[str, Path(min_length=1)],
    body: Annotated[ExternalApprovalRequestDTO, Body()],
    svc: ApprovalServiceDep,
    user: Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))],
) -> ApiResponse[ExternalApprovalGrantDTO]:
    """RBAC: ADMINISTRATOR only."""
    return ApiResponse(
        data=await svc.create_external_approval(
            dossier_id=dossier_id,
            provider=body.provider,
            approver_email=body.approver_email,
            approver_name=body.approver_name,
            created_by=user.user_id,
            expires_in_hours=body.expires_in_hours,
            notes=body.notes,
        )
    )


@router.get(
    "/dossiers/{dossier_id}/external-approvals",
    response_model=ApiResponse[list[ExternalApprovalGrantDTO]],
    summary="List external approvals",
)
async def list_external_approvals(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ApprovalServiceDep,
    _user: Annotated[
        AuthenticatedUser, Depends(require_role("OPERATOR", "REVIEWER", "ADMINISTRATOR"))
    ],
) -> ApiResponse[list[ExternalApprovalGrantDTO]]:
    return ApiResponse(data=await svc.list_external_approvals(dossier_id))


@router.post(
    "/external-approvals/callback",
    response_model=ApiResponse[ExternalApprovalGrantDTO],
    summary="Webhook nhận response từ DocuSign/SAP/ERP",
    responses={
        403: {"description": "Insufficient role"},
        404: {"description": "Grant not found"},
    },
)
async def external_approval_callback(
    body: Annotated[ExternalApprovalCallbackDTO, Body()],
    svc: ApprovalServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))],
) -> ApiResponse[ExternalApprovalGrantDTO]:
    """OpenAPI x-rbac: ADMINISTRATOR."""
    return ApiResponse(
        data=await svc.handle_external_callback(
            grant_id=body.grant_id,
            status=body.status,
            external_reference_id=body.external_reference_id,
            digital_signature_hash=body.digital_signature_hash,
            signature_certificate=body.signature_certificate,
            signed_at=body.signed_at,
        )
    )
