"""Shared kernel — shared types & cross-cutting concerns.

Mọi bounded context đều được phép import từ ``shared/`` mà KHÔNG vi phạm
Dependency Rule. Đây là **shared kernel** theo nghĩa DDD.

Quy tắc:
- **KHÔNG** import framework (FastAPI, SQLAlchemy) trực tiếp từ ``shared/``.
  Riêng ``shared/auth/`` được phép import fastapi/jwt vì là cross-cutting.
- Nếu cần ORM/Pydantic, đặt trong sub-module riêng (``shared/persistence/`` chẳng hạn)
  và bounded context tự quyết định có dùng hay không.
"""

# Auth cross-cutting (KHÔNG vi phạm shared kernel rule vì được phép)
from contract_intelligence.shared.auth import (
    AuthenticatedUser,
    AuthenticationError,
    KeycloakTokenClaims,
    LocalTokenClaims,
    TenantMismatchError,
    TokenType,
    get_current_user,
    require_role,
)
from contract_intelligence.shared.base import BaseEntity, BaseRepository

__all__ = [
    # Base
    "BaseEntity",
    "BaseRepository",
    # Auth
    "AuthenticatedUser",
    "AuthenticationError",
    "KeycloakTokenClaims",
    "LocalTokenClaims",
    "TenantMismatchError",
    "TokenType",
    "get_current_user",
    "require_role",
]
