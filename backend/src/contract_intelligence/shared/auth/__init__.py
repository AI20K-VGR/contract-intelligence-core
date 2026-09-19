"""Auth cross-cutting concerns — schemas, JWT service, FastAPI dependencies.

Module này được phép import fastapi/jwt vì là shared kernel,
KHÔNG thuộc domain layer của bounded context nào.

Cấu trúc:
    schemas.py      — Pydantic models cho auth context (AuthenticatedUser, TokenClaims)
    jwt_service.py — JWT encode/decode (HS256 local + RS256 Keycloak)
    dependencies.py — FastAPI Depends() factories (get_current_user, require_role)
    exceptions.py  — Auth-specific exceptions (AuthenticationError, TenantMismatch)

Quy tắc:
    - KHÔNG import SQLAlchemy, MinIO, httpx (đó là infrastructure concerns)
    - JWT service tự detect mode dựa trên settings.auth_mode
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
    LocalTokenClaims,
    TokenType,
)

__all__ = [
    # Schemas
    "AuthenticatedUser",
    "LocalTokenClaims",
    "KeycloakTokenClaims",
    "TokenType",
    # Dependencies
    "get_current_user",
    "require_role",
    # Exceptions
    "AuthenticationError",
    "TenantMismatchError",
]
