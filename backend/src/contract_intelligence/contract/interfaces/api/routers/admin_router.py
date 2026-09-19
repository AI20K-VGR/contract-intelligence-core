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

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field

from contract_intelligence.contract.interfaces.api.dependencies_admin import (
    BatchServiceDep,
    OptimizationServiceDep,
)
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
from contract_intelligence.shared.responses import ApiResponse

router = APIRouter(tags=["Admin/Ops"])


# ============================================================================
# Batches — Màn hình 2
# ============================================================================


class CreateBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=255)


@router.post(
    "/batches",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[dict[str, Any]],
    summary="Tạo batch mới (upload ZIP nhiều dossier — Sprint 4)",
    responses={403: {"description": "Insufficient role"}},
)
async def create_batch(
    body: Annotated[CreateBatchRequest, Body()],
    svc: BatchServiceDep,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    """RBAC: OPERATOR, ADMINISTRATOR. Sprint 3 stub — accept name only."""
    if user.role not in ("OPERATOR", "ADMINISTRATOR"):
        raise HTTPException(status_code=403, detail="Insufficient role")
    # Stub: return existing or new batch_id — full impl Sprint 4
    return ApiResponse(
        data={
            "id": f"bat_stub_{user.tenant_id}",
            "name": body.name,
            "status": "running",
            "note": "Sprint 3 stub — full ZIP upload in Sprint 4",
        }
    )


@router.get(
    "/batches",
    response_model=ApiResponse[dict[str, Any]],
    summary="List batches",
)
async def list_batches(
    svc: BatchServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[dict[str, Any]]:
    items, total = await svc.list_batches(limit=limit, offset=offset)
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
    "/batches/{batch_id}",
    response_model=ApiResponse[dict[str, Any]],
    responses={404: {"description": "Batch not found"}},
)
async def get_batch(
    batch_id: Annotated[str, Path(min_length=1)],
    svc: BatchServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    return ApiResponse(data=await svc.get_batch(batch_id))


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
    response_model=ApiResponse[dict[str, Any]],
    responses={403: {"description": "Insufficient role"}},
)
async def cancel_batch(
    batch_id: Annotated[str, Path(min_length=1)],
    svc: BatchServiceDep,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    """RBAC: OPERATOR, ADMINISTRATOR."""
    if user.role not in ("OPERATOR", "ADMINISTRATOR"):
        raise HTTPException(status_code=403, detail="Insufficient role")
    return ApiResponse(data=await svc.cancel_batch(batch_id))


@router.post(
    "/batches/{batch_id}/resume",
    response_model=ApiResponse[dict[str, Any]],
    responses={403: {"description": "Insufficient role"}},
)
async def resume_batch(
    batch_id: Annotated[str, Path(min_length=1)],
    svc: BatchServiceDep,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    if user.role not in ("OPERATOR", "ADMINISTRATOR"):
        raise HTTPException(status_code=403, detail="Insufficient role")
    return ApiResponse(data=await svc.resume_batch(batch_id))


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
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    """RBAC: ADMINISTRATOR only."""
    if _user.role != "ADMINISTRATOR":
        raise HTTPException(status_code=403, detail="ADMINISTRATOR only")
    # Stub metrics — Sprint 4 sẽ aggregate từ usage_ledger
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
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[list[Any]]:
    if _user.role != "ADMINISTRATOR":
        raise HTTPException(status_code=403, detail="ADMINISTRATOR only")
    return ApiResponse(data=await svc.list_campaigns())


@router.post(
    "/optimization/campaigns",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[dict[str, Any]],
)
async def create_campaign(
    body: Annotated[CreateBatchRequest, Body()],
    svc: OptimizationServiceDep,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    if user.role != "ADMINISTRATOR":
        raise HTTPException(status_code=403, detail="ADMINISTRATOR only")
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
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    if _user.role != "ADMINISTRATOR":
        raise HTTPException(status_code=403, detail="ADMINISTRATOR only")
    return ApiResponse(data=await svc.get_campaign(campaign_id))


@router.get(
    "/optimization/candidates",
    response_model=ApiResponse[list[Any]],
)
async def list_candidates(
    svc: OptimizationServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    campaign_id: str = Query(..., min_length=1),
) -> ApiResponse[list[Any]]:
    if _user.role != "ADMINISTRATOR":
        raise HTTPException(status_code=403, detail="ADMINISTRATOR only")
    return ApiResponse(data=await svc.list_candidates(campaign_id))


@router.post(
    "/optimization/candidates",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[dict[str, Any]],
)
async def create_candidate(
    body: Annotated[dict[str, Any], Body()],
    svc: OptimizationServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    if _user.role != "ADMINISTRATOR":
        raise HTTPException(status_code=403, detail="ADMINISTRATOR only")
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
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    if _user.role != "ADMINISTRATOR":
        raise HTTPException(status_code=403, detail="ADMINISTRATOR only")
    return ApiResponse(data=await svc.promote_candidate(candidate_id))


@router.get(
    "/optimization/experiments",
    response_model=ApiResponse[list[Any]],
)
async def list_experiments(
    svc: OptimizationServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    campaign_id: str = Query(..., min_length=1),
) -> ApiResponse[list[Any]]:
    if _user.role != "ADMINISTRATOR":
        raise HTTPException(status_code=403, detail="ADMINISTRATOR only")
    return ApiResponse(data=await svc.list_experiments(campaign_id))


@router.post(
    "/optimization/experiments",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[dict[str, Any]],
)
async def create_experiment(
    body: Annotated[dict[str, Any], Body()],
    svc: OptimizationServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    if _user.role != "ADMINISTRATOR":
        raise HTTPException(status_code=403, detail="ADMINISTRATOR only")
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
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    if _user.role != "ADMINISTRATOR":
        raise HTTPException(status_code=403, detail="ADMINISTRATOR only")
    return ApiResponse(data=await svc.run_experiment(experiment_id))


@router.get(
    "/optimization/experiments/{experiment_id}/results",
    response_model=ApiResponse[dict[str, Any]],
)
async def get_experiment_results(
    experiment_id: Annotated[str, Path(min_length=1)],
    svc: OptimizationServiceDep,
    _user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[dict[str, Any]]:
    if _user.role != "ADMINISTRATOR":
        raise HTTPException(status_code=403, detail="ADMINISTRATOR only")
    return ApiResponse(data=await svc.get_experiment_results(experiment_id))
