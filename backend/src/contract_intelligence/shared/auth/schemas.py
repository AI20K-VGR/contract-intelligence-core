"""Auth schemas — pure Pydantic/dataclass, no ORM/framework dependencies.

Định nghĩa các schema cho auth flow sau khi refactor sang Keycloak SSO:

    - AuthenticatedUser: Dataclass chứa identity context gắn vào request
                         (sau khi `get_current_user` decode xong JWT).
    - KeycloakTokenClaims: Pydantic model cho JWT claims đã map từ Keycloak.
    - UserProfilePayload / MeResponse: Response shape cho GET /auth/me.

QUAN TRỌNG — Backend KHÔNG issue token:
    - KHÔNG còn LoginRequest / LoginResponse (frontend gọi thẳng Keycloak)
    - KHÔNG còn RefreshRequest / RefreshResponse (frontend gọi thẳng Keycloak)
    - KHÔNG còn LogoutResponse (frontend gọi thẳng Keycloak logout endpoint)
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

# -----------------------------------------------------------------------------
# AuthenticatedUser — injected vào request via get_current_user()
# -----------------------------------------------------------------------------


@dataclass
class AuthenticatedUser:
    """Auth context gắn vào mỗi request đã được xác thực.

    Đây là dataclass thuần (không phải Pydantic/FastAPI) để giữ
    shared/auth/ gần với pure Python và dễ test không cần mock FastAPI.

    Được build từ Keycloak JWT claims bởi `jwt_service.decode_and_validate_access()`.

    Attributes:
        user_id: Keycloak `sub` claim (vd "usr_01HZXYZ..." hoặc UUID).
        tenant_id: Tenant scope — custom claim hoặc derive từ realm.
        email: Từ Keycloak `email` claim.
        display_name: Từ `name` hoặc `preferred_username`.
        role: RBAC role mapped từ `realm_access.roles[]`
              (OPERATOR | REVIEWER | ADMINISTRATOR).
        is_active: False khi admin disable user. Backend-side protection
              bổ sung cho Keycloak session. Defaults to True if not in token.

    Usage trong router:
        @router.get("/items")
        async def list_items(user: AuthenticatedUser = Depends(get_current_user)):
            assert user.tenant_id == "tenant_vgr_01"

    Usage trong service:
        def business_logic(user: AuthenticatedUser) -> None:
            if user.role not in {UserRole.OPERATOR, UserRole.ADMINISTRATOR}:
                raise PermissionError("Insufficient role")
    """

    user_id: str
    tenant_id: str
    email: str
    display_name: str
    role: str
    is_active: bool = True

    def has_role(self, *roles: str) -> bool:
        """Kiểm tra user có một trong các vai trò được phép."""
        return self.role in roles


# -----------------------------------------------------------------------------
# Keycloak JWT claims (Production: RS256, JWKS)
# -----------------------------------------------------------------------------


class KeycloakTokenClaims(BaseModel):
    """Claims từ Keycloak JWT — đã được map sang unified format.

    Keycloak OIDC token structure (RFC 7519 + OIDC):
      - `sub`: User ID (UUID hoặc custom "usr_..." nếu đã provision)
      - `email`, `email_verified`: User identity
      - `name`, `preferred_username`: Display fields
      - `realm_access.roles[]`: Realm-level roles
      - `tenant_id`: Custom claim (do Keycloak protocol mapper thêm vào)
      - Standard: `iss`, `aud`, `iat`, `exp`, `nbf`

    Sau khi `jwt_service._decode_keycloak_token()` xử lý, các field
    `tenant_id`, `role`, `display_name`, `email` được chuẩn hóa về
    cùng shape với AuthenticatedUser.
    """

    model_config = ConfigDict(extra="allow")

    sub: str
    tenant_id: str = ""
    email: str = ""
    display_name: str = ""
    role: str = "OPERATOR"
    is_active: bool = True
    preferred_username: str | None = None
    realm_access_roles: list[str] = Field(default_factory=list)
    iat: int = 0
    exp: int = 0


# -----------------------------------------------------------------------------
# Profile response schemas — dùng trong GET /auth/me
# -----------------------------------------------------------------------------


class UserProfilePayload(BaseModel):
    """User profile payload — dùng cho GET /auth/me (trả từ JWT claims).

    Lưu ý: payload này PHẢI build từ decoded Keycloak JWT, KHÔNG query DB.
    User info là single source of truth ở Keycloak, backend chỉ pass-through.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Keycloak sub claim (user ID)")
    email: str = Field(..., description="Từ email claim")
    display_name: str = Field(..., description="Từ name hoặc preferred_username claim")
    role: str = Field(..., description="RBAC role đã map từ realm_access.roles[]")
    tenant_id: str = Field(..., description="Tenant scope — từ tenant_id custom claim")


class MeResponse(BaseModel):
    """Response shape cho GET /auth/me — alias cho UserProfilePayload.

    Giữ riêng để dễ mở rộng (vd thêm metadata fields) mà không phá
    UserProfilePayload đang được dùng ở chỗ khác.
    """

    id: str
    email: str
    display_name: str
    role: str
    tenant_id: str
