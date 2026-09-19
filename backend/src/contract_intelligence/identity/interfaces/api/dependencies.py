"""Identity FastAPI dependencies — composition root cho auth flow.

Layer: interfaces (FastAPI DI) — được phép import từ infrastructure
để compose dependencies theo Clean Architecture pattern.

Nguyên tắc:
    - Domain/application KHÔNG biết infrastructure impl
    - Chỉ composition root (ở interfaces/) mới wire:
        AsyncSession → UserRepositoryImpl → AuthService

Mỗi request sẽ resolve:
    AsyncSession → fresh session per request (auto commit/rollback)
    UserRepositoryImpl(session) → tạo mới per request
    AuthService(repo, verifier) → tạo mới per request
    AuthService methods → dùng session đã commit

Note về thread safety:
    AuthService và UserRepositoryImpl KHÔNG lưu state ngoài session —
    mỗi request tạo instance mới, an toàn với concurrent requests.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.identity.application.services.auth_service import (
    AuthService,
)
from contract_intelligence.identity.domain.repositories.user_repository import (
    UserRepository,
)
from contract_intelligence.identity.infrastructure.persistence.user_repository_impl import (
    UserRepositoryImpl,
)
from contract_intelligence.identity.infrastructure.security.password_hasher import (
    Argon2PasswordVerifier,
)
from contract_intelligence.shared.persistence import get_async_session

# -----------------------------------------------------------------------------
# Repository factories
# -----------------------------------------------------------------------------


async def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> UserRepository:
    """FastAPI dependency: tạo UserRepositoryImpl bound to current session.

    Usage:
        async def endpoint(
            repo: UserRepository = Depends(get_user_repository),
        ):
            user = await repo.get_by_email(...)
    """
    return UserRepositoryImpl(session)


# Type alias cho clean dependency signatures
UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]


# -----------------------------------------------------------------------------
# Auth service factory
# -----------------------------------------------------------------------------

# Singleton verifier — stateless, thread-safe
_password_verifier = Argon2PasswordVerifier()


async def get_auth_service(
    repo: UserRepositoryDep,
) -> AuthService:
    """FastAPI dependency: tạo AuthService với real UserRepository + Argon2 verifier.

    Usage trong router:
        @router.post("/login")
        async def login(
            svc: AuthService = Depends(get_auth_service),
            body: LoginRequest,
        ):
            result = await svc.login(...)

    Returns:
        AuthService instance mới cho mỗi request — fresh state.
    """
    return AuthService(user_repository=repo, password_verifier=_password_verifier.verify)


# Type alias
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


__all__ = [
    "AuthServiceDep",
    "UserRepositoryDep",
    "get_auth_service",
    "get_user_repository",
]
