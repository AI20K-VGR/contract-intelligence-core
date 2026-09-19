r"""POST /auth/login, /auth/refresh, /auth/me, /auth/logout.

Layer: interfaces (FastAPI router) — composition root cho auth flow.

Wiring (Sprint 2):
    AsyncSession → UserRepositoryImpl → AuthService (real, không stub)
    get_auth_service dependency từ interfaces/api/dependencies.py

Auth flow:
    POST /auth/login     → AuthService.login() → LoginResponse (201)
    POST /auth/refresh  → AuthService.refresh() → RefreshResponse (200)
    GET  /auth/me       → AuthService.get_profile() → MeResponse (200)
    POST /auth/logout   → AuthService.logout() → LogoutResponse (200)

Headers trả về:
    WWW-Authenticate: Bearer  (kèm 401 response)

Mã lỗi:
    AuthenticationError → 401 Unauthorized (handled bởi main.py exception handler)
    UserDeactivatedError → 401 Unauthorized
    InsufficientRoleError → 403 Forbidden
    TenantMismatchError → 403 Forbidden
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from contract_intelligence.identity.interfaces.api.dependencies import AuthServiceDep
from contract_intelligence.shared.auth.dependencies import get_current_user
from contract_intelligence.shared.auth.exceptions import (
    AuthenticationError,
    UserDeactivatedError,
)
from contract_intelligence.shared.auth.schemas import (
    AuthenticatedUser,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    MeResponse,
    RefreshRequest,
    RefreshResponse,
    UserProfilePayload,
)
from contract_intelligence.shared.responses import ApiResponse

router = APIRouter(tags=["Authentication"])


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------


@router.post(
    "/login",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[LoginResponse],
    summary="Login — nhận JWT access + refresh tokens",
    responses={
        401: {"description": "Invalid credentials hoặc user bị vô hiệu hóa"},
    },
)
async def login(
    body: LoginRequest,
    x_tenant_id: Annotated[str, Header(description="Tenant ID, ví dụ tenant_vgr_01")],
    svc: AuthServiceDep,
) -> ApiResponse[LoginResponse]:
    """Xác thực email + password, trả về JWT tokens.

    Args:
        body: email và password.
        x_tenant_id: Tenant scope — email là unique per tenant.
        svc: AuthService được inject qua Depends.

    Returns:
        access_token (JWT, 1 giờ), refresh_token (JWT, 7 ngày),
        expires_in (giây), user profile.

    Raises:
        400: X-Tenant-Id header missing.
        401: Invalid credentials hoặc user deactivated.
    """
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-Id header is required",
        )

    try:
        result = await svc.login(
            email=body.email,
            password=body.password,
            tenant_id=x_tenant_id,
        )
    except (AuthenticationError, UserDeactivatedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return ApiResponse(
        data=LoginResponse(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            expires_in=result.expires_in,
            user=UserProfilePayload(
                id=result.user_id,
                display_name=result.display_name,
                role=result.role,
                tenant_id=result.tenant_id,
            ),
        ),
    )


@router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[RefreshResponse],
    summary="Refresh access token",
    responses={
        401: {"description": "Refresh token hết hạn hoặc đã bị revoke"},
    },
)
async def refresh(
    body: RefreshRequest,
    svc: AuthServiceDep,
) -> ApiResponse[RefreshResponse]:
    """Dùng refresh token để lấy cặp access + refresh token mới.

    Args:
        body: refresh_token (JWT).
        svc: AuthService dependency.

    Returns:
        Cặp tokens mới. Refresh token cũ bị revoke ngay lập tức
        (token_version tăng).

    Raises:
        401: Refresh token không hợp lệ, hết hạn, hoặc đã bị revoke.
    """
    try:
        result = await svc.refresh(body.refresh_token)
        return ApiResponse(
            data=RefreshResponse(
                access_token=result.access_token,
                refresh_token=result.refresh_token,
                expires_in=result.expires_in,
            ),
        )
    except (AuthenticationError, UserDeactivatedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[MeResponse],
    summary="Get current user profile",
    responses={
        401: {"description": "Token không hợp lệ hoặc hết hạn"},
    },
)
async def me(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    svc: AuthServiceDep,
) -> ApiResponse[MeResponse]:
    """Lấy thông tin user hiện tại từ JWT claims + database.

    Args:
        user: Injected từ get_current_user() dependency.
        svc: AuthService dependency.

    Returns:
        User profile (id, display_name, role, tenant_id, email).
    """
    try:
        profile = await svc.get_profile(user.user_id)
        return ApiResponse(data=profile)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[LogoutResponse],
    summary="Logout — revoke refresh token",
    responses={
        401: {"description": "Token không hợp lệ"},
    },
)
async def logout(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    svc: AuthServiceDep,
) -> ApiResponse[LogoutResponse]:
    """Đăng xuất — revoke refresh token hiện tại.

    Tăng token_version trong DB → refresh token cũ bị từ chối
    ở lần refresh tiếp theo.

    Returns:
        {"data": {"message": "Logged out successfully"}}
    """
    await svc.logout(user.user_id)
    return ApiResponse(data=LogoutResponse())
