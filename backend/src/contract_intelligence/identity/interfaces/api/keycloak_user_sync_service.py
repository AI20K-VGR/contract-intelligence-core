"""Keycloak user sync service — upsert/delete users from Keycloak events.

Layer: interfaces/api — webhook handler. Được gọi từ
``webhook_router.POST /api/v1/auth/webhooks/keycloak``.

Luồng (Approach A — Phase Two keycloak-events extension):
    1. Keycloak gọi POST /api/v1/auth/webhooks/keycloak khi user
       LOGIN / REGISTER / UPDATE_PROFILE / DELETE_ACCOUNT.
    2. Payload là raw Keycloak ``Event`` JSON từ ``ModelToRepresentation``
       (chỉ có userId, không có firstName/lastName/email/attributes).
    3. Service extract ``userId``, gọi ``KeycloakAdminClient.get_user_profile``
       để fetch full UserRepresentation từ Keycloak Admin REST API.
    4. ``UserRepository.upsert_from_keycloak()`` → persist xuống DB.
    5. Trả 200 OK cho Keycloak (Phase Two retry với exponential backoff nếu !2xx).

Security:
    - Webhook signature (HMAC-SHA256) được verify ở router layer
      (xem ``webhook_router.py``).
    - Admin API call dùng Client Credentials Grant (Service Account).
      Service account phải có realm-management client role ``view-users``
      (xem ``keycloak/realm-export.json``).

Token issuance hoàn toàn do Keycloak quản lý — backend không can thiệp.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

from contract_intelligence.identity.domain.entities.app_user import UserRole
from contract_intelligence.identity.domain.repositories.user_repository import (
    UserRepository,
)
from contract_intelligence.identity.infrastructure.keycloak_admin_client import (
    KeycloakAdminAuthError,
    KeycloakAdminClient,
    KeycloakAdminClientPort,
    KeycloakAdminError,
    KeycloakAdminRequestError,
    KeycloakAdminUserNotFoundError,
)


class KeycloakEventType(StrEnum):
    """Keycloak event types được hỗ trợ bởi service.

    Match với raw Keycloak EventType enum:
        https://www.keycloak.org/docs-api/latest/javadocs/org/keycloak/events/EventType.html
    """

    LOGIN = "LOGIN"
    REGISTER = "REGISTER"
    UPDATE_PROFILE = "UPDATE_PROFILE"
    DELETE_ACCOUNT = "DELETE_ACCOUNT"


# -----------------------------------------------------------------------------
# Pydantic schemas cho Keycloak webhook payload (raw Event JSON)
# -----------------------------------------------------------------------------


class KeycloakUserEvent(BaseModel):
    """Raw Keycloak ``Event`` JSON từ Phase Two keycloak-events extension.

    Keycloak Event schema (org.keycloak.events.Event):
        {
          "time": 1737370000000,
          "type": "LOGIN",
          "realmId": "abc-123",
          "clientId": "contract-intel-frontend",
          "userId": "f8a7...-...-...-...",
          "sessionId": "...",
          "ipAddress": "172.17.0.1",
          "error": null,
          "details": {
            "username": "admin@ci.local",
            "auth_method": "openid-connect",
            ...
          }
        }

    Note: Khác với phiên bản trước — Phase Two gửi raw Keycloak Event,
    không có nested ``user`` object. Full profile phải fetch qua
    ``KeycloakAdminClient.get_user_profile(userId)``.
    """

    model_config = {"populate_by_name": True, "extra": "ignore"}

    type: str  # LOGIN | REGISTER | UPDATE_PROFILE | DELETE_ACCOUNT | ...
    realmId: str = Field(default="", alias="realmId")  # noqa: N815
    clientId: str = Field(default="", alias="clientId")  # noqa: N815
    userId: str = Field(default="", alias="userId")  # noqa: N815
    sessionId: str = Field(default="", alias="sessionId")  # noqa: N815
    ipAddress: str = Field(default="", alias="ipAddress")  # noqa: N815
    time: int = 0
    error: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class KeycloakUserProfile(BaseModel):
    """User representation trả về từ Keycloak Admin REST API.

    Map 1-1 với ``org.keycloak.representations.idm.UserRepresentation``.
    Chỉ chứa các field backend cần để upsert ``app_user``.

    Xem:
        GET /admin/realms/{realm}/users/{id}
        https://www.keycloak.org/docs-api/latest/rest-api/index.html#_userrepresentation
    """

    model_config = {"populate_by_name": True, "extra": "ignore"}

    id: str
    username: str = ""
    email: str = ""
    firstName: str = Field(default="", alias="firstName")  # noqa: N815
    lastName: str = Field(default="", alias="lastName")  # noqa: N815
    enabled: bool = True
    attributes: dict[str, list[str]] = Field(default_factory=dict)


class WebhookResponse(BaseModel):
    """Response shape cho webhook endpoint."""

    synced: bool
    user_id: str
    action: str


# -----------------------------------------------------------------------------
# KeycloakUserSyncService
# -----------------------------------------------------------------------------


class KeycloakUserSyncService:
    """Sync Keycloak user events → local app_user table.

    Args:
        user_repository: Repository để upsert/delete users.
        admin_client: Keycloak Admin REST API client để fetch user profile.

    Usage:
        svc = KeycloakUserSyncService(user_repository, admin_client)
        await svc.handle_event(raw_event_dict)
    """

    def __init__(
        self,
        user_repository: UserRepository,
        admin_client: KeycloakAdminClientPort,
    ) -> None:
        self._repo = user_repository
        self._admin = admin_client
        self._log = structlog.get_logger(__name__)

    async def handle_event(self, event: KeycloakUserEvent) -> WebhookResponse:
        """Xử lý Keycloak event, sync user vào local DB.

        Args:
            event: Parsed raw Keycloak Event payload.

        Returns:
            ``WebhookResponse`` chứa synced user_id và action đã thực hiện.

        Raises:
            KeycloakAdminError: Khi Admin API call fail sau retry.
        """
        event_type = str(event.type).upper()
        user_id = event.userId

        # Một số event không có userId (VD LOGIN của anonymous flow) → skip
        if not user_id:
            self._log.info(
                "keycloak_webhook_event_without_user_id",
                type=event_type,
                realm_id=event.realmId,
            )
            return WebhookResponse(
                synced=False,
                user_id="unknown",
                action=f"IGNORED_NO_USER_ID_{event_type}",
            )

        match event_type:
            case "LOGIN" | "REGISTER" | "UPDATE_PROFILE":
                return await self._handle_upsert(event_type, user_id, event.realmId)

            case "DELETE_ACCOUNT":
                return await self._handle_delete_account(user_id)

            case _:
                # Event type khác (LOGOUT, CODE_TO_TOKEN, REFRESH_TOKEN, ...)
                # → acknowledge nhưng no-op.
                return WebhookResponse(
                    synced=False,
                    user_id=f"usr_{user_id}",
                    action=f"IGNORED_{event_type}",
                )

    # -------------------------------------------------------------------------
    # Internal — upsert flow
    # -------------------------------------------------------------------------

    async def _handle_upsert(self, event_type: str, user_id: str, realm_id: str) -> WebhookResponse:
        """Fetch full profile từ Keycloak Admin API rồi upsert local DB.

        Args:
            event_type: LOGIN | REGISTER | UPDATE_PROFILE (cho audit log).
            user_id: Keycloak user UUID.
            realm_id: Keycloak realm ID (cho log context).

        Returns:
            WebhookResponse với synced=True và action = event_type.
        """
        # 1. Fetch full profile
        try:
            profile_data = await self._admin.get_user_profile(user_id)
        except KeycloakAdminUserNotFoundError:
            # User vừa bị xoá giữa lúc event được enqueue → race
            self._log.warning(
                "keycloak_admin_user_not_found",
                user_id=user_id,
                event_type=event_type,
            )
            return WebhookResponse(
                synced=False,
                user_id=f"usr_{user_id}",
                action="USER_NOT_FOUND_AT_KEYCLOAK",
            )
        except KeycloakAdminAuthError:
            # Service account thiếu permission / token invalid → log + raise
            self._log.error(
                "keycloak_admin_auth_failed",
                user_id=user_id,
                event_type=event_type,
            )
            raise
        except KeycloakAdminRequestError:
            # Network/5xx — rethrow để caller có thể return 500 (Phase Two retry)
            self._log.error(
                "keycloak_admin_request_failed",
                user_id=user_id,
                event_type=event_type,
            )
            raise

        profile = KeycloakUserProfile.model_validate(profile_data)

        # 2. Derive fields
        display_name = _build_display_name(profile)
        tenant_id = _extract_tenant_id(profile, realm_id)
        role = _map_realm_roles_to_rbac(
            profile_data.get("_realm_role_names") or [],
        )

        # 3. Fetch realm roles separately nếu user representation chưa có sẵn
        # (UserRepresentation.getRoleMappings() cần gọi riêng)
        if not role or role == UserRole.OPERATOR.value:
            try:
                realm_role_names = await self._admin.get_user_realm_roles(user_id)
                role = _map_realm_roles_to_rbac(realm_role_names)
            except (KeycloakAdminError, KeycloakAdminRequestError):
                # Fallback về role đã derive ở bước 2 (giữ OPERATOR nếu lỗi)
                self._log.warning(
                    "keycloak_admin_role_fetch_failed_using_fallback",
                    user_id=user_id,
                )

        # 4. Upsert local DB
        email = profile.email or profile.username or f"{user_id}@keycloak.local"
        user = await self._repo.upsert_from_keycloak(
            keycloak_sub=user_id,
            tenant_id=tenant_id,
            email=email,
            display_name=display_name,
            role=role,
        )

        self._log.info(
            "keycloak_user_synced",
            user_id=user.id,
            keycloak_sub=user_id,
            event_type=event_type,
            role=role,
            tenant_id=tenant_id,
        )

        return WebhookResponse(
            synced=True,
            user_id=user.id,
            action=event_type,
        )

    # -------------------------------------------------------------------------
    # Internal — delete-account flow
    # -------------------------------------------------------------------------

    async def _handle_delete_account(self, user_id: str) -> WebhookResponse:
        """Deactivate local user khi Keycloak xoá account.

        Args:
            user_id: Keycloak user UUID (Keycloak sub).

        Returns:
            WebhookResponse với action = DEACTIVATE (kể cả khi user
            chưa tồn tại ở local DB — acknowledge cho Keycloak).
        """
        existing = await self._repo.get_by_keycloak_sub(user_id)
        if existing is None:
            # User chưa bao giờ được sync (VD REGISTER không trigger
            # webhook do misconfig) → acknowledge nhưng không fail.
            self._log.info(
                "keycloak_delete_account_no_local_user",
                user_id=f"usr_{user_id}",
            )
            return WebhookResponse(
                synced=True,
                user_id=f"usr_{user_id}",
                action="DEACTIVATE",
            )

        existing.deactivate()
        await self._repo.save(existing)

        self._log.info(
            "keycloak_user_deactivated",
            user_id=existing.id,
            keycloak_sub=user_id,
        )

        return WebhookResponse(
            synced=True,
            user_id=existing.id,
            action="DEACTIVATE",
        )


# -----------------------------------------------------------------------------
# Helpers — pure functions
# -----------------------------------------------------------------------------


def _build_display_name(profile: KeycloakUserProfile) -> str:
    """Compose display_name từ firstName + lastName, fallback username/email.

    Returns:
        Display name string (không bao giờ empty).
    """
    full = " ".join(part for part in (profile.firstName.strip(), profile.lastName.strip()) if part)
    return full or profile.username or profile.email or profile.id


def _extract_tenant_id(profile: KeycloakUserProfile, realm_id: str) -> str:
    """Lấy tenant_id từ Keycloak user attribute.

    Convention: backend đọc user attribute ``tenant_id`` (list[str]) — Keycloak
    admin set qua Admin Console → User → Attributes. Nếu không có thì
    fallback về ``kc_{realm_id}`` để đảm bảo luôn có giá trị.

    Args:
        profile: UserRepresentation đã validate.
        realm_id: Keycloak realm ID (cho fallback).

    Returns:
        Tenant ID string (không bao giờ empty).
    """
    raw = profile.attributes.get("tenant_id") or []
    if raw and isinstance(raw, list) and raw[0]:
        return str(raw[0])
    return f"kc_{realm_id}" if realm_id else "kc_default"


# Priority: ci_administrator > ci_reviewer > ci_operator (admin bao trùm)
_KC_ROLE_PRIORITY = ("ci_administrator", "ci_reviewer", "ci_operator")
_RBAC_ROLE_FROM_KC_ROLE = {
    "ci_administrator": UserRole.ADMINISTRATOR.value,
    "ci_reviewer": UserRole.REVIEWER.value,
    "ci_operator": UserRole.OPERATOR.value,
}


def _map_realm_roles_to_rbac(realm_role_names: list[str]) -> str:
    """Map Keycloak realm role names → RBAC role string.

    Thứ tự ưu tiên: ADMINISTRATOR > REVIEWER > OPERATOR.

    Args:
        realm_role_names: Realm role names từ Keycloak (VD
            ``["ci_administrator"]`` hoặc ``["OPERATOR", "ADMINISTRATOR"]``
            nếu dùng realm role names trực tiếp).

    Returns:
        RBAC role string (OPERATOR | REVIEWER | ADMINISTRATOR).
        Default OPERATOR nếu không match role nào.
    """
    # Hỗ trợ cả 2 convention:
    # 1. Keycloak realm role = "ci_administrator" / "ci_reviewer" / "ci_operator"
    #    (mapped từ "ADMINISTRATOR" qua realm client-role mapping)
    # 2. Keycloak realm role = "ADMINISTRATOR" / "REVIEWER" / "OPERATOR"
    #    (giữ nguyên — set trực tiếp trên realm)
    normalized = set(realm_role_names or [])
    for kc_role in _KC_ROLE_PRIORITY:
        if kc_role in normalized:
            return _RBAC_ROLE_FROM_KC_ROLE[kc_role]
    # Fallback: uppercase Keycloak role names match
    for upper_kc_role in ("ADMINISTRATOR", "REVIEWER", "OPERATOR"):
        if upper_kc_role in normalized:
            return upper_kc_role
    return UserRole.OPERATOR.value


__all__ = [
    "KeycloakAdminClient",  # re-export cho FastAPI Depends type hint
    "KeycloakEventType",
    "KeycloakUserEvent",
    "KeycloakUserProfile",
    "KeycloakUserSyncService",
    "WebhookResponse",
    "_map_realm_roles_to_rbac",  # exported cho tests
]
