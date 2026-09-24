r"""POST /auth/webhooks/keycloak — Keycloak user event sync endpoint.

Layer: interfaces (FastAPI router).

Security:
    1. HMAC-SHA256 signature verification (X-Keycloak-Signature header)
       - Phase Two ``keycloak-events`` extension ký mọi webhook body bằng
         HMAC-SHA256 với shared ``WEBHOOK_SECRET``.
       - Backend recompute HMAC với ``KEYCLOAK_WEBHOOK_SECRET`` (cùng secret)
         và so sánh constant-time.
       - Configurable: ``KEYCLOAK_WEBHOOK_VERIFY_SIGNATURE=true|false``.
    2. Network policy (production): chỉ cho phép Keycloak pod IP gọi endpoint.
    3. Idempotent: xử lý REGISTER/UPDATE_PROFILE/LOGIN đều thông qua
       ``upsert_from_keycloak`` (Keycloak có thể retry nếu nhận !2xx).

Event types được xử lý:
    - LOGIN          → upsert profile (Approach A — Admin API fetch)
    - REGISTER       → upsert profile
    - UPDATE_PROFILE → upsert profile
    - DELETE_ACCOUNT → soft-delete local user (set is_active=false)

Backend chỉ sync user vào local DB để:
    1. Join với audit logs (dossier.created_by, review.approved_by, ...)
    2. Admin có thể deactivate user backend-side mà không cần chờ Keycloak

Token issuance hoàn toàn do Keycloak quản lý — backend không can thiệp.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.config.settings import get_settings
from contract_intelligence.identity.infrastructure.keycloak_admin_client import (
    KeycloakAdminAuthError,
    KeycloakAdminRequestError,
)
from contract_intelligence.identity.interfaces.api.dependencies import (
    KeycloakSyncServiceDep,
    UserRepositoryDep,
)
from contract_intelligence.identity.interfaces.api.keycloak_user_sync_service import (
    KeycloakUserEvent,
    WebhookResponse,
)
from contract_intelligence.shared.persistence import get_async_session
from contract_intelligence.shared.responses import ApiResponse

router = APIRouter(tags=["Authentication"])

# Header name do Phase Two ext-event-http extension set (X-Keycloak-Signature
# cho hmac auth-type). Xem docs Phase Two keycloak-events README.
SIGNATURE_HEADER = "X-Keycloak-Signature"


# -----------------------------------------------------------------------------
# HMAC verification
# -----------------------------------------------------------------------------


def _verify_keycloak_signature(body_bytes: bytes, signature_header: str | None) -> bool:
    """Verify HMAC-SHA256 signature từ Phase Two webhook.

    Algorithm:
        signature = HMAC_SHA256(secret, body)
        header_value = lowercase_hex(signature)

    Args:
        body_bytes: Raw request body bytes (KHÔNG parse JSON trước khi verify
            để tránh tampering với whitespace/key-order).
        signature_header: Giá trị ``X-Keycloak-Signature`` header (hex string).

    Returns:
        True nếu signature khớp, False nếu lệch hoặc missing.
    """
    if not signature_header:
        return False

    settings = get_settings()
    secret = settings.keycloak_webhook_secret.encode("utf-8")
    expected = hmac.new(secret, body_bytes, hashlib.sha256).hexdigest()
    # compare_digest để chống timing attack
    return hmac.compare_digest(expected, signature_header.strip().lower())


# -----------------------------------------------------------------------------
# Endpoint
# -----------------------------------------------------------------------------


@router.post(
    "/webhooks/keycloak",
    status_code=200,
    response_model=ApiResponse[WebhookResponse],
    summary="Keycloak user event webhook — sync user vào local DB",
    responses={
        200: {"description": "Event processed (synced hoặc ignored)"},
        400: {"description": "Invalid event payload"},
        401: {"description": "HMAC signature invalid hoặc missing"},
        422: {"description": "Pydantic validation failed"},
        500: {"description": "Keycloak Admin API call failed (Phase Two sẽ retry)"},
    },
)
async def keycloak_webhook(
    request: Request,
    x_keycloak_signature: Annotated[str | None, Header(alias=SIGNATURE_HEADER)] = None,
    svc: KeycloakSyncServiceDep = ...,  # type: ignore[assignment]
    repo: UserRepositoryDep = ...,  # type: ignore[assignment]
    session: Annotated[AsyncSession, Depends(get_async_session)] = ...,  # type: ignore[assignment]
) -> ApiResponse[WebhookResponse]:
    """Receive user lifecycle events từ Keycloak và sync vào local app_user table.

    Luồng xử lý:
        1. Đọc raw body bytes (để HMAC verify với whitespace chính xác).
        2. Verify HMAC signature (nếu enabled trong settings).
        3. Parse JSON body → ``KeycloakUserEvent``.
        4. Gọi ``svc.handle_event()`` để fetch user profile từ
           Keycloak Admin API rồi upsert local DB.

    Args:
        request: FastAPI Request (dùng cho logging + raw body access).
        x_keycloak_signature: HMAC-SHA256 hex signature từ Keycloak.
        svc: ``KeycloakUserSyncService`` được inject qua Depends.

    Returns:
        ``WebhookResponse`` với synced=True/False và action đã thực hiện.

    Raises:
        HTTPException 401: HMAC signature invalid.
    """
    logger = structlog.get_logger(__name__)
    settings = get_settings()

    # 1. Read raw body (trước khi Pydantic parse) để HMAC verify chính xác
    body_bytes = await request.body()

    # 2. HMAC verify (optional, on by default)
    if settings.keycloak_webhook_verify_signature and not _verify_keycloak_signature(
        body_bytes, x_keycloak_signature
    ):
        logger.warning(
            "keycloak_webhook_invalid_signature",
            path=str(request.url.path),
            body_preview=body_bytes[:200].decode("utf-8", errors="replace"),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Keycloak-Signature header",
        )

    # 3. Parse JSON body
    try:
        import json

        body_dict: dict[str, Any] = json.loads(body_bytes) if body_bytes else {}
    except json.JSONDecodeError:
        logger.warning(
            "keycloak_webhook_invalid_json",
            body_preview=body_bytes[:200].decode("utf-8", errors="replace"),
        )
        return ApiResponse(
            data=WebhookResponse(
                synced=False,
                user_id="unknown",
                action="INVALID_PAYLOAD",
            ),
        )

    try:
        event = KeycloakUserEvent.model_validate(body_dict)
    except ValidationError:
        # Keycloak gửi event không parse được (admin events, ...) → log + ack
        logger.warning(
            "keycloak_webhook_unparseable_event",
            body_preview=str(body_dict)[:500],
        )
        return ApiResponse(
            data=WebhookResponse(
                synced=False,
                user_id="unknown",
                action="INVALID_PAYLOAD",
            ),
        )

    # 4. Handle event
    try:
        result = await svc.handle_event(event)
    except KeycloakAdminAuthError as exc:
        # Service account thiếu permission — KHÔNG retry (lỗi config)
        logger.error(
            "keycloak_webhook_admin_auth_error",
            user_id=event.userId,
            event_type=event.type,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Keycloak Admin API authentication failed. "
                "Verify service account has realm-management client role 'view-users'."
            ),
        ) from exc
    except KeycloakAdminRequestError as exc:
        # Network/5xx — cho Phase Two retry với exponential backoff
        logger.error(
            "keycloak_webhook_admin_request_error",
            user_id=event.userId,
            event_type=event.type,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Keycloak Admin API unavailable — caller should retry",
        ) from exc

    if result.synced and result.action == "LOGIN":
        try:
            from contract_intelligence.admin.activity_feed import record_activity

            user = await repo.get_by_id(result.user_id)
            if user is not None:
                await record_activity(
                    session,
                    tenant_id=user.tenant_id,
                    title="Đăng nhập",
                    actor_display_name=user.display_name,
                    detail=None,
                    kind="user.login",
                )
        except Exception as exc:  # noqa: BLE001 — login sync already succeeded
            logger.exception("activity.login_record_failed", error=str(exc))

    return ApiResponse(data=result)


# Re-export for convenience
__all__ = ["router"]
