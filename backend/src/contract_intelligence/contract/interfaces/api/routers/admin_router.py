r"""Admin/Ops routers — Màn hình 2 (Batches + Ops Metrics) + Màn hình 10 (Optimization Studio).

DOC-05b §5.2 + §5.10:
    GET  /batches
    POST /batches
    GET  /batches/{id}
    GET  /batches/{id}/summary
    POST /batches/{id}/cancel
    POST /batches/{id}/resume
    GET  /ops/metrics

    GET  /optimization/campaigns
    POST /optimization/campaigns
    GET  /optimization/campaigns/{id}
    GET  /optimization/candidates
    POST /optimization/candidates
    POST /optimization/candidates/{id}/promote
    GET  /optimization/experiments
    POST /optimization/experiments
    POST /optimization/experiments/{id}/run
    GET  /optimization/experiments/{id}/results
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    Path,
    Query,
    UploadFile,
    status,
)
from pydantic import BaseModel, ConfigDict, Field

from contract_intelligence.contract.application.dtos.batch_dtos import (
    BatchCreatedDTO,
    BatchDetailDTO,
    BatchListItemDTO,
)
from contract_intelligence.contract.interfaces.api.dependencies_admin import (
    BatchServiceDep,
    OptimizationServiceDep,
)
from contract_intelligence.shared.auth import (
    AuthenticatedUser,
    get_current_user,
    require_role,
)
from contract_intelligence.shared.exceptions import ValidationError
from contract_intelligence.shared.responses import ApiMeta, ApiResponse

router = APIRouter(tags=["Admin/Ops"])


# ============================================================================
# Batches — Màn hình 2
# ============================================================================


class CreateBatchNameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=255)


@router.post(
    "/batches",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[BatchCreatedDTO],
    summary="Tạo batch từ ZIP + manifest.csv",
    responses={
        400: {"description": "Invalid manifest"},
        403: {"description": "Insufficient role"},
    },
)
async def create_batch(
    svc: BatchServiceDep,
    user: Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))],
    manifest: Annotated[UploadFile, File(description="manifest.csv")],
    archive: Annotated[UploadFile, File(description="ZIP archive")],
    name: Annotated[str | None, Form()] = None,
) -> ApiResponse[BatchCreatedDTO]:
    """RBAC: ADMINISTRATOR inherits OPERATOR."""
    manifest_bytes = await manifest.read()
    archive_bytes = await archive.read()
    if not manifest_bytes:
        raise ValidationError("manifest.csv is required and must not be empty")
    if not archive_bytes:
        raise ValidationError("archive ZIP is required and must not be empty")
    try:
        created = await svc.create_batch(
            created_by=user.user_id,
            manifest_bytes=manifest_bytes,
            archive_bytes=archive_bytes,
            name=name,
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return ApiResponse(data=BatchCreatedDTO.model_validate(created))


@router.get(
    "/batches",
    response_model=ApiResponse[list[BatchListItemDTO]],
    summary="List batches",
)
async def list_batches(
    svc: BatchServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    status_filter: Annotated[
        str | None,
        Query(
            alias="status",
            pattern="^(processing|completed|partial_failed|failed|cancelled)$",
        ),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[list[BatchListItemDTO]]:
    items, total = await svc.list_batches(status=status_filter, limit=limit, offset=offset)
    return ApiResponse(
        data=[BatchListItemDTO.from_row(i) for i in items],
        meta=ApiMeta(
            page=(offset // limit) + 1,
            page_size=limit,
            total=total,
        ),
    )


@router.get(
    "/batches/{batch_id}",
    response_model=ApiResponse[BatchDetailDTO],
    responses={404: {"description": "Batch not found"}},
)
async def get_batch(
    batch_id: Annotated[str, Path(min_length=1)],
    svc: BatchServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[BatchDetailDTO]:
    row = await svc.get_batch(batch_id)
    item = BatchListItemDTO.from_row(row)
    return ApiResponse(data=BatchDetailDTO(**item.model_dump(), dossiers=row.get("dossiers") or []))


@router.get(
    "/batches/{batch_id}/summary",
    response_model=ApiResponse[dict[str, Any]],
    summary="Thống kê: succeeded, failed, pending_review, total_cost_usd",
)
async def get_batch_summary(
    batch_id: Annotated[str, Path(min_length=1)],
    svc: BatchServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await svc.get_summary(batch_id))


@router.post(
    "/batches/{batch_id}/cancel",
    response_model=ApiResponse[BatchDetailDTO],
    responses={
        403: {"description": "Insufficient role"},
        409: {"description": "Batch already terminal"},
    },
)
async def cancel_batch(
    batch_id: Annotated[str, Path(min_length=1)],
    svc: BatchServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))],
) -> ApiResponse[BatchDetailDTO]:
    """RBAC: ADMINISTRATOR inherits OPERATOR."""
    row = await svc.cancel_batch(batch_id)
    item = BatchListItemDTO.from_row(row)
    return ApiResponse(data=BatchDetailDTO(**item.model_dump(), dossiers=row.get("dossiers") or []))


@router.post(
    "/batches/{batch_id}/resume",
    response_model=ApiResponse[BatchDetailDTO],
    responses={
        403: {"description": "Insufficient role"},
        409: {"description": "Batch not resumable"},
    },
)
async def resume_batch(
    batch_id: Annotated[str, Path(min_length=1)],
    svc: BatchServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))],
) -> ApiResponse[BatchDetailDTO]:
    """RBAC: ADMINISTRATOR inherits OPERATOR."""
    row = await svc.resume_batch(batch_id)
    item = BatchListItemDTO.from_row(row)
    return ApiResponse(data=BatchDetailDTO(**item.model_dump(), dossiers=row.get("dossiers") or []))


# ============================================================================
# Ops Metrics
# ============================================================================


@router.get(
    "/ops/metrics",
    response_model=ApiResponse[dict[str, Any]],
    summary="Ops dashboard — server load, latency, cost theo ngày",
    responses={403: {"description": "ADMINISTRATOR only"}},
)
async def ops_metrics(
    _user: Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))],
) -> ApiResponse[dict[str, Any]]:
    """RBAC: ADMINISTRATOR only (top-level role)."""
    return ApiResponse(
        data={
            "by_day": [],
            "totals": {
                "tokens": 0,
                "cost_usd": 0.0,
                "latency_p50_ms": 0,
                "latency_p95_ms": 0,
            },
            "note": "Sprint 3 stub — wire usage_ledger in Sprint 4",
        }
    )


# ============================================================================
# Optimization Studio (Admin) — Màn hình 10
# ============================================================================


@router.get(
    "/optimization/campaigns",
    response_model=ApiResponse[list[Any]],
    summary="List optimization campaigns",
)
async def list_campaigns(
    svc: OptimizationServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))],
) -> ApiResponse[list[Any]]:
    return ApiResponse(data=await svc.list_campaigns())


@router.post(
    "/optimization/campaigns",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[dict[str, Any]],
)
async def create_campaign(
    body: Annotated[CreateBatchNameRequest, Body()],
    svc: OptimizationServiceDep,
    user: Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))],
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(
        data=await svc.create_campaign(
            name=body.name,
            goal="",
            target_metric="",
            created_by=user.user_id,
        )
    )


@router.get(
    "/optimization/campaigns/{campaign_id}",
    response_model=ApiResponse[dict[str, Any]],
    responses={404: {"description": "Campaign not found"}},
)
async def get_campaign(
    campaign_id: Annotated[str, Path(min_length=1)],
    svc: OptimizationServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))],
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await svc.get_campaign(campaign_id))


@router.get(
    "/optimization/candidates",
    response_model=ApiResponse[list[Any]],
)
async def list_candidates(
    svc: OptimizationServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))],
    campaign_id: str = Query(..., min_length=1),
) -> ApiResponse[list[Any]]:
    return ApiResponse(data=await svc.list_candidates(campaign_id))


@router.post(
    "/optimization/candidates",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[dict[str, Any]],
)
async def create_candidate(
    body: Annotated[dict[str, Any], Body()],
    svc: OptimizationServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))],
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(
        data=await svc.create_candidate(
            campaign_id=body["campaign_id"],
            name=body["name"],
            prompt_version=body["prompt_version"],
            hyperparameters=body.get("hyperparameters", {}),
        )
    )


@router.post(
    "/optimization/candidates/{candidate_id}/promote",
    response_model=ApiResponse[dict[str, Any]],
)
async def promote_candidate(
    candidate_id: Annotated[str, Path(min_length=1)],
    svc: OptimizationServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))],
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await svc.promote_candidate(candidate_id))


@router.get(
    "/optimization/experiments",
    response_model=ApiResponse[list[Any]],
)
async def list_experiments(
    svc: OptimizationServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))],
    campaign_id: str = Query(..., min_length=1),
) -> ApiResponse[list[Any]]:
    return ApiResponse(data=await svc.list_experiments(campaign_id))


@router.post(
    "/optimization/experiments",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[dict[str, Any]],
)
async def create_experiment(
    body: Annotated[dict[str, Any], Body()],
    svc: OptimizationServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))],
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(
        data=await svc.create_experiment(
            campaign_id=body["campaign_id"],
            candidate_id=body["candidate_id"],
            benchmark_set_name=body["benchmark_set_name"],
        )
    )


@router.post(
    "/optimization/experiments/{experiment_id}/run",
    response_model=ApiResponse[dict[str, Any]],
)
async def run_experiment(
    experiment_id: Annotated[str, Path(min_length=1)],
    svc: OptimizationServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))],
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await svc.run_experiment(experiment_id))


@router.get(
    "/optimization/experiments/{experiment_id}/results",
    response_model=ApiResponse[dict[str, Any]],
)
async def get_experiment_results(
    experiment_id: Annotated[str, Path(min_length=1)],
    svc: OptimizationServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))],
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await svc.get_experiment_results(experiment_id))
