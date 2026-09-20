"""Identity FastAPI dependencies — composition root cho user repository và sync service.

Layer: interfaces (FastAPI DI) — được phép import từ infrastructure
để compose dependencies theo Clean Architecture pattern.

Sau refactor Keycloak SSO (Approach A — Admin API fetch):
    - Backend không có AuthService (Keycloak lo auth).
    - Backend không issue token, không verify password.
    - Identity BC chỉ còn UserRepository (cho Keycloak user provisioning)
      và KeycloakUserSyncService (cho webhook events).
    - Auth (JWT verify) thuộc shared/auth/ — đã được sử dụng qua
      ``shared.auth.dependencies.get_current_user``.
    - KeycloakAdminClient cung cấp REST API access để fetch full user
      profile khi webhook event không chứa firstName/lastName/email.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.identity.domain.repositories.user_repository import (
    UserRepository,
)
from contract_intelligence.identity.infrastructure.keycloak_admin_client import (
    KeycloakAdminClient,
    KeycloakAdminClientPort,
)
from contract_intelligence.identity.infrastructure.persistence.user_repository_impl import (
    UserRepositoryImpl,
)
from contract_intelligence.identity.interfaces.api.keycloak_user_sync_service import (
    KeycloakUserSyncService,
)
from contract_intelligence.shared.persistence import get_async_session

# -----------------------------------------------------------------------------
# Repository factory
# -----------------------------------------------------------------------------


async def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> UserRepository:
    """FastAPI dependency: tạo UserRepositoryImpl bound to current session.

    Usage:
        async def endpoint(
            repo: UserRepository = Depends(get_user_repository),
        ):
            user = await repo.upsert_from_keycloak(...)
    """
    return UserRepositoryImpl(session)


# Type alias cho clean dependency signatures
UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]


# ------------------------------------------------------------------------------
# Keycloak Admin REST API client
# -----------------------------------------------------------------------------


async def get_keycloak_admin_client() -> KeycloakAdminClient:
    """FastAPI dependency: trả singleton KeycloakAdminClient.

    Singleton accessor đọc settings tại first-call; subsequent calls
    trả về cùng instance. Lý do singleton: httpx.AsyncClient + token
    cache cần share giữa các request để không reconnect liên tục.

    Usage:
        @router.post("/webhooks/keycloak")
        async def webhook(
            client: Annotated[KeycloakAdminClient, Depends(get_keycloak_admin_client)],
        ):
            profile = await client.get_user_profile(user_id)
    """
    from contract_intelligence.identity.infrastructure.keycloak_admin_client import (
        get_keycloak_admin_client as _factory,
    )

    return _factory()


# Type alias
KeycloakAdminClientDep = Annotated[
    KeycloakAdminClientPort, Depends(get_keycloak_admin_client)
]


# ------------------------------------------------------------------------------
# Keycloak sync service factory
# -----------------------------------------------------------------------------


async def get_keycloak_sync_service(
    repo: UserRepositoryDep,
    admin_client: KeycloakAdminClientDep,
) -> KeycloakUserSyncService:
    """FastAPI dependency: tạo KeycloakUserSyncService.

    Compose:
        - UserRepository (DB) — để upsert/delete users
        - KeycloakAdminClient (HTTP) — để fetch full user profile

    Usage:
        @router.post("/webhooks/keycloak")
        async def webhook(svc: KeycloakSyncServiceDep):
            result = await svc.handle_event(event)
    """
    return KeycloakUserSyncService(
        user_repository=repo,
        admin_client=admin_client,
    )


# Type alias
KeycloakSyncServiceDep = Annotated[
    KeycloakUserSyncService, Depends(get_keycloak_sync_service)
]


__all__ = [
    "KeycloakAdminClientDep",
    "KeycloakSyncServiceDep",
    "UserRepositoryDep",
    "get_keycloak_admin_client",
    "get_keycloak_sync_service",
    "get_user_repository",
]
