"""AppUser entity — domain model cho user trong hệ thống.

Sau khi refactor sang Keycloak SSO:
    - User identity (email, password, role, ...) → quản lý bởi Keycloak.
    - Backend chỉ cache thông tin cần thiết để join với audit logs
      (vd: dossier.created_by, review.approved_by) thông qua
      Keycloak user provisioning webhook.
    - KHÔNG lưu password_hash ở backend (Keycloak quản lý password).
    - KHÔNG cần token_version (Keycloak quản lý refresh token revocation).

Domain invariants giữ lại:
    - deactivate(): Đánh dấu user bị vô hiệu hóa — admin dùng để cấm truy cập
      ngay cả khi Keycloak token còn valid. Check ở middleware/dependency.
    - activate(): Kích hoạt lại user.

Tất cả fields là plain Python — không dùng SQLAlchemy/Pydantic.
ORM mapping thực hiện trong infrastructure/persistence/.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from contract_intelligence.shared.base import BaseEntity, new_ulid


class UserRole(StrEnum):
    """RBAC roles — matching DOC-05b §2.3 matrix."""

    OPERATOR = "OPERATOR"
    REVIEWER = "REVIEWER"
    ADMINISTRATOR = "ADMINISTRATOR"


@dataclass(eq=False)
class AppUser(BaseEntity[str]):
    """User account entity — local cache cho Keycloak user.

    Source of truth cho user identity là Keycloak. Backend chỉ lưu cache
    các field cần thiết cho business logic (audit log joins, admin actions).

    Attributes:
        id: User ID — match Keycloak `sub` claim. Dùng prefix "usr_"
            nếu đã provision, hoặc raw Keycloak UUID/sub nếu lazy-create.
        tenant_id: Tenant scope — dùng cho tenant isolation trên mọi query.
        email: Email từ Keycloak (sync qua webhook).
        display_name: Tên hiển thị từ Keycloak `name` hoặc `preferred_username`.
        role: Một trong OPERATOR / REVIEWER / ADMINISTRATOR — map từ
            Keycloak `realm_access.roles[]`.
        is_active: False khi admin disable user trên backend.
            Lưu ý: Keycloak có cơ chế disable riêng (account.enabled),
            backend is_active là lớp bảo vệ thứ 2.
        created_at: Timestamp tạo local cache.
        updated_at: Timestamp lần sync cuối từ Keycloak.

    Invariants:
        - Khi deactivate(): set is_active = False.
        - Khi activate(): set is_active = True.
        - update_profile(): chỉ sync từ Keycloak — KHÔNG cho phép BE tự sửa.
    """

    id: str = field(default_factory=lambda: new_ulid("usr_"))
    tenant_id: str = ""
    email: str = ""
    display_name: str = ""
    role: UserRole = UserRole.OPERATOR
    is_active: bool = True
    keycloak_sub: str | None = None  # Original Keycloak sub claim nếu id khác

    # -------------------------------------------------------------------------
    # Domain invariants
    # -------------------------------------------------------------------------

    def deactivate(self) -> None:
        """Vô hiệu hóa user — không thể truy cập API ngay cả khi Keycloak token valid.

        Đây là lớp bảo vệ backend-side. Admin dùng để cấm user trong TH
        cần revoke truy cập ngay mà không cần chờ Keycloak session timeout.
        """
        self.is_active = False
        self.touch()

    def activate(self) -> None:
        """Kích hoạt lại user (admin re-enable)."""
        self.is_active = True
        self.touch()

    def update_profile(
        self,
        email: str | None = None,
        display_name: str | None = None,
        role: UserRole | None = None,
        tenant_id: str | None = None,
    ) -> None:
        """Sync profile từ Keycloak — chỉ update các field được truyền vào.

        Args:
            email: Email mới từ Keycloak (None = giữ nguyên).
            display_name: Display name mới từ Keycloak.
            role: RBAC role mới đã map từ Keycloak roles.
            tenant_id: Tenant mới (thường không đổi sau initial provision).
        """
        if email is not None:
            self.email = email
        if display_name is not None:
            self.display_name = display_name
        if role is not None:
            self.role = role
        if tenant_id is not None:
            self.tenant_id = tenant_id
        self.touch()


__all__ = ["AppUser", "UserRole"]
