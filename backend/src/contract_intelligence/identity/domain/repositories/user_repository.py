"""UserRepository protocol — domain định nghĩa, infrastructure impl.

Sau refactor Keycloak SSO:
    - Backend không login (không có get_by_email).
    - Backend không cập nhật last_login_at (Keycloak track riêng).
    - User data được sync từ Keycloak qua webhook (upsert_from_keycloak)
      hoặc lazy-provision trên first /me request (upsert_from_keycloak).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from contract_intelligence.identity.domain.entities.app_user import AppUser


class UserRepository(ABC):
    """Abstract repository cho AppUser — local cache của Keycloak users.

    Domain layer định nghĩa protocol này. Infrastructure layer
    (persistence/) implement bằng SQLAlchemy.
    """

    @abstractmethod
    async def get_by_id(self, user_id: str) -> AppUser | None:
        """Lấy user theo id (usr_... hoặc Keycloak sub).

        Returns:
            AppUser nếu tồn tại, None nếu không.
        """

    @abstractmethod
    async def get_by_keycloak_sub(self, keycloak_sub: str) -> AppUser | None:
        """Lấy user theo Keycloak sub claim.

        Args:
            keycloak_sub: Original `sub` claim từ Keycloak JWT.

        Returns:
            AppUser nếu đã provision, None nếu chưa.
        """

    @abstractmethod
    async def upsert_from_keycloak(
        self,
        *,
        keycloak_sub: str,
        tenant_id: str,
        email: str,
        display_name: str,
        role: str,
    ) -> AppUser:
        """Tạo mới hoặc cập nhật user từ Keycloak claims.

        Idempotent — gọi nhiều lần với cùng keycloak_sub sẽ trả về cùng user
        với profile mới nhất.

        Args:
            keycloak_sub: `sub` claim từ Keycloak JWT (unique).
            tenant_id: Tenant scope — từ custom claim hoặc realm.
            email: Email từ Keycloak.
            display_name: Tên hiển thị từ `name` hoặc `preferred_username`.
            role: RBAC role đã map (OPERATOR | REVIEWER | ADMINISTRATOR).

        Returns:
            AppUser đã được persist (existing hoặc newly created).
        """

    @abstractmethod
    async def save(self, user: AppUser) -> None:
        """Tạo mới hoặc cập nhật user — dùng cho admin operations."""
