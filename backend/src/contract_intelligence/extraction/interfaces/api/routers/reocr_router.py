r"""Re-OCR Workbench router — Màn hình 9 (DOC-05b §5.9).

Endpoints:
    POST /documents/{id}/re-ocr          — Tạo yêu cầu re-OCR (submit AI service async)
    GET  /documents/{id}/re-ocr-requests — Theo dõi trạng thái
    GET  /re-ocr-requests/{id}           — Chi tiết 1 request
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Path
from pydantic import BaseModel, ConfigDict, Field

from contract_intelligence.extraction.interfaces.api.dependencies_reocr import (
    ReOcrServiceDep,
)
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user, require_role
from contract_intelligence.shared.responses import ApiResponse

router = APIRouter(tags=["ReOCR"])


class ReOcrOptions(BaseModel):
    """Tùy chọn xử lý ảnh nâng cao."""

    model_config = ConfigDict(extra="forbid")
    deskew: bool = False
    denoise: bool = False
    enhance_dpi: int = Field(default=300, ge=72, le=600)
    engine: str = Field(default="terra_advanced")


class ReOcrRequest(BaseModel):
    """Body cho POST /documents/{id}/re-ocr."""

    model_config = ConfigDict(extra="forbid")
    page_ids: list[str] = Field(..., min_length=1)
    reason: str = Field(..., min_length=1, max_length=2000)
    options: ReOcrOptions = Field(default_factory=ReOcrOptions)


@router.post(
    "/documents/{document_id}/re-ocr",
    response_model=ApiResponse[dict[str, Any]],
    summary="Tạo yêu cầu re-OCR",
    responses={
        400: {"description": "page_ids rỗng"},
        403: {"description": "Insufficient role"},
    },
)
async def create_reocr_request(
    document_id: Annotated[str, Path(min_length=1)],
    body: Annotated[ReOcrRequest, Body()],
    svc: ReOcrServiceDep,
    user: Annotated[
        AuthenticatedUser, Depends(require_role("OPERATOR", "REVIEWER", "ADMINISTRATOR"))
    ],
    background_tasks: BackgroundTasks,
) -> ApiResponse[dict[str, Any]]:
    """RBAC: OPERATOR, REVIEWER, ADMINISTRATOR.

    Submit ReOcrJobRequest sang AI service (DOC-05c §4.2) async qua dispatcher.
    Polling trạng thái tự động — frontend poll GET /documents/{id}/re-ocr-requests.
    """
    return ApiResponse(
        data=await svc.create_request(
            document_id=document_id,
            page_ids=body.page_ids,
            reason=body.reason,
            options=body.options.model_dump(),
            requested_by=user.user_id,
            background_tasks=background_tasks,
        )
    )


@router.get(
    "/documents/{document_id}/re-ocr-requests",
    response_model=ApiResponse[list[Any]],
    summary="List re-OCR requests cho document",
)
async def list_reocr_requests(
    document_id: Annotated[str, Path(min_length=1)],
    svc: ReOcrServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[list[Any]]:
    return ApiResponse(data=await svc.list_requests(document_id))


@router.get(
    "/re-ocr-requests/{request_id}",
    response_model=ApiResponse[dict[str, Any]],
    summary="Chi tiết 1 re-OCR request — poll status",
    responses={404: {"description": "Request not found"}},
)
async def get_reocr_request(
    request_id: Annotated[str, Path(min_length=1)],
    svc: ReOcrServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    """Poll status của 1 re-OCR request — frontend polling endpoint."""
    return ApiResponse(data=await svc.get_request(request_id))
