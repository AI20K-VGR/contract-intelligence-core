"""Auth cross-cutting concerns — schemas, JWT service, FastAPI dependencies.

Module này được phép import fastapi/jwt vì là shared kernel,
KHÔNG thuộc domain layer của bounded context nào.

Sau refactor Keycloak SSO:
    - JWT service chỉ verify (KHÔNG encode) — backend không issue token.
    - Chỉ hỗ trợ Keycloak RS256 mode (local HS256 đã bị bỏ).
    - Frontend gọi thẳng Keycloak cho login/refresh/logout.

Cấu trúc:
    schemas.py      — Pydantic/dataclass: AuthenticatedUser, KeycloakTokenClaims, MeResponse
    jwt_service.py  — JWT verify (Keycloak RS256 via JWKS)
    dependencies.py — FastAPI Depends() factories (get_current_user, require_role)
    exceptions.py   — Auth-specific exceptions (AuthenticationError, TenantMismatch)

Quy tắc:
    - KHÔNG import SQLAlchemy, MinIO, httpx (đó là infrastructure concerns)
"""

from contract_intelligence.shared.auth.dependencies import (
    get_current_user,
    require_role,
)
from contract_intelligence.shared.auth.exceptions import (
    AuthenticationError,
    TenantMismatchError,
)
from contract_intelligence.shared.auth.schemas import (
    AuthenticatedUser,
    KeycloakTokenClaims,
    MeResponse,
    UserProfilePayload,
)

__all__ = [
    # Schemas
    "AuthenticatedUser",
    "KeycloakTokenClaims",
    "MeResponse",
    "UserProfilePayload",
    # Dependencies
    "get_current_user",
    "require_role",
    # Exceptions
    "AuthenticationError",
    "TenantMismatchError",
]
