r"""Re-OCR Workbench router — Màn hình 9 (DOC-05b §5.9).

Endpoints:
    POST /documents/{id}/re-ocr          — Tạo yêu cầu re-OCR (202 Accepted)
    GET  /documents/{id}/re-ocr-requests — Theo dõi trạng thái
    GET  /re-ocr-requests/{id}           — Chi tiết 1 request
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Path, status

from contract_intelligence.extraction.application.dtos.reocr_dtos import (
    ReOcrRequestPayloadDTO,
    ReOcrRequestRecordDTO,
)
from contract_intelligence.extraction.interfaces.api.dependencies_reocr import (
    ReOcrServiceDep,
)
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user, require_role
from contract_intelligence.shared.responses import ApiResponse

router = APIRouter(tags=["ReOCR"])


@router.post(
    "/documents/{document_id}/re-ocr",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[ReOcrRequestRecordDTO],
    summary="Tạo yêu cầu re-OCR",
    responses={
        400: {"description": "Invalid payload"},
        403: {"description": "Insufficient role"},
    },
)
async def create_reocr_request(
    document_id: Annotated[str, Path(min_length=1)],
    body: Annotated[ReOcrRequestPayloadDTO, Body()],
    svc: ReOcrServiceDep,
    user: Annotated[
        AuthenticatedUser, Depends(require_role("OPERATOR", "REVIEWER", "ADMINISTRATOR"))
    ],
    background_tasks: BackgroundTasks,
) -> ApiResponse[ReOcrRequestRecordDTO]:
    """RBAC: OPERATOR, REVIEWER, ADMINISTRATOR. OpenAPI ReOcrRequestPayload → 202."""
    record = await svc.create_request(
        document_id=document_id,
        profile=body.profile,
        page_numbers=body.page_numbers,
        reason=body.reason or "",
        requested_by=user.user_id,
        background_tasks=background_tasks,
    )
    return ApiResponse(data=record)


@router.get(
    "/documents/{document_id}/re-ocr-requests",
    response_model=ApiResponse[list[ReOcrRequestRecordDTO]],
    summary="List re-OCR requests cho document",
)
async def list_reocr_requests(
    document_id: Annotated[str, Path(min_length=1)],
    svc: ReOcrServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[list[ReOcrRequestRecordDTO]]:
    return ApiResponse(data=await svc.list_requests(document_id))


@router.get(
    "/re-ocr-requests/{request_id}",
    response_model=ApiResponse[ReOcrRequestRecordDTO],
    summary="Chi tiết 1 re-OCR request — poll status",
    responses={404: {"description": "Request not found"}},
)
async def get_reocr_request(
    request_id: Annotated[str, Path(min_length=1)],
    svc: ReOcrServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[ReOcrRequestRecordDTO]:
    """Poll status của 1 re-OCR request — frontend polling endpoint."""
    return ApiResponse(data=await svc.get_request(request_id))
