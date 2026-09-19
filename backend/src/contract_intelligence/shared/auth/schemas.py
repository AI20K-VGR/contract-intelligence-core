"""Auth schemas — pure Pydantic, no ORM/framework dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TokenType(StrEnum):
    """Loại JWT token."""

    ACCESS = "access"
    REFRESH = "refresh"


# -----------------------------------------------------------------------------
# AuthenticatedUser — injected vào request.state via get_current_user()
# -----------------------------------------------------------------------------

@dataclass
class AuthenticatedUser:
    """Auth context gắn vào mỗi request đã được xác thực.

    Đây là dataclass thuần (không phải Pydantic/FastAPI) để giữ
    shared/auth/ gần với pure Python và dễ test không cần mock FastAPI.

    Usage trong router:
        @router.get("/items")
        async def list_items(user: AuthenticatedUser = Depends(get_current_user)):
            assert user.tenant_id == "tenant_vgr_01"

    Usage trong service:
        def business_logic(user: AuthenticatedUser) -> None:
            if user.role not in {UserRole.OPERATOR, UserRole.ADMINISTRATOR}:
                raise PermissionError("Insufficient role")
    """

    user_id: str       # "usr_..."
    tenant_id: str     # "tenant_vgr_01"
    email: str         # "john@company.com"
    display_name: str  # "Nguyễn Văn A"
    role: str          # "OPERATOR" | "REVIEWER" | "ADMINISTRATOR"
    token_type: TokenType = TokenType.ACCESS

    def has_role(self, *roles: str) -> bool:
        """Kiểm tra user có một trong các vai trò được phép."""
        return self.role in roles


# -----------------------------------------------------------------------------
# Local JWT claims (Sprint 1: HS256, self-issued)
# -----------------------------------------------------------------------------

LocalTokenClaimsPayload = dict[str, object] | None


class LocalTokenClaims(BaseModel):
    """Claims trong JWT access/refresh token — Sprint 1 local mode.

    Token được sign bằng HS256 secret key local.
    Claims tuân theo RFC 7519 + custom fields cho RBAC + tenant.

    Token access:
        {
          "sub": "usr_01HZXYZ...",
          "email": "john@company.com",
          "display_name": "Nguyễn Văn A",
          "role": "REVIEWER",
          "tenant_id": "tenant_vgr_01",
          "token_type": "access",
          "iat": 1726000000,
          "exp": 1726003600
        }

    Token refresh:
        {
          "sub": "usr_01HZXYZ...",
          "token_type": "refresh",
          "token_version": 3,
          "tenant_id": "tenant_vgr_01",
          "iat": 1726000000,
          "exp": 1726604800
        }
    """

    model_config = ConfigDict(extra="allow")

    sub: str = Field(..., description="User ID (usr_...)")
    tenant_id: str = Field(..., description="Tenant isolation scope")
    token_type: TokenType = Field(..., description='"access" hoặc "refresh"')
    email: str | None = Field(None, description="Email — chỉ có trong access token")
    display_name: str | None = Field(
        None, description="Tên hiển thị — chỉ có trong access token"
    )
    role: str | None = Field(
        None, description="RBAC role — chỉ có trong access token"
    )
    token_version: int = Field(
        default=0,
        description="Số version của refresh token — dùng revoke session",
    )
    iat: int = Field(..., description="Issued at (Unix timestamp)")
    exp: int = Field(..., description="Expiration (Unix timestamp)")


# -----------------------------------------------------------------------------
# Keycloak JWT claims (Production: RS256, JWKS)
# -----------------------------------------------------------------------------

class KeycloakTokenClaims(BaseModel):
    """Claims từ Keycloak JWT — production mode (RS256).

    Keycloak dùng cấu trúc khác local JWT:
      - role nằm trong realm_access.roles[] hoặc resource_access.{client}.roles[]
      - preferred_username thay vì email
      - tenant_id là custom claim (phải map từ Keycloak group hoặc realm attribute)

    Để đơn giản, ta flatten thành interface giống LocalTokenClaims
    sau khi map trong jwt_service.py.
    """

    model_config = ConfigDict(extra="allow")

    sub: str
    tenant_id: str
    token_type: TokenType = TokenType.ACCESS
    email: str | None = None
    display_name: str | None = None
    role: str | None = None
    token_version: int = 0
    # Keycloak-specific (sau khi map sẽ flatten)
    preferred_username: str | None = None
    realm_access_roles: list[str] = Field(default_factory=list)
    iat: int = 0
    exp: int = 0


# -----------------------------------------------------------------------------
# Auth DTOs (request/response — dùng trong interfaces/router)
# -----------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """Request body cho POST /auth/login."""

    email: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    """Response body cho POST /auth/login — success."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(..., description="Access token expiry in seconds")
    user: UserProfilePayload


class RefreshRequest(BaseModel):
    """Request body cho POST /auth/refresh."""

    refresh_token: str


class RefreshResponse(BaseModel):
    """Response body cho POST /auth/refresh — success."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class UserProfilePayload(BaseModel):
    """User profile payload — dùng trong LoginResponse và GET /auth/me."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    role: str
    tenant_id: str


class MeResponse(BaseModel):
    """Response body cho GET /auth/me."""

    id: str
    display_name: str
    role: str
    tenant_id: str
    email: str


class LogoutResponse(BaseModel):
    """Response body cho POST /auth/logout."""

    message: str = "Logged out successfully"
