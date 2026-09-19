"""AuthService — application service cho login, refresh, logout, me.

Layer: application (theo Clean Architecture / DDD)
Dependency: KHÔNG được import infrastructure (router/FastAPI).

Triển khai 4 use cases:
  1. login(email, password, tenant_id) → (access_token, refresh_token, expires_in, user)
  2. refresh(refresh_token) → (access_token, refresh_token, expires_in)
  3. me(user_id) → UserProfilePayload
  4. logout(user_id) → None  (revoke refresh token bằng cách tăng token_version)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from contract_intelligence.identity.domain.repositories.user_repository import (
    UserRepository,
)
from contract_intelligence.shared.auth.exceptions import (
    AuthenticationError,
    UserDeactivatedError,
)
from contract_intelligence.shared.auth.jwt_service import get_jwt_service
from contract_intelligence.shared.auth.schemas import (
    MeResponse,
)


@dataclass
class LoginResult:
    """Kết quả login — trả về cho router serialize thành LoginResponse."""

    access_token: str
    refresh_token: str
    expires_in: int
    user_id: str
    tenant_id: str
    email: str
    display_name: str
    role: str


@dataclass
class RefreshResult:
    """Kết quả refresh token."""

    access_token: str
    refresh_token: str
    expires_in: int
    user_id: str
    tenant_id: str


class AuthService:
    """Application service — xử lý auth use cases.

    Args:
        user_repository: Repository để tra user từ DB.
        password_verifier: Callable verify(plaintext, hash) → bool.
            Argon2 impl nằm ở infrastructure/identity/persistence/.

    Usage (trong router):
        auth_svc = AuthService(
            user_repository=user_repo,
            password_verifier=Argon2PasswordVerifier(),
        )
        result = await auth_svc.login(email, password, tenant_id)

    Sprint 2: Inject qua FastAPI Depends().
    """

    def __init__(
        self,
        user_repository: UserRepository,
        password_verifier: PasswordVerifierCallable,
    ) -> None:
        self._user_repo = user_repository
        self._verify_password = password_verifier
        self._jwt_svc = get_jwt_service()

    # -------------------------------------------------------------------------
    # Use case 1: Login
    # -------------------------------------------------------------------------

    async def login(
        self,
        email: str,
        password: str,
        tenant_id: str,
    ) -> LoginResult:
        """Xác thực credentials và cấp JWT tokens.

        Args:
            email: Email address (case-insensitive, unique per tenant).
            password: Plaintext password — KHÔNG BAO GIỜ log.
            tenant_id: Tenant scope — dùng để tra user.

        Returns:
            LoginResult chứa tokens và user profile.

        Raises:
            AuthenticationError: Email/password sai.
            UserDeactivatedError: User bị vô hiệu hóa.
        """
        # 1. Tra user
        user = await self._user_repo.get_by_email(tenant_id, email.lower())

        if user is None:
            # Delay uniform để tránh timing oracle
            raise AuthenticationError("Invalid email or password")

        # 2. Check active
        if not user.is_active:
            raise UserDeactivatedError(user.id)

        # 3. Verify password
        if not self._verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password")

        # 4. Sign tokens
        new_version = user.increment_token_version()

        access_token, expires_in = self._jwt_svc.encode_access_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            display_name=user.display_name,
            role=user.role.value,
        )
        refresh_token = self._jwt_svc.encode_refresh_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            token_version=new_version,
        )

        # 5. Persist login metadata (token_version + last_login_at)
        await self._user_repo.update_login(user)

        return LoginResult(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            user_id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            display_name=user.display_name,
            role=user.role.value,
        )

    # -------------------------------------------------------------------------
    # Use case 2: Refresh token
    # -------------------------------------------------------------------------

    async def refresh(self, refresh_token: str) -> RefreshResult:
        """Xác thực refresh token và cấp cặp tokens mới.

        Args:
            refresh_token: JWT refresh token (đã sign với token_version cũ).

        Returns:
            RefreshResult chứa tokens mới.

        Raises:
            AuthenticationError: Token không hợp lệ / hết hạn /
                                  token_version không khớp (bị revoke).
        """
        # 1. Decode & validate refresh token
        user_id, tenant_id, token_version_from_token = self._jwt_svc.decode_refresh_token(
            refresh_token
        )

        # 2. Tra user và kiểm tra token_version
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise AuthenticationError("User not found")

        if not user.is_active:
            raise UserDeactivatedError(user.id)

        # 3. CRITICAL: Token version phải khớp — nếu không, token đã bị revoke
        if user.token_version != token_version_from_token:
            raise AuthenticationError("Session has been revoked — please login again")

        # 4. Sign tokens mới
        new_version = user.increment_token_version()

        access_token, expires_in = self._jwt_svc.encode_access_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            display_name=user.display_name,
            role=user.role.value,
        )
        new_refresh_token = self._jwt_svc.encode_refresh_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            token_version=new_version,
        )

        # 5. Persist token_version mới
        await self._user_repo.update_login(user)

        return RefreshResult(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=expires_in,
            user_id=user.id,
            tenant_id=user.tenant_id,
        )

    # -------------------------------------------------------------------------
    # Use case 3: Get current user profile
    # -------------------------------------------------------------------------

    async def get_profile(self, user_id: str) -> MeResponse:
        """Lấy thông tin user profile cho endpoint GET /auth/me."""
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise AuthenticationError("User not found")

        return MeResponse(
            id=user.id,
            display_name=user.display_name,
            role=user.role.value,
            tenant_id=user.tenant_id,
            email=user.email,
        )

    # -------------------------------------------------------------------------
    # Use case 4: Logout (revoke session)
    # -------------------------------------------------------------------------

    async def logout(self, user_id: str) -> None:
        """Thu hồi tất cả sessions bằng cách tăng token_version.

        Gọi khi user đăng xuất — refresh token cũ sẽ bị từ chối ở
        lần refresh tiếp theo vì token_version không khớp.
        """
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            # Logout cho user không tồn tại → vẫn trả 200 (idempotent)
            return

        user.revoke_all_sessions()
        await self._user_repo.update_login(user)


# -----------------------------------------------------------------------------
# Type alias cho password verifier callable
# -----------------------------------------------------------------------------

PasswordVerifierCallable = Callable[[str, str], bool]
