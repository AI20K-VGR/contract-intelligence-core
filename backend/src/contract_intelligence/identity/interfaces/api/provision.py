"""Đưa user đang đăng nhập vào app_user nếu Keycloak chưa sync.

Thẩm định lưu reviewer_id = claim `sub`. Tên và email chỉ hiện khi có dòng
app_user khớp id hoặc keycloak_sub. User seed (admin@ci.local) không đi qua
webhook, nên lần gọi /auth/me hoặc API thẩm định sẽ tạo dòng đó.
"""

from __future__ import annotations

from contract_intelligence.identity.domain.repositories.user_repository import (
    UserRepository,
)
from contract_intelligence.shared.auth.schemas import AuthenticatedUser

_ROLES = frozenset({"OPERATOR", "REVIEWER", "ADMINISTRATOR"})


async def ensure_app_user(repo: UserRepository, user: AuthenticatedUser) -> None:
    """Tạo app_user từ JWT khi chưa có. Không ghi đè hồ sơ đã tồn tại."""
    if not user.user_id or not user.tenant_id:
        return
    existing = await repo.get_by_keycloak_sub(user.user_id)
    if existing is not None:
        return
    email = user.email.strip() or f"{user.user_id}@keycloak.local"
    display_name = user.display_name.strip() or email
    role = user.role if user.role in _ROLES else "OPERATOR"
    await repo.upsert_from_keycloak(
        keycloak_sub=user.user_id,
        tenant_id=user.tenant_id,
        email=email,
        display_name=display_name,
        role=role,
    )
