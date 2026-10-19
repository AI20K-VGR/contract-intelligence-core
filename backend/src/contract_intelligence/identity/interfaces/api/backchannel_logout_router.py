"""POST /auth/backchannel-logout — Keycloak reports a session that ended.

Layer: interfaces (FastAPI router).

OIDC Back-Channel Logout 1.0: when a session ends (the user logs out, an
administrator logs them out or disables them), Keycloak POSTs a signed
``logout_token`` here from inside ci-network. The backend records its ``sid``,
and from then on every access token of that session gets 401 instead of
working until it expires (up to 15 minutes).

Not for browsers: Caddy answers 404 on this path from the Internet. The token
is signed by the realm key, so a caller cannot forge one; replaying a real one
only ends a session that already ended.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Form, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.shared.auth.exceptions import AuthenticationError
from contract_intelligence.shared.auth.jwt_service import get_jwt_service
from contract_intelligence.shared.persistence import get_async_session
from contract_intelligence.shared.session_revocation import revoke_session

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Authentication"])

_NO_STORE = {"Cache-Control": "no-store"}


@router.post(
    "/backchannel-logout",
    status_code=200,
    summary="Keycloak back-channel logout (internal, called by Keycloak)",
    include_in_schema=False,
)
async def backchannel_logout(
    logout_token: Annotated[str, Form(min_length=1, max_length=16384)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Response:
    try:
        # In a thread: an unknown kid refetches the JWKS over HTTP.
        claims = await asyncio.to_thread(get_jwt_service().decode_logout_token, logout_token)
    except AuthenticationError as exc:
        logger.warning("auth.backchannel_logout.rejected", reason=str(exc))
        # §2.8: 400 for a token that does not validate.
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_request", "error_description": "invalid logout token"},
            headers=_NO_STORE,
        )

    expires_at = await revoke_session(session, sid=claims.sid, sub=claims.sub)
    logger.info(
        "auth.backchannel_logout.revoked",
        sub=claims.sub,
        sid_prefix=claims.sid[:8],
        refused_until=expires_at.isoformat(),
    )
    return Response(status_code=200, headers=_NO_STORE)


__all__ = ["router"]
