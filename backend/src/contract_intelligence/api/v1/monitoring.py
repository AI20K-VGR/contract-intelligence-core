"""Admin monitoring — opens the Grafana dashboard for /admin/monitoring.

RBAC: ADMINISTRATOR only. The response sets the HttpOnly ``/grafana`` cookie
the dashboard iframe needs (see ``monitoring/session.py``); the cookie value is
never readable by page scripts.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict

from contract_intelligence.config.settings import get_settings
from contract_intelligence.monitoring.session import (
    COOKIE_NAME,
    COOKIE_PATH,
    issue_session_token,
)
from contract_intelligence.shared.auth import AuthenticatedUser, require_role
from contract_intelligence.shared.responses import ApiResponse

router = APIRouter(prefix="/admin/monitoring", tags=["Admin"])

AdminUser = Annotated[AuthenticatedUser, Depends(require_role("ADMINISTRATOR"))]


def session_cookie(token: str, *, max_age: int, samesite: str, secure: bool) -> str:
    """Set-Cookie value for the /grafana session.

    Built by hand because Starlette only emits ``Partitioned`` on Python 3.14+.
    SameSite=None requires Secure; Partitioned (CHIPS) keeps the cookie usable
    only under the app's own top-level site, never when another site frames it.
    """
    cross_site = samesite == "none"
    parts = [
        f"{COOKIE_NAME}={token}",
        f"Max-Age={max_age}",
        f"Path={COOKIE_PATH}",
        "HttpOnly",
        f"SameSite={samesite}",
    ]
    if secure or cross_site:
        parts.append("Secure")
    if cross_site:
        parts.append("Partitioned")
    return "; ".join(parts)


class MonitoringSessionDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dashboard_path: str
    expires_in: int


@router.post(
    "/session",
    response_model=ApiResponse[MonitoringSessionDTO],
    summary="Open the monitoring dashboard (sets the /grafana cookie)",
)
async def open_monitoring_session(
    admin: AdminUser, response: Response
) -> ApiResponse[MonitoringSessionDTO]:
    settings = get_settings()
    if not settings.monitoring_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Monitoring is not configured")

    ttl = settings.monitoring_session_ttl_seconds
    token = issue_session_token(
        admin, secret=settings.monitoring_session_secret or "", ttl_seconds=ttl
    )
    response.headers.append(
        "set-cookie",
        session_cookie(
            token,
            max_age=ttl,
            samesite=settings.monitoring_cookie_samesite,
            secure=settings.monitoring_cookie_secure,
        ),
    )
    response.headers["Cache-Control"] = "no-store"
    return ApiResponse(
        data=MonitoringSessionDTO(
            dashboard_path=f"/grafana/d/{settings.grafana_dashboard_uid}?orgId=1&kiosk",
            expires_in=ttl,
        )
    )
