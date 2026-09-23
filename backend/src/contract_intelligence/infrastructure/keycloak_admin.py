"""Keycloak Admin integration for B2B SaaS User Management.

Uses ``python-keycloak`` against the configured service account
(``KEYCLOAK_ADMIN_CLIENT_ID``, manage-users + query-users).
Sync SDK calls run in ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from keycloak import KeycloakAdmin
from keycloak.exceptions import KeycloakConnectionError, KeycloakError

from contract_intelligence.config.settings import get_settings
from contract_intelligence.schemas.users import UserDTO, UserRole, UserStatus

logger = structlog.get_logger(__name__)

_APP_ROLES: frozenset[str] = frozenset({"OPERATOR", "REVIEWER", "ADMINISTRATOR"})
_ROLE_PRIORITY: tuple[str, ...] = ("ADMINISTRATOR", "REVIEWER", "OPERATOR")

# Keycloak sometimes returns 409 with these message fragments.
_EMAIL_EXISTS_RE = re.compile(
    r"exists|already|User exists with same email|duplicate",
    re.IGNORECASE,
)
_EMAIL_CONFIG_RE = re.compile(
    r"smtp|email|mail.?server|Failed to send|not configured",
    re.IGNORECASE,
)


# -----------------------------------------------------------------------------
# Typed errors — translated to HTTP in the API layer
# -----------------------------------------------------------------------------


class UserAdminError(Exception):
    """Base error for user-admin Keycloak operations."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 502,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class EmailExistsError(UserAdminError):
    def __init__(self, email: str) -> None:
        super().__init__(
            "email_exists",
            f"A user with email {email!r} already exists",
            status_code=409,
            details={"email": email},
        )


class UserNotFoundError(UserAdminError):
    def __init__(self, user_id: str) -> None:
        super().__init__(
            "user_not_found",
            f"User {user_id!r} was not found in Keycloak",
            status_code=404,
            details={"user_id": user_id},
        )


class KeycloakUnavailableError(UserAdminError):
    def __init__(self, message: str = "Keycloak is unavailable") -> None:
        super().__init__(
            "keycloak_unavailable",
            message,
            status_code=503,
        )


class EmailNotConfiguredError(UserAdminError):
    def __init__(self, message: str = "Keycloak SMTP / invite email is not configured") -> None:
        super().__init__(
            "email_not_configured",
            message,
            status_code=502,
        )


class InvalidUserStateError(UserAdminError):
    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(code, message, status_code=409, details=details)


# -----------------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------------


def _build_keycloak_admin() -> KeycloakAdmin:
    settings = get_settings()
    return KeycloakAdmin(
        server_url=settings.keycloak_admin_base_url(),
        client_id=settings.keycloak_admin_client_id,
        client_secret_key=settings.keycloak_admin_client_secret,
        realm_name=settings.keycloak_realm,
    )


def _ms_to_dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        ms = int(value)
    elif isinstance(value, str):
        try:
            ms = int(value)
        except ValueError:
            return None
    else:
        return None
    if ms <= 0:
        return None
    return datetime.fromtimestamp(ms / 1000.0, tz=UTC)


def _attr_first(attributes: dict[str, Any] | None, key: str) -> str | None:
    if not attributes:
        return None
    raw = attributes.get(key)
    if isinstance(raw, list) and raw:
        return str(raw[0])
    if isinstance(raw, str):
        return raw
    return None


def _extract_app_role(realm_roles: list[dict[str, Any]]) -> UserRole | None:
    names = {str(r.get("name", "")) for r in realm_roles if isinstance(r, dict)}
    for role in _ROLE_PRIORITY:
        if role in names:
            return role  # type: ignore[return-value]
    return None


def _derive_status(user: dict[str, Any]) -> UserStatus:
    if not user.get("enabled", True):
        return "disabled"
    required = user.get("requiredActions") or []
    if isinstance(required, list) and "UPDATE_PASSWORD" in required:
        return "invited"
    return "active"


def _to_user_dto(user: dict[str, Any], role: UserRole | None) -> UserDTO:
    status = _derive_status(user)
    created_at = _ms_to_dt(user.get("createdTimestamp"))
    display_name = (
        (user.get("firstName") or "").strip()
        or (user.get("lastName") or "").strip()
        or (user.get("username") or "").strip()
        or (user.get("email") or "").strip()
    )
    invited_at = created_at if status == "invited" else None
    last_login_raw = _attr_first(user.get("attributes"), "last_login_at")
    last_login_at: datetime | None = None
    if last_login_raw:
        try:
            last_login_at = datetime.fromisoformat(last_login_raw.replace("Z", "+00:00"))
        except ValueError:
            last_login_at = None

    return UserDTO(
        id=str(user["id"]),
        email=str(user.get("email") or ""),
        display_name=display_name,
        role=role or "OPERATOR",
        status=status,
        created_at=created_at,
        invited_at=invited_at,
        last_login_at=last_login_at,
    )


def _translate_keycloak_error(exc: Exception, *, email: str | None = None) -> UserAdminError:
    if isinstance(exc, UserAdminError):
        return exc
    if isinstance(exc, KeycloakConnectionError):
        msg = str(exc.error_message or exc) or "Keycloak connection failed"
        return KeycloakUnavailableError(msg)

    if isinstance(exc, KeycloakError):
        code = exc.response_code
        msg = str(exc.error_message or exc)
        body = ""
        if exc.response_body:
            try:
                body = exc.response_body.decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                body = str(exc.response_body)
        combined = f"{msg} {body}"

        if code == 409 or _EMAIL_EXISTS_RE.search(combined):
            return EmailExistsError(email or "unknown")
        if code in (404,):
            return UserNotFoundError("unknown")
        if code in (502, 503) or _EMAIL_CONFIG_RE.search(combined):
            # SMTP misconfig often surfaces as 500/502 with mail wording.
            if _EMAIL_CONFIG_RE.search(combined):
                return EmailNotConfiguredError(msg)
            return KeycloakUnavailableError(msg)
        if code is not None and code >= 500:
            return KeycloakUnavailableError(msg)
        return UserAdminError(
            "keycloak_error",
            msg,
            status_code=502,
            details={"response_code": code},
        )

    return UserAdminError("keycloak_error", str(exc), status_code=502)


def _get_user_or_raise(admin: KeycloakAdmin, user_id: str) -> dict[str, Any]:
    try:
        user = admin.get_user(user_id)
    except KeycloakError as exc:
        if exc.response_code == 404:
            raise UserNotFoundError(user_id) from exc
        raise _translate_keycloak_error(exc) from exc
    if not isinstance(user, dict) or not user.get("id"):
        raise UserNotFoundError(user_id)
    return user


def _get_app_role_for_user(admin: KeycloakAdmin, user_id: str) -> UserRole | None:
    roles = admin.get_realm_roles_of_user(user_id)
    if not isinstance(roles, list):
        return None
    return _extract_app_role(roles)


def _assign_app_role(admin: KeycloakAdmin, user_id: str, role_name: str) -> None:
    role = admin.get_realm_role(role_name)
    admin.assign_realm_roles(user_id, [role])


def _replace_app_role(admin: KeycloakAdmin, user_id: str, new_role: str) -> None:
    current = admin.get_realm_roles_of_user(user_id)
    if not isinstance(current, list):
        current = []
    to_remove = [r for r in current if isinstance(r, dict) and r.get("name") in _APP_ROLES]
    if to_remove:
        admin.delete_realm_roles_of_user(user_id, to_remove)
    _assign_app_role(admin, user_id, new_role)


def _rollback_created_user(admin: KeycloakAdmin, user_id: str) -> None:
    """Xóa user vừa tạo nếu gửi email mời thất bại, để lần sau không báo trùng."""
    try:
        admin.delete_user(user_id)
    except KeycloakError as exc:
        logger.warning(
            "keycloak.create_user.rollback_failed",
            user_id=user_id,
            error=str(exc),
        )


def _send_update_password_email(admin: KeycloakAdmin, user_id: str) -> None:
    settings = get_settings()
    try:
        admin.send_update_account(
            user_id,
            payload=["UPDATE_PASSWORD"],
            client_id=settings.keycloak_invite_client_id,
            lifespan=settings.keycloak_invite_lifespan_seconds,
            redirect_uri=settings.keycloak_invite_redirect_uri,
        )
    except KeycloakError as exc:
        raise _translate_keycloak_error(exc) from exc


def _count_administrators(admin: KeycloakAdmin) -> int:
    try:
        members = admin.get_realm_role_members("ADMINISTRATOR")
    except KeycloakError:
        return 0
    if not isinstance(members, list):
        return 0
    # Count only enabled admins for last-admin protection.
    return sum(1 for m in members if isinstance(m, dict) and m.get("enabled", True))


@dataclass(frozen=True, slots=True)
class UserListResult:
    items: list[UserDTO]
    total: int


# -----------------------------------------------------------------------------
# Sync implementations (run via asyncio.to_thread)
# -----------------------------------------------------------------------------


def _list_users_sync(
    *,
    q: str | None,
    role: UserRole | None,
    status: UserStatus | None,
    limit: int,
    offset: int,
    tenant_id: str | None,
) -> UserListResult:
    admin = _build_keycloak_admin()
    try:
        query: dict[str, Any] = {"max": 1000, "first": 0}
        if q:
            query["search"] = q

        raw_users: list[dict[str, Any]]
        if role is not None and not q:
            members = admin.get_realm_role_members(role, query={"max": 1000, "first": 0})
            raw_users = [u for u in members if isinstance(u, dict)]
        else:
            users = admin.get_users(query)
            raw_users = [u for u in users if isinstance(u, dict)]

        dtos: list[UserDTO] = []
        for user in raw_users:
            uid = str(user.get("id") or "")
            if not uid:
                continue
            if tenant_id:
                attrs = user.get("attributes") or {}
                tid = _attr_first(attrs if isinstance(attrs, dict) else None, "tenant_id")
                if tid is not None and tid != tenant_id:
                    continue
            try:
                user_role = _get_app_role_for_user(admin, uid)
            except KeycloakError:
                user_role = None
            if role is not None and user_role != role:
                continue
            dto = _to_user_dto(user, user_role)
            if status is not None and dto.status != status:
                continue
            if q:
                needle = q.lower()
                hay = f"{dto.email} {dto.display_name}".lower()
                if needle not in hay and needle not in dto.id.lower():
                    continue
            dtos.append(dto)

        # Stable sort by email for deterministic pagination.
        dtos.sort(key=lambda u: (u.email.lower(), u.id))
        total = len(dtos)
        page = dtos[offset : offset + limit]
        return UserListResult(items=page, total=total)
    except KeycloakError as exc:
        raise _translate_keycloak_error(exc) from exc
    except KeycloakConnectionError as exc:
        raise KeycloakUnavailableError(str(exc)) from exc


def _create_user_sync(
    *,
    email: str,
    display_name: str,
    role: UserRole,
    tenant_id: str,
) -> UserDTO:
    admin = _build_keycloak_admin()
    user_id: str | None = None
    try:
        created_id = admin.create_user(
            {
                "username": email,
                "email": email,
                "firstName": display_name,
                "enabled": True,
                "emailVerified": True,
                "requiredActions": ["UPDATE_PASSWORD"],
                "attributes": {"tenant_id": [tenant_id]},
            }
        )
        user_id = str(created_id or "")
        if not user_id:
            raise UserAdminError(
                "keycloak_error",
                "Keycloak did not return a user id",
                status_code=502,
            )
        _assign_app_role(admin, user_id, role)
        _send_update_password_email(admin, user_id)
        user = _get_user_or_raise(admin, user_id)
        logger.info("keycloak.create_user.ok", user_id=user_id, email=email, role=role)
        return _to_user_dto(user, role)
    except UserAdminError:
        if user_id:
            _rollback_created_user(admin, user_id)
        raise
    except KeycloakError as exc:
        if user_id:
            _rollback_created_user(admin, user_id)
        raise _translate_keycloak_error(exc, email=email) from exc
    except KeycloakConnectionError as exc:
        if user_id:
            _rollback_created_user(admin, user_id)
        raise KeycloakUnavailableError(str(exc)) from exc


def _update_role_sync(*, user_id: str, new_role: UserRole) -> UserDTO:
    admin = _build_keycloak_admin()
    try:
        user = _get_user_or_raise(admin, user_id)
        current_role = _get_app_role_for_user(admin, user_id)
        if (
            current_role == "ADMINISTRATOR"
            and new_role != "ADMINISTRATOR"
            and _count_administrators(admin) <= 1
        ):
            raise InvalidUserStateError(
                "last_administrator",
                "Cannot demote the last ADMINISTRATOR",
                user_id=user_id,
            )
        _replace_app_role(admin, user_id, new_role)
        user = _get_user_or_raise(admin, user_id)
        logger.info("keycloak.update_role.ok", user_id=user_id, role=new_role)
        return _to_user_dto(user, new_role)
    except UserAdminError:
        raise
    except KeycloakError as exc:
        raise _translate_keycloak_error(exc) from exc
    except KeycloakConnectionError as exc:
        raise KeycloakUnavailableError(str(exc)) from exc


def _set_enabled_sync(*, user_id: str, enabled: bool) -> UserDTO:
    admin = _build_keycloak_admin()
    try:
        user = _get_user_or_raise(admin, user_id)
        role = _get_app_role_for_user(admin, user_id)
        if not enabled and role == "ADMINISTRATOR" and _count_administrators(admin) <= 1:
            raise InvalidUserStateError(
                "last_administrator",
                "Cannot disable the last ADMINISTRATOR",
                user_id=user_id,
            )
        if enabled:
            admin.enable_user(user_id)
        else:
            admin.disable_user(user_id)
        user = _get_user_or_raise(admin, user_id)
        logger.info("keycloak.set_enabled.ok", user_id=user_id, enabled=enabled)
        return _to_user_dto(user, role)
    except UserAdminError:
        raise
    except KeycloakError as exc:
        raise _translate_keycloak_error(exc) from exc
    except KeycloakConnectionError as exc:
        raise KeycloakUnavailableError(str(exc)) from exc


def _resend_invite_sync(*, user_id: str) -> UserDTO:
    admin = _build_keycloak_admin()
    try:
        user = _get_user_or_raise(admin, user_id)
        role = _get_app_role_for_user(admin, user_id)
        dto = _to_user_dto(user, role)
        if dto.status != "invited":
            raise InvalidUserStateError(
                "invalid_invite_state",
                "Invite email can only be resent when status is 'invited'",
                user_id=user_id,
                status=dto.status,
            )
        # Ensure required action is still set before sending.
        required = list(user.get("requiredActions") or [])
        if "UPDATE_PASSWORD" not in required:
            required.append("UPDATE_PASSWORD")
            admin.update_user(user_id, {"requiredActions": required})
        _send_update_password_email(admin, user_id)
        user = _get_user_or_raise(admin, user_id)
        logger.info("keycloak.resend_invite.ok", user_id=user_id)
        return _to_user_dto(user, role)
    except UserAdminError:
        raise
    except KeycloakError as exc:
        raise _translate_keycloak_error(exc) from exc
    except KeycloakConnectionError as exc:
        raise KeycloakUnavailableError(str(exc)) from exc


# -----------------------------------------------------------------------------
# Async public API
# -----------------------------------------------------------------------------


async def list_users(
    *,
    q: str | None = None,
    role: UserRole | None = None,
    status: UserStatus | None = None,
    limit: int = 20,
    offset: int = 0,
    tenant_id: str | None = None,
) -> UserListResult:
    """List/search users with optional filters and offset pagination."""
    return await asyncio.to_thread(
        _list_users_sync,
        q=q,
        role=role,
        status=status,
        limit=limit,
        offset=offset,
        tenant_id=tenant_id,
    )


async def create_user(
    *,
    email: str,
    display_name: str,
    role: UserRole,
    tenant_id: str,
) -> UserDTO:
    """Create user in Keycloak, assign role, and send UPDATE_PASSWORD email."""
    return await asyncio.to_thread(
        _create_user_sync,
        email=email,
        display_name=display_name,
        role=role,
        tenant_id=tenant_id,
    )


async def update_user_role(*, user_id: str, role: UserRole) -> UserDTO:
    """Replace the user's app realm role."""
    return await asyncio.to_thread(_update_role_sync, user_id=user_id, new_role=role)


async def disable_user(*, user_id: str) -> UserDTO:
    """Disable a Keycloak user (enabled=false)."""
    return await asyncio.to_thread(_set_enabled_sync, user_id=user_id, enabled=False)


async def enable_user(*, user_id: str) -> UserDTO:
    """Enable a Keycloak user (enabled=true)."""
    return await asyncio.to_thread(_set_enabled_sync, user_id=user_id, enabled=True)


async def resend_invite(*, user_id: str) -> UserDTO:
    """Resend UPDATE_PASSWORD email — only valid when status is invited."""
    return await asyncio.to_thread(_resend_invite_sync, user_id=user_id)


# Backward-compatible alias used by the earlier Sprint-2 invite endpoint.
async def invite_user_via_keycloak(email: str, role_name: str) -> str:
    """Legacy helper — create + invite; returns Keycloak user id."""
    dto = await create_user(
        email=email.lower().strip(),
        display_name=email.split("@")[0],
        role=role_name,  # type: ignore[arg-type]
        tenant_id="",
    )
    return dto.id


__all__ = [
    "EmailExistsError",
    "EmailNotConfiguredError",
    "InvalidUserStateError",
    "KeycloakUnavailableError",
    "UserAdminError",
    "UserListResult",
    "UserNotFoundError",
    "create_user",
    "disable_user",
    "enable_user",
    "invite_user_via_keycloak",
    "list_users",
    "resend_invite",
    "update_user_role",
]
