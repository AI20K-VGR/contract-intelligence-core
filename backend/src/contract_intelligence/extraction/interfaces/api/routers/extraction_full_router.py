r"""Extraction bounded context router — Màn hình 4, 5, 6 (DOC-05b §5.4, §5.5, §5.6).

Endpoints (Màn hình 4 — Pipeline Run):
    POST  /dossiers/{id}/runs         — Trigger new pipeline run
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

from fastapi import APIRouter, BackgroundTasks, Depends, Path, Query, Response, status
from fastapi.responses import StreamingResponse

from contract_intelligence.extraction.application.dtos.clause_dtos import ClauseNodeDTO
from contract_intelligence.extraction.application.dtos.fact_effective_dtos import (
    FactEffectiveDTO,
)
from contract_intelligence.extraction.application.dtos.page_dtos import PageDTO
from contract_intelligence.extraction.application.dtos.table_dtos import DocTableDTO
from contract_intelligence.extraction.interfaces.api.dependencies import (
    ExtractionServiceDep,
)
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user, require_role
from contract_intelligence.shared.responses import ApiResponse

router = APIRouter(tags=["Extraction"])


# -----------------------------------------------------------------------------
# Màn hình 4 — Pipeline runs
# -----------------------------------------------------------------------------


@router.post(
    "/dossiers/{dossier_id}/runs",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[dict[str, Any]],
    summary="Trigger pipeline run",
    responses={
        403: {"description": "Insufficient role"},
        404: {"description": "Dossier not found"},
    },
)
async def trigger_run(
    dossier_id: Annotated[str, Path(min_length=1)],
    svc: ExtractionServiceDep,
    user: Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))],
    background_tasks: BackgroundTasks,
) -> ApiResponse[dict[str, Any]]:
    """Kích hoạt pipeline run mới. RBAC: ADMINISTRATOR inherits OPERATOR.

    Background orchestrator sẽ chạy OCR → Extract → Compare chain qua AI service.
    Frontend poll GET /runs/{id} để theo dõi tiến độ.
    """
    run = await svc.trigger_pipeline_run(
        dossier_id=dossier_id,
        trace_id=str(user.user_id),
        background_tasks=background_tasks,
    )
    return ApiResponse(
        data={
            "id": run.id,
            "tenant_id": run.tenant_id,
            "dossier_id": run.dossier_id,
            "status": run.status.value,
            "pipeline_version": run.pipeline_version,
            "git_sha": run.git_sha,
            "trace_id": run.trace_id,
            "created_at": run.created_at.isoformat(),
        }
    )


@router.get(
    "/runs",
    response_model=ApiResponse[dict[str, Any]],
    summary="List pipeline runs",
)
async def list_runs(
    svc: ExtractionServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    dossier_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[dict[str, Any]]:
    """Danh sách runs trong tenant."""
    items, total = await svc.list_pipeline_runs(dossier_id=dossier_id, limit=limit, offset=offset)
    return ApiResponse(
        data={
            "items": [
                {
                    "id": r.id,
                    "dossier_id": r.dossier_id,
                    "status": r.status.value,
                    "pipeline_version": r.pipeline_version,
                    "created_at": r.created_at.isoformat(),
                    "finished_at": (
                        r.finished_at.isoformat()
                        if hasattr(r.finished_at, "isoformat")
                        else r.finished_at
                    )
                    if r.finished_at
                    else None,
                }
                for r in items
            ],
            "total": total,
            "page": (offset // limit) + 1,
            "page_size": limit,
            "total_pages": (total + limit - 1) // limit if total > 0 else 0,
        }
    )


@router.get(
    "/runs/{run_id}",
    response_model=ApiResponse[dict[str, Any]],
    responses={404: {"description": "Run not found"}},
)
async def get_run(
    run_id: Annotated[str, Path(min_length=1)],
    svc: ExtractionServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    """Chi tiết run + config snapshot."""
    run = await svc.get_pipeline_run(run_id)
    return ApiResponse(
        data={
            "id": run.id,
            "tenant_id": run.tenant_id,
            "dossier_id": run.dossier_id,
            "status": run.status.value,
            "pipeline_version": run.pipeline_version,
            "git_sha": run.git_sha,
            "trace_id": run.trace_id,
            "created_at": run.created_at.isoformat(),
            "finished_at": (
                run.finished_at.isoformat()
                if hasattr(run.finished_at, "isoformat")
                else run.finished_at
            )
            if run.finished_at
            else None,
        }
    )


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
    response_model=ApiResponse[dict[str, Any]],
    summary="Cancel running pipeline run",
    responses={
        403: {"description": "Insufficient role"},
        404: {"description": "Run not found or not cancellable"},
    },
)
async def cancel_run(
    run_id: Annotated[str, Path(min_length=1)],
    svc: ExtractionServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))],
) -> ApiResponse[dict[str, Any]]:
    """Hủy run đang chạy. RBAC: ADMINISTRATOR inherits OPERATOR."""
    run = await svc.cancel_pipeline_run(run_id)
    return ApiResponse(
        data={
            "id": run.id,
            "status": run.status.value,
        }
    )


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
    # Weak ETag from max current_version — UI can use for cache/concurrency hints
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
