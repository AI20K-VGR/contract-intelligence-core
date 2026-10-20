"""Short-lived credential that lets the admin page's iframe reach /grafana.

An iframe cannot attach ``Authorization: Bearer``. The page therefore posts its
Keycloak token to ``POST /api/v1/admin/monitoring/session``; once that request
passed ``require_role("ADMINISTRATOR")`` the backend sets this HS256 token as an
HttpOnly cookie scoped to ``/grafana``. It is not a second login: it can only
be minted from a valid Keycloak token, expires within minutes, and the page
renews it with a fresh Keycloak token (so a removed role stops working).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import jwt

from contract_intelligence.shared.auth.exceptions import AuthenticationError
from contract_intelligence.shared.auth.schemas import AuthenticatedUser

COOKIE_NAME = "ci_monitoring_session"
COOKIE_PATH = "/grafana"
_ISSUER = "ci-backend"
_AUDIENCE = "ci-monitoring"
_ALGORITHM = "HS256"


@dataclass(frozen=True)
class MonitoringSession:
    user_id: str
    tenant_id: str
    role: str
    expires_at: int


def issue_session_token(user: AuthenticatedUser, *, secret: str, ttl_seconds: int) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": _ISSUER,
        "aud": _AUDIENCE,
        "sub": user.user_id,
        "tid": user.tenant_id,
        "role": user.role,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return jwt.encode(claims, secret, algorithm=_ALGORITHM)


def verify_session_token(token: str, *, secret: str) -> MonitoringSession:
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            secret,
            algorithms=[_ALGORITHM],
            audience=_AUDIENCE,
            issuer=_ISSUER,
            options={"require": ["exp", "iat", "sub", "role"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Monitoring session has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid monitoring session") from exc
    return MonitoringSession(
        user_id=str(claims["sub"]),
        tenant_id=str(claims.get("tid") or ""),
        role=str(claims["role"]),
        expires_at=int(claims["exp"]),
    )
