"""Keycloak Admin integration for B2B SaaS User Management.

Uses ``python-keycloak`` against the configured service account
(``KEYCLOAK_ADMIN_CLIENT_ID``, manage-users + query-users).
Sync SDK calls run in ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from keycloak import KeycloakAdmin
from keycloak.exceptions import KeycloakConnectionError, KeycloakError

from contract_intelligence.config.settings import get_settings
from contract_intelligence.schemas.users import UserDTO, UserRole, UserStatus
from contract_intelligence.shared.email_delivery import (
    UNDELIVERABLE_MESSAGE,
    skip_undeliverable,
)

logger = structlog.get_logger(__name__)

_APP_ROLES: frozenset[str] = frozenset({"OPERATOR", "REVIEWER", "ADMINISTRATOR"})
_ROLE_PRIORITY: tuple[str, ...] = ("ADMINISTRATOR", "REVIEWER", "OPERATOR")
# Newest realm-wide LOGIN events read in one call to fill last_login_at for a
# page of users; users of the page not among them are asked for one by one.
_LOGIN_EVENTS_MAX = 1000

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


class UndeliverableEmailError(UserAdminError):
    """The address is on a reserved domain (``.local``, ``.test``...): mail would bounce."""

    def __init__(self, email: str) -> None:
        super().__init__(
            "email_domain_undeliverable",
            UNDELIVERABLE_MESSAGE,
            status_code=422,
            details={"email": email},
        )


@dataclass(frozen=True, slots=True)
class TenantMember:
    """A Keycloak user checked to be enabled and stamped with the caller's tenant."""

    id: str
    email: str
    display_name: str
    status: UserStatus
    role: UserRole | None = None


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
        user_realm_name=settings.keycloak_realm,
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


def _to_user_dto(
    user: dict[str, Any], role: UserRole | None, *, last_login_at: datetime | None = None
) -> UserDTO:
    status = _derive_status(user)
    created_at = _ms_to_dt(user.get("createdTimestamp"))
    display_name = (
        (user.get("firstName") or "").strip()
        or (user.get("lastName") or "").strip()
        or (user.get("username") or "").strip()
        or (user.get("email") or "").strip()
    )
    invited_at = created_at if status == "invited" else None

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


def _login_events(admin: KeycloakAdmin, query: dict[str, Any]) -> list[Any] | None:
    """One read of Keycloak's LOGIN events; None (logged) when the call fails."""
    try:
        events = admin.get_events(query)
    except Exception as exc:
        logger.warning(
            "keycloak.login_events.failed",
            error_type=type(exc).__name__,
            code=getattr(exc, "response_code", None),
        )
        return None
    return events if isinstance(events, list) else []


def _keep_newest(events: list[Any], wanted: set[str], latest: dict[str, datetime]) -> None:
    for event in events:
        if not isinstance(event, dict):
            continue
        uid = str(event.get("userId") or "")
        when = _ms_to_dt(event.get("time"))
        if uid not in wanted or when is None:
            continue
        if uid not in latest or when > latest[uid]:
            latest[uid] = when


def _last_login_times(admin: KeycloakAdmin, user_ids: Iterable[str]) -> dict[str, datetime]:
    """Latest LOGIN event of each user, read from Keycloak's event log.

    Several users: one call reads the newest ``_LOGIN_EVENTS_MAX`` LOGIN events
    of the realm. When that window is full, a user of the page who is not in it
    may still have logged in earlier, so each of them gets a call of their own
    (newest first, ``max=1``). A window that is not full already holds every
    event the realm keeps, and no further call is made.

    Best effort: the realm keeps events for a limited time (30 days), so a user
    who has not logged in since is absent. A failed call (403, timeout, ...)
    is logged and stops the lookup; users not found by then have no last login,
    and the caller does not fail.
    """
    wanted = {uid for uid in user_ids if uid}
    if not wanted:
        return {}
    latest: dict[str, datetime] = {}
    missing = sorted(wanted)
    if len(wanted) > 1:
        events = _login_events(admin, {"type": "LOGIN", "max": _LOGIN_EVENTS_MAX})
        if events is None:
            return {}
        _keep_newest(events, wanted, latest)
        missing = [] if len(events) < _LOGIN_EVENTS_MAX else sorted(wanted - latest.keys())
    for uid in missing:
        events = _login_events(admin, {"type": "LOGIN", "user": uid, "max": 1})
        if events is None:
            break
        _keep_newest(events, {uid}, latest)
    return latest


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
        if code == 401:
            # The service account could not authenticate: wrong or rotated client
            # secret (deploy/keycloak_configure.py rotates it), not a missing role.
            return UserAdminError(
                "keycloak_unauthenticated",
                "Keycloak không xác thực được service account contract-intel-backend: "
                "kiểm tra KEYCLOAK_ADMIN_CLIENT_SECRET khớp secret của client trong Keycloak.",
                status_code=502,
                details={"response_code": code},
            )
        if code == 403:
            # Service account "contract-intel-backend" thiếu client role của
            # realm-management (manage-users để tạo/sửa user).
            return UserAdminError(
                "keycloak_forbidden",
                "Keycloak từ chối thao tác: service account contract-intel-backend "
                "thiếu quyền realm-management (manage-users).",
                status_code=502,
                details={"response_code": code},
            )
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


def _user_attributes(user: dict[str, Any]) -> dict[str, list[str]]:
    raw = user.get("attributes") or {}
    if not isinstance(raw, dict):
        return {}
    cleaned: dict[str, list[str]] = {}
    for key, value in raw.items():
        if isinstance(value, list):
            cleaned[str(key)] = [str(item) for item in value]
        elif value is not None:
            cleaned[str(key)] = [str(value)]
    return cleaned


# Keycloak user ids are UUIDs; anything else is not looked up (it lands in the URL path).
_USER_ID_RE = re.compile(r"[A-Za-z0-9-]{1,64}")


def _users_with_email(admin: KeycloakAdmin, email: str) -> list[dict[str, Any]]:
    """Users whose email is exactly ``email`` (case-insensitive)."""
    wanted = email.strip().casefold()
    if not wanted:
        return []
    users = admin.get_users({"email": email.strip(), "exact": True, "max": 10})
    return [
        user
        for user in users or []
        if isinstance(user, dict) and str(user.get("email") or "").strip().casefold() == wanted
    ]


def _as_tenant_member(user: dict[str, Any], tenant_id: str) -> TenantMember | None:
    """``user`` as a member of ``tenant_id``; None when disabled or in another tenant."""
    if not tenant_id or user.get("enabled") is not True or not user.get("id"):
        return None
    attrs = user.get("attributes")
    if _attr_first(attrs if isinstance(attrs, dict) else None, "tenant_id") != tenant_id:
        return None
    dto = _to_user_dto(user, None)
    return TenantMember(
        id=dto.id, email=dto.email, display_name=dto.display_name, status=dto.status
    )


def _resolve_tenant_members_sync(
    *, tenant_id: str, recipients: list[tuple[str, str]]
) -> list[TenantMember | None]:
    admin = _build_keycloak_admin()
    try:
        out: list[TenantMember | None] = []
        for user_id, email in recipients:
            user: dict[str, Any] | None = None
            if user_id:
                if _USER_ID_RE.fullmatch(user_id):
                    try:
                        user = _get_user_or_raise(admin, user_id)
                    except UserNotFoundError:
                        user = None
            else:
                matches = _users_with_email(admin, email)
                user = matches[0] if len(matches) == 1 else None
            out.append(_as_tenant_member(user, tenant_id) if user else None)
        return out
    except KeycloakError as exc:
        raise _translate_keycloak_error(exc) from exc
    except KeycloakConnectionError as exc:
        raise KeycloakUnavailableError(str(exc)) from exc


def _lookup_tenant_member_sync(*, tenant_id: str, email: str) -> TenantMember | None:
    admin = _build_keycloak_admin()
    try:
        matches = [
            member
            for member in (_as_tenant_member(u, tenant_id) for u in _users_with_email(admin, email))
            if member is not None and member.status == "active"
        ]
        if len(matches) != 1:
            return None
        member = matches[0]
        return TenantMember(
            id=member.id,
            email=member.email,
            display_name=member.display_name,
            status=member.status,
            role=_get_app_role_for_user(admin, member.id),
        )
    except KeycloakError as exc:
        raise _translate_keycloak_error(exc) from exc
    except KeycloakConnectionError as exc:
        raise KeycloakUnavailableError(str(exc)) from exc


def send_share_login_email_sync(
    *,
    user_id: str,
    dossier_name: str,
    sender_name: str,
    email: str = "",
    require_password: bool = False,
) -> bool:
    """Gửi thư đặt mật khẩu khi user còn trạng thái được mời hoặc chưa có mật khẩu.

    True khi việc gửi thư cho người này đã xong ở đây (đã gửi, hoặc bỏ qua vì địa chỉ
    thuộc tên miền không nhận thư); False khi người này cần thư mở hồ sơ thường.
    """
    admin = _build_keycloak_admin()
    user = _get_user_or_raise(admin, user_id)
    invited = _derive_status(user) == "invited" or require_password
    if not invited:
        return False
    address = (user.get("email") or email or user.get("username") or "").strip()
    if skip_undeliverable(address, purpose="share_login", user_id=user_id):
        return True
    required = list(user.get("requiredActions") or [])
    if "UPDATE_PASSWORD" not in required:
        required.append("UPDATE_PASSWORD")
    attributes = _user_attributes(user)
    attributes["share_dossier_name"] = [dossier_name]
    attributes["share_sender_name"] = [sender_name]
    profile = {
        "email": address,
        "emailVerified": True,
        "requiredActions": required,
        "attributes": attributes,
    }
    if user.get("username"):
        profile["username"] = user.get("username")
    if user.get("firstName"):
        profile["firstName"] = user.get("firstName")
    admin.update_user(user_id, profile)
    try:
        _send_update_password_email(admin, user_id)
    finally:
        attributes.pop("share_dossier_name", None)
        attributes.pop("share_sender_name", None)
        profile["attributes"] = attributes
        admin.update_user(user_id, profile)
    return True


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
    with_last_login: bool = True,
    strict_tenant: bool = False,
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
            attrs = user.get("attributes") or {}
            tid = _attr_first(attrs if isinstance(attrs, dict) else None, "tenant_id")
            if strict_tenant:
                # Only users stamped with the caller's tenant; none when it is unknown.
                if not tenant_id or tid != tenant_id:
                    continue
            elif tenant_id and tid is not None and tid != tenant_id:
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
        logins = _last_login_times(admin, [dto.id for dto in page]) if with_last_login else {}
        page = [
            dto.model_copy(update={"last_login_at": logins[dto.id]}) if dto.id in logins else dto
            for dto in page
        ]
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
    if skip_undeliverable(email, purpose="invite"):
        raise UndeliverableEmailError(email)
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
        return _to_user_dto(
            user, new_role, last_login_at=_last_login_times(admin, [user_id]).get(user_id)
        )
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
        return _to_user_dto(
            user, role, last_login_at=_last_login_times(admin, [user_id]).get(user_id)
        )
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
        if skip_undeliverable(dto.email, purpose="invite_resend", user_id=user_id):
            raise UndeliverableEmailError(dto.email)
        # Ensure required action is still set before sending.
        required = list(user.get("requiredActions") or [])
        if "UPDATE_PASSWORD" not in required:
            required.append("UPDATE_PASSWORD")
            admin.update_user(user_id, {"requiredActions": required})
        _send_update_password_email(admin, user_id)
        user = _get_user_or_raise(admin, user_id)
        logger.info("keycloak.resend_invite.ok", user_id=user_id)
        return _to_user_dto(
            user, role, last_login_at=_last_login_times(admin, [user_id]).get(user_id)
        )
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
    with_last_login: bool = True,
    strict_tenant: bool = False,
) -> UserListResult:
    """List/search users with optional filters and offset pagination.

    ``strict_tenant`` drops users without a ``tenant_id`` attribute, which the
    default filter keeps.
    """
    return await asyncio.to_thread(
        _list_users_sync,
        q=q,
        role=role,
        status=status,
        limit=limit,
        offset=offset,
        tenant_id=tenant_id,
        with_last_login=with_last_login,
        strict_tenant=strict_tenant,
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


async def resolve_tenant_members(
    *, tenant_id: str, recipients: list[tuple[str, str]]
) -> list[TenantMember | None]:
    """Check share recipients ``(user_id, email)``: by id, or by exact email without one.

    One entry per recipient, None when the user is missing, disabled or outside
    ``tenant_id``. Keycloak being down raises, so the caller saves nothing.
    """
    return await asyncio.to_thread(
        _resolve_tenant_members_sync, tenant_id=tenant_id, recipients=recipients
    )


async def lookup_tenant_member(*, tenant_id: str, email: str) -> TenantMember | None:
    """The one active member of ``tenant_id`` whose email is exactly ``email``, with role."""
    return await asyncio.to_thread(_lookup_tenant_member_sync, tenant_id=tenant_id, email=email)


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
    "TenantMember",
    "UndeliverableEmailError",
    "UserAdminError",
    "UserListResult",
    "UserNotFoundError",
    "create_user",
    "disable_user",
    "enable_user",
    "invite_user_via_keycloak",
    "list_users",
    "lookup_tenant_member",
    "resend_invite",
    "resolve_tenant_members",
    "update_user_role",
]
