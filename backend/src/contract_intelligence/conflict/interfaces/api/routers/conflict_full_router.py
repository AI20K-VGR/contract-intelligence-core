r"""Conflict bounded context router — Phase 2 findings & conflicts.

Endpoints:
    GET  /dossiers/{id}/findings     — List findings (all dispositions)
    GET  /dossiers/{id}/conflicts    — Findings needing review (= v_conflict)
    GET  /findings/{id}              — Finding detail
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from contract_intelligence.conflict.application.dtos.finding_dtos import FindingDTO
from contract_intelligence.conflict.interfaces.api.dependencies import (
    ConflictServiceDep,
)
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
from contract_intelligence.shared.responses import ApiMeta, ApiResponse

router = APIRouter(tags=["Conflict"])


@router.get(
    "/dossiers/{dossier_id}/findings",
    response_model=ApiResponse[list[FindingDTO]],
    summary="List findings trong dossier",
)
async def list_findings(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ConflictServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    disposition: Annotated[str | None, Query()] = None,
    scope: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[list[FindingDTO]]:
    """Danh sách phát hiện xung đột / điều chỉnh giữa hợp đồng & phụ lục."""
    items, total = await svc.list_findings(
        dossier_id,
        disposition=disposition,
        scope=scope,
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
    "/dossiers/{dossier_id}/conflicts",
    response_model=ApiResponse[list[FindingDTO]],
    summary="Findings needing reviewer (= v_conflict)",
)
async def list_conflicts(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ConflictServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[list[FindingDTO]]:
    """Subset of findings: disposition in conflict set OR confidence < 0.6."""
    items, total = await svc.list_conflicts(dossier_id, limit=limit, offset=offset)
    return ApiResponse(
        data=items,
        meta=ApiMeta(
            total=total,
            page=(offset // limit) + 1,
            page_size=limit,
        ),
    )


@router.get(
    "/findings/{finding_id}",
    response_model=ApiResponse[FindingDTO],
    responses={404: {"description": "Finding not found"}},
)
async def get_finding(
    finding_id: Annotated[str, Path(min_length=1)],
    svc: ConflictServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[FindingDTO]:
    """Chi tiết finding: severity, 2 phía đối sánh."""
    return ApiResponse(data=await svc.get_finding(finding_id))
