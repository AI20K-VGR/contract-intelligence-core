r"""Extraction bounded context router — Màn hình 4, 5, 6 (DOC-05b §5.4, §5.5, §5.6).

Endpoints (Màn hình 4 — Pipeline Run):
    POST  /dossiers/{id}/runs         — Trigger new pipeline run
    POST  /dossiers/{id}/reprocess    — Reprocess (new immutable run)
    GET   /runs                       — List runs
    GET   /runs/{id}                  — Run status + config
    GET   /runs/{id}/steps            — 11 steps S0..S10 status
    POST  /runs/{id}/cancel           — Cancel running run

Endpoints (Màn hình 5 — PDF Explorer):
    GET   /documents/{id}/pages       — List pages with metadata
    GET   /pages/{id}                 — Page detail with OCR lines
    GET   /documents/{id}/clauses     — Clause tree
    GET   /documents/{id}/tables      — Tables list

Endpoints (Màn hình 6 — Fact Inspector):
    GET   /documents/{id}/facts       — List facts
    GET   /facts/{id}                 — Fact detail
    GET   /citations/{id}             — Citation detail
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Path, Query, Response, status
from fastapi.responses import StreamingResponse

from contract_intelligence.extraction.application.dtos.clause_dtos import ClauseNodeDTO
from contract_intelligence.extraction.application.dtos.fact_effective_dtos import (
    FactEffectiveDTO,
)
from contract_intelligence.extraction.application.dtos.page_dtos import PageDTO
from contract_intelligence.extraction.application.dtos.run_dtos import (
    CreateRunRequestDTO,
    PipelineRunSummaryDTO,
    ReprocessAcceptedDTO,
)
from contract_intelligence.extraction.application.dtos.table_dtos import DocTableDTO
from contract_intelligence.extraction.interfaces.api.dependencies import (
    ExtractionServiceDep,
)
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user, require_role
from contract_intelligence.shared.responses import ApiMeta, ApiResponse

router = APIRouter(tags=["Extraction"])


# -----------------------------------------------------------------------------
# Màn hình 4 — Pipeline runs
# -----------------------------------------------------------------------------


@router.post(
    "/dossiers/{dossier_id}/runs",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[PipelineRunSummaryDTO],
    summary="Trigger pipeline run",
    responses={
        403: {"description": "Insufficient role"},
        404: {"description": "Dossier not found"},
        409: {"description": "Active run already exists"},
    },
)
async def trigger_run(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ExtractionServiceDep,
    user: Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))],
    background_tasks: BackgroundTasks,
    body: Annotated[CreateRunRequestDTO | None, Body()] = None,
) -> ApiResponse[PipelineRunSummaryDTO]:
    """Kích hoạt pipeline run mới. RBAC: ADMINISTRATOR inherits OPERATOR."""
    override = (
        body.config_override.model_dump(exclude_none=True)
        if body and body.config_override
        else None
    )
    run = await svc.trigger_pipeline_run(
        dossier_id=dossier_id,
        trace_id=str(user.user_id),
        background_tasks=background_tasks,
        config_override=override,
    )
    return ApiResponse(data=svc.to_summary(run, triggered_by=user.user_id))


@router.post(
    "/dossiers/{dossier_id}/reprocess",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[ReprocessAcceptedDTO],
    summary="Reprocess dossier (new immutable pipeline run)",
    responses={
        403: {"description": "Insufficient role"},
        404: {"description": "Dossier not found"},
        409: {"description": "Active run already exists"},
    },
)
async def reprocess_dossier(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ExtractionServiceDep,
    user: Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))],
    background_tasks: BackgroundTasks,
) -> ApiResponse[ReprocessAcceptedDTO]:
    accepted = await svc.reprocess_dossier(
        dossier_id=dossier_id,
        background_tasks=background_tasks,
        trace_id=str(user.user_id),
    )
    return ApiResponse(data=accepted)


@router.get(
    "/runs",
    response_model=ApiResponse[list[PipelineRunSummaryDTO]],
    summary="List pipeline runs",
)
async def list_runs(
    svc: ExtractionServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    dossier_id: Annotated[str | None, Query()] = None,
    status_filter: Annotated[
        str | None,
        Query(
            alias="status",
            pattern="^(queued|running|completed|failed|cancelled)$",
        ),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[list[PipelineRunSummaryDTO]]:
    """Danh sách runs trong tenant — OpenAPI status filter (completed↔succeeded)."""
    items, total = await svc.list_pipeline_runs(
        dossier_id=dossier_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(
        data=[svc.to_summary(r) for r in items],
        meta=ApiMeta(
            page=(offset // limit) + 1,
            page_size=limit,
            total=total,
        ),
    )


@router.get(
    "/runs/{run_id}",
    response_model=ApiResponse[PipelineRunSummaryDTO],
    responses={404: {"description": "Run not found"}},
)
async def get_run(
    run_id: Annotated[str, Path(min_length=1)],
    svc: ExtractionServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[PipelineRunSummaryDTO]:
    """Chi tiết run + config snapshot."""
    run = await svc.get_pipeline_run(run_id)
    return ApiResponse(data=svc.to_summary(run))


@router.get(
    "/runs/{run_id}/steps",
    response_model=ApiResponse[list[Any]],
    summary="11 steps S0..S10 status",
)
async def get_run_steps(
    run_id: Annotated[str, Path(min_length=1)],
    svc: ExtractionServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[list[Any]]:
    """Tiến độ từng bước S0..S10 (DOC-05b Màn hình 4)."""
    steps = await svc.get_pipeline_steps(run_id)
    return ApiResponse(data=steps)


@router.post(
    "/runs/{run_id}/cancel",
    response_model=ApiResponse[PipelineRunSummaryDTO],
    summary="Cancel running pipeline run",
    responses={
        403: {"description": "Insufficient role"},
        404: {"description": "Run not found"},
        409: {"description": "Run not cancellable"},
    },
)
async def cancel_run(
    run_id: Annotated[str, Path(min_length=1)],
    svc: ExtractionServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))],
) -> ApiResponse[PipelineRunSummaryDTO]:
    """Hủy run đang chạy. RBAC: ADMINISTRATOR inherits OPERATOR."""
    run = await svc.cancel_pipeline_run(run_id)
    return ApiResponse(data=svc.to_summary(run))


# -----------------------------------------------------------------------------
# Màn hình 5 — PDF Document Explorer (Phase 2)
# -----------------------------------------------------------------------------


@router.get(
    "/documents/{document_id}/pages",
    response_model=ApiResponse[list[PageDTO]],
    summary="List pages of document",
)
async def list_pages(
    document_id: Annotated[str, Path(min_length=1)],
    svc: ExtractionServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[list[PageDTO]]:
    """Danh sách trang + kích thước + link ảnh."""
    return ApiResponse(data=await svc.list_pages(document_id))


@router.get(
    "/documents/{document_id}/pages/{page_no}/image",
    summary="Stream page image (PNG/WebP) from storage",
    responses={
        200: {
            "content": {"image/png": {}, "image/webp": {}},
            "description": "Page image binary",
        },
        404: {"description": "Page or image not found"},
    },
)
async def get_page_image(
    document_id: Annotated[str, Path(min_length=1)],
    page_no: Annotated[int, Path(ge=1)],
    svc: ExtractionServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    variant: Annotated[str, Query(pattern="^(preview|render)$")] = "preview",
) -> StreamingResponse:
    """Ảnh trang — variant=preview|render (default preview)."""
    data, media_type = await svc.get_page_image(document_id, page_no, variant=variant)
    return StreamingResponse(
        iter([data]),
        media_type=media_type,
        headers={"Content-Length": str(len(data))},
    )


@router.get(
    "/pages/{page_id}",
    response_model=ApiResponse[dict[str, Any]],
    responses={404: {"description": "Page not found"}},
)
async def get_page(
    page_id: Annotated[str, Path(min_length=1)],
    svc: ExtractionServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    """Page detail + OCR lines."""
    return ApiResponse(data=await svc.get_page(page_id))


@router.get(
    "/documents/{document_id}/clauses",
    response_model=ApiResponse[list[ClauseNodeDTO]],
    summary="Clause tree of document",
)
async def list_clauses(
    document_id: Annotated[str, Path(min_length=1)],
    svc: ExtractionServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    run_id: Annotated[str | None, Query()] = None,
) -> ApiResponse[list[ClauseNodeDTO]]:
    """Cây điều khoản (article > clause > point)."""
    return ApiResponse(data=await svc.list_clauses(document_id, run_id=run_id))


@router.get(
    "/documents/{document_id}/tables",
    response_model=ApiResponse[list[DocTableDTO]],
    summary="Tables detected in document",
)
async def list_tables(
    document_id: Annotated[str, Path(min_length=1)],
    svc: ExtractionServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    run_id: Annotated[str | None, Query()] = None,
) -> ApiResponse[list[DocTableDTO]]:
    """Bảng biểu phát hiện được + cells."""
    return ApiResponse(data=await svc.list_tables(document_id, run_id=run_id))


# -----------------------------------------------------------------------------
# Màn hình 6 — Fact & Extraction Inspector (Phase 2)
# -----------------------------------------------------------------------------


@router.get(
    "/dossiers/{dossier_id}/facts",
    response_model=ApiResponse[list[FactEffectiveDTO]],
    summary="List facts + effective values (with current_version)",
    responses={200: {"description": "FactEffective list; ETag for dossier-level concurrency"}},
)
async def list_dossier_facts(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ExtractionServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    response: Response,
    effective: Annotated[
        bool,
        Query(description="If true, include current_version for optimistic concurrency"),
    ] = True,
    key: Annotated[str | None, Query(description="Filter by fact key")] = None,
) -> ApiResponse[list[FactEffectiveDTO]]:
    """FactEffective list — client MUST echo current_version as base_version on actions."""
    items = await svc.list_dossier_facts(dossier_id, key=key, effective=effective)
    max_ver = max((i.current_version for i in items), default=0)
    response.headers["ETag"] = f'W/"facts-{dossier_id}-{len(items)}-v{max_ver}"'
    return ApiResponse(data=items)


@router.get(
    "/documents/{document_id}/facts",
    response_model=ApiResponse[list[Any]],
    summary="List facts extracted from document",
)
async def list_facts(
    document_id: Annotated[str, Path(min_length=1)],
    svc: ExtractionServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[list[Any]]:
    """Danh sách fact có (key, raw_text, normalized_value) — document-scoped."""
    return ApiResponse(data=await svc.list_facts(document_id))


@router.get(
    "/facts/{fact_id}",
    response_model=ApiResponse[dict[str, Any]],
    responses={404: {"description": "Fact not found"}},
)
async def get_fact(
    fact_id: Annotated[str, Path(min_length=1)],
    svc: ExtractionServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    """Chi tiết fact + citation."""
    return ApiResponse(data=await svc.get_fact(fact_id))


@router.get(
    "/citations/{citation_id}",
    response_model=ApiResponse[dict[str, Any]],
    responses={404: {"description": "Citation not found"}},
)
async def get_citation(
    citation_id: Annotated[str, Path(min_length=1)],
    svc: ExtractionServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    """Citation chi tiết + quote + segments bbox."""
    return ApiResponse(data=await svc.get_citation(citation_id))
