"""UserRepository protocol — domain định nghĩa, infrastructure impl."""

from __future__ import annotations

from abc import ABC, abstractmethod

from contract_intelligence.identity.domain.entities.app_user import AppUser


class UserRepository(ABC):
    """Abstract repository cho AppUser.

    Domain layer định nghĩa protocol này. Infrastructure layer
    (persistence/) implement bằng SQLAlchemy.
    """

    @abstractmethod
    async def get_by_id(self, user_id: str) -> AppUser | None:
        """Lấy user theo id (usr_...)."""

    @abstractmethod
    async def get_by_email(self, tenant_id: str, email: str) -> AppUser | None:
        """Lấy user theo email trong phạm vi tenant.

        Args:
            tenant_id: Scope tenant — email là unique per tenant.
            email: Email address (case-insensitive).

        Returns:
            AppUser nếu tồn tại, None nếu không.
        """

    @abstractmethod
    async def save(self, user: AppUser) -> None:
        """Tạo mới hoặc cập nhật user."""

    @abstractmethod
    async def update_login(self, user: AppUser) -> None:
        """Cập nhật last_login_at và token_version sau khi login thành công.

        Gọi trong cùng transaction với việc cấp token để đảm bảo
        refresh token cũ bị revoke ngay lập tức.
        """
