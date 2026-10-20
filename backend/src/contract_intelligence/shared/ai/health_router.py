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

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Path

from contract_intelligence.config.settings import get_settings
from contract_intelligence.shared.ai import get_ai_service_client
from contract_intelligence.shared.auth import AuthenticatedUser, require_role
from contract_intelligence.shared.responses import ApiResponse
from contract_intelligence.shared.versioning import __ai_contract__

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["AI-Service"])

_AI2_PROBE_TIMEOUT = httpx.Timeout(3.0)


async def ai2_alive() -> bool:
    """AI2 answers its liveness probe (``GET {AI2_BASE_URL}/healthz``).

    AI2 is the only AI service the pipeline calls over HTTP (AI1 is Kafka-only).
    Its /readyz is not used: that one probes the paid LLM provider. The legacy
    DOC-05c client (``AI_SERVICE_URL``) has no service behind it in production,
    so it says nothing about readiness. In stub mode the stub answers.
    """
    settings = get_settings()
    if settings.ai_service_mode != "http":
        return await get_ai_service_client().healthcheck()
    base = settings.ai2_base_url.rstrip("/").removesuffix("/api/v1")
    try:
        async with httpx.AsyncClient(timeout=_AI2_PROBE_TIMEOUT) as client:
            response = await client.get(f"{base}/healthz")
    except httpx.HTTPError:
        return False
    return response.status_code == 200


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
    summary="Readiness probe — kiểm tra DB + AI2 sẵn sàng",
    response_model=ApiResponse[dict[str, Any]],
)
async def backend_readyz() -> ApiResponse[dict[str, Any]]:
    """503 khi DB lỗi, hoặc AI2 không trả lời và ``AI_REQUIRE_READY=1``."""
    ai_ok = await ai2_alive()

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
        # Same key as before (it now means AI2); "unavailable" replaces the
        # old "stub", which was shown for any failed probe.
        "ai_service_ok": ai_ok,
        "ai_service_mode": "live" if ai_ok else "unavailable",
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
    user: Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))],
) -> ApiResponse[dict[str, Any]]:
    """Proxy sang AI service GET /jobs/{id} (DOC-05c §4.5). Chỉ ADMINISTRATOR.

    Job không gắn với hồ sơ nào ở đây nên không kiểm được quyền theo hồ sơ:
    mở cho mọi role thì ai cũng xem được job của người khác. Frontend không
    dùng endpoint này; người vận hành theo dõi qua run và SSE của hồ sơ.
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
    user: Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))],
) -> ApiResponse[dict[str, Any]]:
    """Cancel job tại AI service (DOC-05c §4.6). Chỉ ADMINISTRATOR.

    Không kiểm được job thuộc hồ sơ nào, nên OPERATOR từng huỷ được job của
    người khác. Huỷ lần xử lý của một hồ sơ: ``POST /runs/{run_id}/cancel``.
    """
    client = get_ai_service_client()
    try:
        report = await client.cancel_job(job_id)
    except Exception as exc:
        logger.warning("ai_proxy.cancel_failed", job_id=job_id, error=str(exc))
        raise HTTPException(status_code=502, detail="AI service unavailable") from exc

    return ApiResponse(data=report.model_dump(mode="json"))


__all__ = ["router"]
