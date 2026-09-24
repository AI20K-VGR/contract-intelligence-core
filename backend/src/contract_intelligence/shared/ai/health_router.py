"""AI service health proxy — surfaces DOC-05c §4.7 endpoints.

Endpoints:
    GET /ai/healthz  — AI service liveness
    GET /ai/readyz   — AI service readiness (model loaded)
    GET /ai/jobs/{job_id} — proxy polling status từ AI service

Cơ chế:
    - Stub mode (default): trả hardcoded "ready" — không gọi network.
    - HTTP mode: proxy sang ai-service.internal base_url + headers chuẩn §3.

Headers chuẩn (DOC-05c §3):
    X-Internal-Service-Key  — pre-shared key (settings.ai_service_api_key)
    X-Tenant-Id            — tenant scope
    X-Trace-Id             — W3C TraceContext
"""

from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path

from contract_intelligence.shared.ai import get_ai_service_client
from contract_intelligence.shared.auth import AuthenticatedUser, require_role
from contract_intelligence.shared.responses import ApiResponse
from contract_intelligence.shared.versioning import __ai_contract__

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["AI-Service"])


@router.get(
    "/healthz",
    summary="Liveness probe — kiểm tra backend process còn sống",
    response_model=ApiResponse[dict[str, Any]],
)
async def backend_healthz() -> ApiResponse[dict[str, Any]]:
    """Luôn trả 200 OK nếu process còn chạy."""
    return ApiResponse(
        data={
            "status": "ok",
            "service": "contract-intelligence-backend",
            "ai_contract_version": __ai_contract__,
        },
    )


@router.get(
    "/readyz",
    summary="Readiness probe — kiểm tra DB + AI service sẵn sàng",
    response_model=ApiResponse[dict[str, Any]],
)
async def backend_readyz() -> ApiResponse[dict[str, Any]]:
    """Trả 503 nếu AI service không available (chỉ trong HTTP mode)."""
    client = get_ai_service_client()
    ai_ok = await client.healthcheck()

    from contract_intelligence.shared.persistence import get_engine

    db_ok = True
    try:
        engine = get_engine()
        # Quick connectivity check
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    except Exception as exc:
        logger.warning("readyz.db_check_failed", error=str(exc))
        db_ok = False

    payload = {
        "db_ok": db_ok,
        "ai_service_ok": ai_ok,
        "ai_service_mode": "stub" if not ai_ok else "live",
    }

    if not db_ok or (not ai_ok and __import__("os").environ.get("AI_REQUIRE_READY", "0") == "1"):
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "checks": payload,
            },
        )

    return ApiResponse(
        data={
            "status": "ready" if ai_ok and db_ok else "degraded",
            "checks": payload,
        },
    )


@router.get(
    "/ai/jobs/{job_id}",
    summary="Proxy tới AI service — polling trạng thái job nội bộ",
    response_model=ApiResponse[dict[str, Any]],
    responses={502: {"description": "AI service unavailable"}},
)
async def ai_get_job_status(
    job_id: Annotated[str, Path(min_length=1)],
    user: Annotated[
        AuthenticatedUser, Depends(require_role("OPERATOR", "REVIEWER", "ADMINISTRATOR"))
    ],
) -> ApiResponse[dict[str, Any]]:
    """Proxy sang AI service GET /jobs/{id} (DOC-05c §4.5).

    Frontend có thể poll trực tiếp job_id (do Backend trả về qua dispatcher)
    mà không cần biết nó thuộc dossier/run nào.
    """
    client = get_ai_service_client()
    try:
        report = await client.get_job_status(job_id)
    except Exception as exc:
        logger.warning("ai_proxy.get_job_failed", job_id=job_id, error=str(exc))
        raise HTTPException(status_code=502, detail="AI service unavailable") from exc

    return ApiResponse(data=report.model_dump(mode="json"))


@router.delete(
    "/ai/jobs/{job_id}",
    summary="Cancel AI service job — proxy sang DELETE /jobs/{id}",
    response_model=ApiResponse[dict[str, Any]],
)
async def ai_cancel_job(
    job_id: Annotated[str, Path(min_length=1)],
    user: Annotated[AuthenticatedUser, Depends(require_role("OPERATOR", "ADMINISTRATOR"))],
) -> ApiResponse[dict[str, Any]]:
    """Cancel job tại AI service (DOC-05c §4.6). RBAC: ADMINISTRATOR inherits OPERATOR."""
    client = get_ai_service_client()
    try:
        report = await client.cancel_job(job_id)
    except Exception as exc:
        logger.warning("ai_proxy.cancel_failed", job_id=job_id, error=str(exc))
        raise HTTPException(status_code=502, detail="AI service unavailable") from exc

    return ApiResponse(data=report.model_dump(mode="json"))


__all__ = ["router"]
