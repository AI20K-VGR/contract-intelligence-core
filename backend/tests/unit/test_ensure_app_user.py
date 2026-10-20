"""ensure_app_user tạo hồ sơ local từ JWT khi Keycloak chưa sync."""

from __future__ import annotations

import pytest

from contract_intelligence.identity.domain.entities.app_user import AppUser, UserRole
from contract_intelligence.identity.interfaces.api.provision import ensure_app_user
from contract_intelligence.shared.auth.schemas import AuthenticatedUser


class _Repo:
    def __init__(self, existing: AppUser | None = None) -> None:
        self.existing = existing
        self.upserted: dict[str, str] | None = None

    async def get_by_keycloak_sub(self, keycloak_sub: str) -> AppUser | None:
        if self.existing is not None and self.existing.keycloak_sub == keycloak_sub:
            return self.existing
        return None

    async def upsert_from_keycloak(
        self,
        *,
        keycloak_sub: str,
        tenant_id: str,
        email: str,
        display_name: str,
        role: str,
    ) -> AppUser:
        self.upserted = {
            "keycloak_sub": keycloak_sub,
            "tenant_id": tenant_id,
            "email": email,
            "display_name": display_name,
            "role": role,
        }
        return AppUser(
            id=f"usr_{keycloak_sub}",
            tenant_id=tenant_id,
            email=email,
            display_name=display_name,
            role=UserRole(role),
            keycloak_sub=keycloak_sub,
        )


def _admin() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="dev-admin-keycloak-id",
        tenant_id="tenant_vgr_01",
        email="admin@ci.local",
        display_name="Admin User",
        role="ADMINISTRATOR",
    )


@pytest.mark.asyncio
async def test_ensure_app_user_inserts_name_and_email_from_the_token() -> None:
    repo = _Repo()
    await ensure_app_user(repo, _admin())
    assert repo.upserted == {
        "keycloak_sub": "dev-admin-keycloak-id",
        "tenant_id": "tenant_vgr_01",
        "email": "admin@ci.local",
        "display_name": "Admin User",
        "role": "ADMINISTRATOR",
    }


@pytest.mark.asyncio
async def test_ensure_app_user_does_not_overwrite_an_existing_profile() -> None:
    existing = AppUser(
        id="usr_dev-admin-keycloak-id",
        tenant_id="tenant_vgr_01",
        email="admin@ci.local",
        display_name="Admin User",
        role=UserRole.ADMINISTRATOR,
        keycloak_sub="dev-admin-keycloak-id",
    )
    repo = _Repo(existing)
    await ensure_app_user(repo, _admin())
    assert repo.upserted is None
