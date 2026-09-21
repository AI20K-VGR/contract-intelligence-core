"""GET /conflict/dossiers/{id}/findings."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
from contract_intelligence.shared.responses import ApiResponse

router = APIRouter()


@router.get("/dossiers/{dossier_id}/findings", response_model=ApiResponse[list[object]])
async def list_findings(
    dossier_id: str,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[list[object]]:
    return ApiResponse(data=[])
