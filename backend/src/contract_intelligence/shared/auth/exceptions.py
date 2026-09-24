"""Auth-specific exceptions — domain-level, no HTTP dependencies."""

from __future__ import annotations


class AuthenticationError(Exception):
    """Xác thực thất bại — sai password, token hết hạn, không hợp lệ."""

    def __init__(self, reason: str = "Authentication failed") -> None:
        super().__init__(reason)
        self.reason = reason


class TenantMismatchError(Exception):
    """Header X-Tenant-Id không khớp với JWT claim tenant_id."""

    def __init__(self, header_tenant: str | None, token_tenant: str | None) -> None:
        super().__init__(f"Tenant mismatch: header={header_tenant}, token={token_tenant}")
        self.header_tenant = header_tenant
        self.token_tenant = token_tenant


class InsufficientRoleError(Exception):
    """User không có vai trò cần thiết."""

    def __init__(self, required: str | tuple[str, ...]) -> None:
        required_str = ", ".join(required) if isinstance(required, tuple) else required
        super().__init__(f"Required role: {required_str}")
        self.required = required


class UserDeactivatedError(AuthenticationError):
    """User bị vô hiệu hóa — không thể đăng nhập."""

    def __init__(self, user_id: str) -> None:
        super().__init__(f"User {user_id!r} is deactivated")
        self.user_id = user_id
