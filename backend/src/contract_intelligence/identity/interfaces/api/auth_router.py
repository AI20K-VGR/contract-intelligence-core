r"""GET /auth/me — chỉ endpoint auth duy nhất còn lại sau khi refactor Keycloak SSO.

Layer: interfaces (FastAPI router).

LUỒNG CHUẨN (đã đối thoại với user):
    1. User đăng nhập trên frontend (React) qua Keycloak login page.
    2. Frontend nhận access_token (RS256) + refresh_token.
    3. Frontend gửi access_token trong header ``Authorization: Bearer <token>``.
    4. ``get_current_user`` dependency verify token qua Keycloak JWKS,
       build AuthenticatedUser từ JWT claims.
    5. Endpoint này đơn giản pass-through — trả về profile từ JWT claims.

Backend KHÔNG issue token. Không có /login, /refresh, /logout trên backend
(frontend gọi thẳng Keycloak cho các flow đó).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from contract_intelligence.shared.auth.dependencies import get_current_user
from contract_intelligence.shared.auth.schemas import (
    AuthenticatedUser,
    MeResponse,
    UserProfilePayload,
)
from contract_intelligence.shared.responses import ApiResponse

router = APIRouter(tags=["Authentication"])


@router.get(
    "/me",
    status_code=200,
    response_model=ApiResponse[MeResponse],
    summary="Get current user profile (từ Keycloak JWT claims)",
    responses={
        401: {"description": "Token không hợp lệ, hết hạn, hoặc không phải Keycloak"},
    },
)
async def me(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> ApiResponse[MeResponse]:
    """Lấy thông tin user hiện tại — pass-through từ Keycloak JWT claims.

    Args:
        user: AuthenticatedUser được inject từ ``get_current_user()``
            (đã verify Keycloak RS256 signature + map claims).

    Returns:
        UserProfilePayload chứa id, email, display_name, role, tenant_id
        — tất cả từ JWT claims, KHÔNG query DB.
    """
    return ApiResponse(
        data=MeResponse(
            id=user.user_id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            tenant_id=user.tenant_id,
        ),
    )


# `UserProfilePayload` re-exported để các router khác có thể import từ đây
# thay vì phải biết đường dẫn đầy đủ tới shared/auth/schemas.
__all__ = ["router", "UserProfilePayload"]
