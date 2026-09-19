r"""Conflict bounded context router — Màn hình 7 (DOC-05b §5.7).

Endpoints:
    GET  /dossiers/{id}/findings     — List findings
    GET  /findings/{id}              — Finding detail
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query

from contract_intelligence.conflict.interfaces.api.dependencies import (
    ConflictServiceDep,
)
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
from contract_intelligence.shared.responses import ApiResponse

router = APIRouter(tags=["Conflict"])


@router.get(
    "/dossiers/{dossier_id}/findings",
    response_model=ApiResponse[dict[str, Any]],
    summary="List findings trong dossier",
)
async def list_findings(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ConflictServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[dict[str, Any]]:
    """Danh sách phát hiện xung đột / điều chỉnh giữa hợp đồng & phụ lục."""
    items, total = await svc.list_findings(dossier_id, limit=limit, offset=offset)
    return ApiResponse(
        data={
            "items": items,
            "total": total,
            "page": (offset // limit) + 1,
            "page_size": limit,
            "total_pages": (total + limit - 1) // limit if total > 0 else 0,
        }
    )


@router.get(
    "/findings/{finding_id}",
    response_model=ApiResponse[dict[str, Any]],
    responses={404: {"description": "Finding not found"}},
)
async def get_finding(
    finding_id: Annotated[str, Path(min_length=1)],
    svc: ConflictServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    """Chi tiết finding: severity, 2 phía đối sánh."""
    return ApiResponse(data=await svc.get_finding(finding_id))
