"""/grafana/* — reverse proxy to the internal Grafana, ADMINISTRATOR only.

Every request is authorized here before it reaches Grafana:

    1. Credential: ``Authorization: Bearer <Keycloak token>`` or the
       ``ci_monitoring_session`` cookie (see ``session.py``). None → 401.
    2. Role: ADMINISTRATOR only. Anything else → 403.
    3. Headers: whatever ``X-WEBAUTH-*``, ``Authorization``, ``Cookie`` and
       ``X-Forwarded-*`` the client sent are dropped; the backend then sets
       ``X-WEBAUTH-USER`` (a pseudonym, not the e-mail) and
       ``X-WEBAUTH-ROLE: Viewer``.

Grafana accepts the auth-proxy header only from this container's fixed IP on
the internal ``ci-monitoring`` network (``GF_AUTH_PROXY_WHITELIST``) and has
no published port, so the browser cannot talk to it any other way. Being an
application ADMINISTRATOR only grants viewing: Grafana's role is always Viewer.
"""

from __future__ import annotations

import hashlib
from typing import Annotated
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from starlette.background import BackgroundTask
from starlette.responses import Response, StreamingResponse

from contract_intelligence.config.logging import get_logger
from contract_intelligence.config.settings import Settings, get_settings
from contract_intelligence.monitoring.session import COOKIE_NAME, verify_session_token
from contract_intelligence.shared.auth.dependencies import get_current_user
from contract_intelligence.shared.auth.exceptions import AuthenticationError

logger = get_logger(__name__)

router = APIRouter(include_in_schema=False)

GRAFANA_ROLE = "Viewer"
_ADMIN_ROLE = "ADMINISTRATOR"
_USER_HEADER = "X-WEBAUTH-USER"
_ROLE_HEADER = "X-WEBAUTH-ROLE"
_AUTH_HEADER_PREFIX = "x-webauth-"
# A Viewer reads dashboards with GET and runs panel queries with POST. Nothing
# a Viewer needs uses PUT/PATCH/DELETE, so those never reach Grafana.
_ALLOWED_METHODS = ("GET", "HEAD", "POST")
_SAFE_METHODS = frozenset({"GET", "HEAD"})
# Server admin API: refused here even though Grafana would refuse a Viewer too.
_BLOCKED_PREFIXES = ("/grafana/api/admin",)
_MAX_BODY_BYTES = 1_048_576
_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }
)
_DROPPED_REQUEST_HEADERS = _HOP_BY_HOP | {
    "host",
    "content-length",
    "authorization",
    "cookie",
    "forwarded",
    "x-forwarded-for",
    "x-forwarded-host",
    "x-forwarded-port",
    "x-forwarded-proto",
    "x-real-ip",
}

_client: httpx.AsyncClient | None = None


def _get_client(settings: Settings) -> httpx.AsyncClient:
    global _client  # noqa: PLW0603
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=settings.grafana_proxy_timeout_seconds,
            follow_redirects=False,
        )
    return _client


async def close_grafana_client() -> None:
    global _client  # noqa: PLW0603
    if _client is not None:
        await _client.aclose()
        _client = None


def grafana_login(tenant_id: str, user_id: str) -> str:
    """Stable pseudonym for Grafana's user table — no e-mail or name leaves the backend."""
    digest = hashlib.sha256(f"{tenant_id}:{user_id}".encode()).hexdigest()
    return f"ci-admin-{digest[:16]}"


async def authorize_grafana(request: Request) -> str:
    """Return the Grafana login for an ADMINISTRATOR; 401 / 403 otherwise."""
    settings = get_settings()
    if not settings.monitoring_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Monitoring is not enabled")

    authorization = request.headers.get("authorization")
    cookie = request.cookies.get(COOKIE_NAME)
    if authorization:
        user = await get_current_user(request, authorization)
        tenant_id, user_id, role = user.tenant_id, user.user_id, user.role
    elif cookie:
        try:
            session = verify_session_token(cookie, secret=settings.monitoring_session_secret or "")
        except AuthenticationError as exc:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                str(exc),
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        tenant_id, user_id, role = session.tenant_id, session.user_id, session.role
    else:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Missing credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if role != _ADMIN_ROLE:
        logger.info("grafana.forbidden", role=role)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Monitoring requires ADMINISTRATOR")
    return grafana_login(tenant_id, user_id)


GrafanaLogin = Annotated[str, Depends(authorize_grafana)]


def upstream_headers(request: Request, login: str) -> list[tuple[str, str]]:
    """Client headers minus anything that could carry identity, plus ours."""
    headers = [
        (name, value)
        for name, value in request.headers.items()
        if name.lower() not in _DROPPED_REQUEST_HEADERS
        and not name.lower().startswith(_AUTH_HEADER_PREFIX)
    ]
    headers.append((_USER_HEADER, login))
    headers.append((_ROLE_HEADER, GRAFANA_ROLE))
    return headers


def _frame_ancestors(settings: Settings) -> str:
    origins = [
        origin
        for origin in settings.cors_allow_origins
        if origin != "*" and not any(ch in origin for ch in " ;,'\"")
    ]
    return " ".join(["'self'", *origins])


def _response_headers(upstream: httpx.Response, settings: Settings) -> list[tuple[str, str]]:
    headers = [
        (name, value)
        for name, value in upstream.headers.multi_items()
        if name.lower() not in _HOP_BY_HOP and name.lower() != "content-security-policy"
    ]
    # Only the application's own pages may frame Grafana.
    headers.append(("Content-Security-Policy", f"frame-ancestors {_frame_ancestors(settings)}"))
    return headers


def _check_origin(request: Request) -> None:
    """Refuse a cross-site write even if a browser attached the cookie."""
    if request.method in _SAFE_METHODS:
        return
    origin = request.headers.get("origin")
    if origin and urlsplit(origin).netloc != request.headers.get("host"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-origin request refused")


@router.api_route("/grafana", methods=list(_ALLOWED_METHODS))
@router.api_route("/grafana/{path:path}", methods=list(_ALLOWED_METHODS))
async def grafana_proxy(request: Request, login: GrafanaLogin) -> Response:
    settings = get_settings()
    raw_path = request.scope.get("raw_path") or request.url.path.encode()
    path = raw_path.decode("latin-1")
    if any(path == prefix or path.startswith(prefix + "/") for prefix in _BLOCKED_PREFIXES):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not available through monitoring")
    _check_origin(request)

    body = await request.body()
    if len(body) > _MAX_BODY_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Request too large")

    query = request.url.query
    url = f"{(settings.grafana_upstream_url or '').rstrip('/')}{path}"
    if query:
        url = f"{url}?{query}"

    client = _get_client(settings)
    upstream_request = client.build_request(
        request.method,
        url,
        headers=upstream_headers(request, login),
        content=body or None,
    )
    try:
        upstream = await client.send(upstream_request, stream=True)
    except httpx.HTTPError as exc:
        logger.warning("grafana.upstream_unreachable", error=type(exc).__name__)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Grafana is unreachable") from exc

    response = StreamingResponse(
        upstream.aiter_raw(),
        status_code=upstream.status_code,
        background=BackgroundTask(upstream.aclose),
    )
    # Raw list, not a dict: Grafana may send several Set-Cookie headers.
    response.raw_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in _response_headers(upstream, settings)
    ]
    return response
