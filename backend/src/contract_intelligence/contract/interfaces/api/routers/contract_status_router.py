"""GET /dossiers/{id}, GET /jobs/{id} — truy vấn trạng thái."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
from contract_intelligence.shared.responses import ApiResponse

router = APIRouter()


@router.get("/{dossier_id}", response_model=ApiResponse[dict[str, object]])
async def get_dossier_status(
    dossier_id: str,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, object]]:
    """Trả về trạng thái dossier + latest job."""
    # status_service: ContractStatusService = Depends(...)  # Sprint 2
    # snapshot = await status_service.get_dossier_status(dossier_id)
    return ApiResponse(data={"dossier_id": dossier_id, "status": "placeholder"})


@router.get(
    "/{dossier_id}/jobs/{job_id}",
    response_model=ApiResponse[dict[str, object]],
)
async def get_job_status(
    dossier_id: str,
    job_id: str,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _status_code: int = status.HTTP_200_OK,
) -> ApiResponse[dict[str, object]]:
    return ApiResponse(data={"dossier_id": dossier_id, "job_id": job_id})
