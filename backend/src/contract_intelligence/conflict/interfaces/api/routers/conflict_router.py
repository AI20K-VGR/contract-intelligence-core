"""GET /conflict/dossiers/{id}/findings."""

from __future__ import annotations

from fastapi import APIRouter

from contract_intelligence.shared.responses import ApiResponse

router = APIRouter()


@router.get("/dossiers/{dossier_id}/findings", response_model=ApiResponse[list])
async def list_findings(dossier_id: str) -> ApiResponse[list]:
    return ApiResponse(data=[])
