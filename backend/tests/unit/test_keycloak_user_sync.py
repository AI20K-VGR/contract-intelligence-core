"""Unit tests cho KeycloakUserSyncService (Approach A — Admin API fetch).

Refactored để match raw Keycloak Event JSON payload từ Phase Two
keycloak-events extension. Service giờ:
    1. Nhận raw event với userId (không có firstName/lastName/email)
    2. Gọi KeycloakAdminClient.get_user_profile(userId) để fetch UserRepresentation
    3. Upsert local DB

Test mock KeycloakAdminClient qua AsyncMock, không cần real Keycloak.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from contract_intelligence.identity.domain.entities.app_user import AppUser, UserRole
from contract_intelligence.identity.infrastructure.keycloak_admin_client import (
    KeycloakAdminUserNotFoundError,
)
from contract_intelligence.identity.interfaces.api.keycloak_user_sync_service import (
    KeycloakUserEvent,
    KeycloakUserSyncService,
    WebhookResponse,
    _build_display_name,
    _extract_tenant_id,
    _map_realm_roles_to_rbac,
)

# -----------------------------------------------------------------------
# Helpers — tạo raw Keycloak Event payload (Phase Two shape)
# -----------------------------------------------------------------------


def make_raw_event(
    event_type: str,
    *,
    user_id: str = "kc-uuid-abc123",
    realm_id: str = "contract-intelligence",
    client_id: str = "contract-intel-frontend",
) -> KeycloakUserEvent:
    """Build raw Keycloak Event như Phase Two gửi (không có nested user)."""
    return KeycloakUserEvent.model_validate(
        {
            "type": event_type,
            "realmId": realm_id,
            "clientId": client_id,
            "userId": user_id,
            "sessionId": "session-xyz",
            "ipAddress": "172.17.0.1",
            "time": 1737370000000,
            "details": {"username": "ignored-at-this-layer"},
        }
    )


def make_user_profile(
    *,
    user_id: str = "kc-uuid-abc123",
    email: str = "john@company.com",
    username: str = "john@company.com",
    first_name: str = "John",
    last_name: str = "Doe",
    enabled: bool = True,
    tenant_id: list[str] | None = None,
) -> dict[str, Any]:
    """Build Keycloak UserRepresentation (Admin API response shape)."""
    attrs: dict[str, list[str]] = {}
    if tenant_id is not None:
        attrs["tenant_id"] = tenant_id
    return {
        "id": user_id,
        "username": username,
        "email": email,
        "firstName": first_name,
        "lastName": last_name,
        "enabled": enabled,
        "attributes": attrs,
    }


def make_service(
    user_repo: Any,
    *,
    user_profile: dict[str, Any] | None = None,
    realm_role_names: list[str] | None = None,
    profile_side_effect: BaseException | None = None,
) -> KeycloakUserSyncService:
    """Build service với mocked admin client + repo."""
    admin = AsyncMock()

    # Default: trả profile khi get_user_profile được gọi
    if profile_side_effect is not None:
        admin.get_user_profile.side_effect = profile_side_effect
    elif user_profile is not None:
        admin.get_user_profile.return_value = user_profile
    else:
        admin.get_user_profile.return_value = make_user_profile()

    admin.get_user_realm_roles.return_value = realm_role_names or []

    return KeycloakUserSyncService(
        user_repository=user_repo,
        admin_client=admin,
    )


# -----------------------------------------------------------------------
# Tests — pure helpers
# -----------------------------------------------------------------------


class TestBuildDisplayName:
    def test_first_last(self) -> None:
        from contract_intelligence.identity.interfaces.api.keycloak_user_sync_service import (
            KeycloakUserProfile,
        )

        profile = KeycloakUserProfile.model_validate(
            make_user_profile(first_name="John", last_name="Doe", email="x@x")
        )
        assert _build_display_name(profile) == "John Doe"

    def test_fallback_username(self) -> None:
        from contract_intelligence.identity.interfaces.api.keycloak_user_sync_service import (
            KeycloakUserProfile,
        )

        profile = KeycloakUserProfile.model_validate(
            make_user_profile(
                email="x@x.com",
                username="x@x.com",
                first_name="",
                last_name="",
            )
        )
        assert _build_display_name(profile) == "x@x.com"

    def test_fallback_id(self) -> None:
        from contract_intelligence.identity.interfaces.api.keycloak_user_sync_service import (
            KeycloakUserProfile,
        )

        profile = KeycloakUserProfile.model_validate(
            make_user_profile(first_name="", last_name="", email="", username="")
        )
        assert _build_display_name(profile) == "kc-uuid-abc123"


class TestExtractTenantId:
    def test_from_attribute(self) -> None:
        from contract_intelligence.identity.interfaces.api.keycloak_user_sync_service import (
            KeycloakUserProfile,
        )

        profile = KeycloakUserProfile.model_validate(make_user_profile(tenant_id=["tenant_vgr_01"]))
        assert _extract_tenant_id(profile, "contract-intelligence") == "tenant_vgr_01"

    def test_fallback_to_realm(self) -> None:
        from contract_intelligence.identity.interfaces.api.keycloak_user_sync_service import (
            KeycloakUserProfile,
        )

        profile = KeycloakUserProfile.model_validate(make_user_profile(tenant_id=None))
        assert _extract_tenant_id(profile, "contract-intelligence") == "kc_contract-intelligence"

    def test_fallback_default(self) -> None:
        from contract_intelligence.identity.interfaces.api.keycloak_user_sync_service import (
            KeycloakUserProfile,
        )

        profile = KeycloakUserProfile.model_validate(make_user_profile(tenant_id=None))
        assert _extract_tenant_id(profile, "") == "kc_default"


class TestMapRealmRolesToRbac:
    def test_administrator_priority(self) -> None:
        assert _map_realm_roles_to_rbac(["ci_administrator"]) == "ADMINISTRATOR"
        assert _map_realm_roles_to_rbac(["ci_administrator", "ci_operator"]) == "ADMINISTRATOR"

    def test_reviewer_next(self) -> None:
        assert _map_realm_roles_to_rbac(["ci_reviewer"]) == "REVIEWER"
        assert _map_realm_roles_to_rbac(["ci_reviewer", "ci_operator"]) == "REVIEWER"

    def test_operator_fallback(self) -> None:
        assert _map_realm_roles_to_rbac(["ci_operator"]) == "OPERATOR"
        assert _map_realm_roles_to_rbac([]) == "OPERATOR"
        assert _map_realm_roles_to_rbac(["some_unknown_role"]) == "OPERATOR"

    def test_supports_uppercase_realm_role_names(self) -> None:
        """Nếu Keycloak realm role đặt trực tiếp là ADMINISTRATOR (không qua ci_ prefix)."""
        assert _map_realm_roles_to_rbac(["ADMINISTRATOR"]) == "ADMINISTRATOR"
        assert _map_realm_roles_to_rbac(["REVIEWER"]) == "REVIEWER"


# -----------------------------------------------------------------------
# Tests — KeycloakUserSyncService.handle_event
# -----------------------------------------------------------------------


class TestHandleEvent:
    @pytest.mark.asyncio
    async def test_login_calls_admin_then_upserts(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.upsert_from_keycloak.return_value = AppUser(
            id="usr_abc123",
            tenant_id="tenant_vgr_01",
            email="john@company.com",
            display_name="John Doe",
            role=UserRole.OPERATOR,
            is_active=True,
            keycloak_sub="kc-uuid-abc123",
        )

        svc = make_service(
            mock_repo,
            user_profile=make_user_profile(tenant_id=["tenant_vgr_01"]),
            realm_role_names=["ci_operator"],
        )
        event = make_raw_event("LOGIN")
        result = await svc.handle_event(event)

        assert result.synced is True
        assert result.action == "LOGIN"
        assert result.user_id == "usr_abc123"

        # Verify AdminClient was called with the user_id
        svc._admin.get_user_profile.assert_called_once_with("kc-uuid-abc123")  # noqa: SLF001
        svc._admin.get_user_realm_roles.assert_called_once_with("kc-uuid-abc123")  # noqa: SLF001

        # Verify upsert called with mapped fields
        mock_repo.upsert_from_keycloak.assert_called_once_with(
            keycloak_sub="kc-uuid-abc123",
            tenant_id="tenant_vgr_01",
            email="john@company.com",
            display_name="John Doe",
            role="OPERATOR",
        )

    @pytest.mark.asyncio
    async def test_register_upserts(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.upsert_from_keycloak.return_value = AppUser(
            id="usr_new",
            tenant_id="tenant_vgr_01",
            email="new@company.com",
            display_name="New User",
            role=UserRole.OPERATOR,
            is_active=True,
            keycloak_sub="kc-uuid-new",
        )

        svc = make_service(
            mock_repo,
            user_profile=make_user_profile(
                user_id="kc-uuid-new",
                email="new@company.com",
                username="new@company.com",
                first_name="New",
                last_name="User",
                tenant_id=["tenant_vgr_01"],
            ),
            realm_role_names=["ci_operator"],
        )
        event = make_raw_event("REGISTER", user_id="kc-uuid-new")
        result = await svc.handle_event(event)

        assert result.synced is True
        assert result.action == "REGISTER"

    @pytest.mark.asyncio
    async def test_update_profile_upserts(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.upsert_from_keycloak.return_value = AppUser(
            id="usr_update",
            tenant_id="tenant_vgr_01",
            email="updated@company.com",
            display_name="Updated Name",
            role=UserRole.REVIEWER,
            is_active=True,
            keycloak_sub="kc-uuid-update",
        )

        svc = make_service(
            mock_repo,
            user_profile=make_user_profile(
                user_id="kc-uuid-update",
                email="updated@company.com",
                first_name="Updated",
                last_name="Name",
                tenant_id=["tenant_vgr_01"],
            ),
            realm_role_names=["ci_reviewer"],
        )
        event = make_raw_event("UPDATE_PROFILE", user_id="kc-uuid-update")
        result = await svc.handle_event(event)

        assert result.synced is True
        assert result.action == "UPDATE_PROFILE"
        mock_repo.upsert_from_keycloak.assert_called_once_with(
            keycloak_sub="kc-uuid-update",
            tenant_id="tenant_vgr_01",
            email="updated@company.com",
            display_name="Updated Name",
            role="REVIEWER",
        )

    @pytest.mark.asyncio
    async def test_delete_account_deactivates_existing_user(self) -> None:
        mock_repo = AsyncMock()
        existing = AppUser(
            id="usr_delete",
            tenant_id="tenant_vgr_01",
            email="deleted@company.com",
            display_name="Deleted User",
            role=UserRole.OPERATOR,
            is_active=True,
            keycloak_sub="kc-uuid-delete",
        )
        mock_repo.get_by_keycloak_sub.return_value = existing

        svc = make_service(mock_repo)  # admin not called for DELETE
        event = make_raw_event("DELETE_ACCOUNT", user_id="kc-uuid-delete")
        result = await svc.handle_event(event)

        assert result.synced is True
        assert result.action == "DEACTIVATE"
        assert result.user_id == "usr_delete"
        assert existing.is_active is False
        mock_repo.save.assert_called_once_with(existing)

        # AdminClient NOT called for DELETE_ACCOUNT (no profile fetch needed)
        svc._admin.get_user_profile.assert_not_called()  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_delete_account_unknown_user_acknowledges(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.get_by_keycloak_sub.return_value = None

        svc = make_service(mock_repo)
        event = make_raw_event("DELETE_ACCOUNT", user_id="kc-uuid-unknown")
        result = await svc.handle_event(event)

        assert result.synced is True
        assert result.action == "DEACTIVATE"
        assert "usr_" in result.user_id
        mock_repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_event_type_acknowledges_without_action(self) -> None:
        mock_repo = AsyncMock()
        svc = make_service(mock_repo)
        event = make_raw_event("LOGOUT", user_id="kc-uuid-abc123")
        result = await svc.handle_event(event)

        assert result.synced is False
        assert "IGNORED" in result.action
        assert "LOGOUT" in result.action
        mock_repo.upsert_from_keycloak.assert_not_called()
        svc._admin.get_user_profile.assert_not_called()  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_event_without_user_id_acknowledges(self) -> None:
        """Một số event (VD LOGIN anonymous) không có userId."""
        mock_repo = AsyncMock()
        svc = make_service(mock_repo)
        event = make_raw_event("LOGIN", user_id="")
        result = await svc.handle_event(event)

        assert result.synced is False
        assert "IGNORED_NO_USER_ID" in result.action
        mock_repo.upsert_from_keycloak.assert_not_called()

    @pytest.mark.asyncio
    async def test_admin_returns_user_not_found(self) -> None:
        """Race: user vừa bị xoá giữa lúc event enqueue → acknowledge gracefully."""
        mock_repo = AsyncMock()
        svc = make_service(
            mock_repo,
            profile_side_effect=KeycloakAdminUserNotFoundError("not found"),
        )
        event = make_raw_event("REGISTER", user_id="kc-uuid-deleted")
        result = await svc.handle_event(event)

        assert result.synced is False
        assert result.action == "USER_NOT_FOUND_AT_KEYCLOAK"
        mock_repo.upsert_from_keycloak.assert_not_called()

    @pytest.mark.asyncio
    async def test_tenant_fallback_to_realm(self) -> None:
        """User không có tenant_id attribute → fallback về kc_{realm}."""
        mock_repo = AsyncMock()
        mock_repo.upsert_from_keycloak.return_value = AppUser(
            id="usr_tenant_fb",
            tenant_id="kc_contract-intelligence",
            email="x@x.com",
            display_name="X",
            role=UserRole.OPERATOR,
            is_active=True,
            keycloak_sub="kc-uuid-fb",
        )

        svc = make_service(
            mock_repo,
            user_profile=make_user_profile(user_id="kc-uuid-fb", tenant_id=None),
            realm_role_names=[],
        )
        event = make_raw_event("LOGIN", user_id="kc-uuid-fb")
        result = await svc.handle_event(event)

        assert result.synced is True
        mock_repo.upsert_from_keycloak.assert_called_once()
        _, kwargs = mock_repo.upsert_from_keycloak.call_args
        assert kwargs["tenant_id"] == "kc_contract-intelligence"

    @pytest.mark.asyncio
    async def test_email_fallback_to_user_id(self) -> None:
        """User không có email → dùng user_id làm fallback (đảm bảo UNIQUE constraint)."""
        mock_repo = AsyncMock()
        mock_repo.upsert_from_keycloak.return_value = AppUser(
            id="usr_x",
            tenant_id="kc_contract-intelligence",
            email="kc-uuid-noemail@keycloak.local",
            display_name="kc-uuid-noemail",
            role=UserRole.OPERATOR,
            is_active=True,
            keycloak_sub="kc-uuid-noemail",
        )

        svc = make_service(
            mock_repo,
            user_profile=make_user_profile(
                user_id="kc-uuid-noemail",
                email="",
                username="",
                first_name="",
                last_name="",
                tenant_id=None,
            ),
            realm_role_names=[],
        )
        event = make_raw_event("LOGIN", user_id="kc-uuid-noemail")
        await svc.handle_event(event)

        _, kwargs = mock_repo.upsert_from_keycloak.call_args
        assert kwargs["email"] == "kc-uuid-noemail@keycloak.local"


# -----------------------------------------------------------------------
# Tests — KeycloakUserEvent schema (raw Keycloak Event shape)
# -----------------------------------------------------------------------


class TestKeycloakUserEventSchema:
    def test_accepts_raw_phase_two_event(self) -> None:
        """Schema phải parse được đúng shape Phase Two gửi."""
        event = KeycloakUserEvent.model_validate(
            {
                "type": "LOGIN",
                "realmId": "abc-123",
                "clientId": "contract-intel-frontend",
                "userId": "f8a7-uuid",
                "sessionId": "sess-1",
                "ipAddress": "10.0.0.1",
                "time": 1737370000000,
                "details": {"username": "x", "auth_method": "openid-connect"},
            }
        )
        assert event.type == "LOGIN"
        assert event.userId == "f8a7-uuid"
        assert event.realmId == "abc-123"
        assert event.clientId == "contract-intel-frontend"
        assert event.details["username"] == "x"

    def test_ignores_unknown_fields(self) -> None:
        """Schema forward-compatible với Keycloak fields mới."""
        event = KeycloakUserEvent.model_validate(
            {
                "type": "LOGIN",
                "userId": "u1",
                "futureField": "ignored",
                "anotherUnknown": 42,
            }
        )
        assert event.userId == "u1"

    def test_required_user_id_falsy_for_non_user_events(self) -> None:
        """LOGIN_EVENT không có userId (anonymous) vẫn parse được."""
        event = KeycloakUserEvent.model_validate(
            {
                "type": "LOGIN",
                "realmId": "abc",
            }
        )
        assert event.userId == ""


# -----------------------------------------------------------------------
# Tests — WebhookResponse schema
# -----------------------------------------------------------------------


class TestWebhookResponse:
    def test_model_validate(self) -> None:
        resp = WebhookResponse(synced=True, user_id="usr_123", action="LOGIN")
        assert resp.synced is True
        assert resp.user_id == "usr_123"
        assert resp.action == "LOGIN"
