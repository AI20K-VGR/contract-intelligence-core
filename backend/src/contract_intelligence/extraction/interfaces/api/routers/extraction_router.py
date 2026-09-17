"""GET /extraction/documents/{id}/facts — list fact của document (run hiện hành)."""

from __future__ import annotations

from fastapi import APIRouter

from contract_intelligence.shared.responses import ApiResponse

router = APIRouter()


@router.get("/documents/{document_id}/facts", response_model=ApiResponse[list])
async def list_facts(document_id: str) -> ApiResponse[list]:
    return ApiResponse(data=[])
