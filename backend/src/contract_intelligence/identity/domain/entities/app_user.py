"""AppUser entity — pure Python, no ORM/framework dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from contract_intelligence.shared.base import BaseEntity, new_ulid


class UserRole(StrEnum):
    """RBAC roles — matching DOC-05b §2.3 matrix."""

    OPERATOR = "OPERATOR"
    REVIEWER = "REVIEWER"
    ADMINISTRATOR = "ADMINISTRATOR"


@dataclass(eq=False)
class AppUser(BaseEntity[str]):
    """User account entity.

    Tất cả fields đều là plain Python — không dùng SQLAlchemy/Pydantic.
    ORM mapping thực hiện trong infrastructure/persistence/.

    Attributes:
        id: ULID với prefix "usr_", vd "usr_01HZXYZ..."
        tenant_id: Định danh tenant — dùng cho tenant isolation trên mọi query.
        email: Email duy nhất trong phạm vi tenant. Dùng để login.
        display_name: Tên hiển thị (full name, không phải username).
        role: Một trong OPERATOR / REVIEWER / ADMINISTRATOR.
        password_hash: Argon2 hash — KHÔNG BAO GIỜ expose ra ngoài domain.
        is_active: False khi user bị vô hiệu hóa (không login được).
        last_login_at: Timestamp đăng nhập cuối cùng (null nếu chưa bao giờ).
        token_version: Số nguyên tăng mỗi lần refresh token được cấp.
            Dùng để revoke tất cả refresh token cũ khi cần (đổi mật khẩu,
            admin disable user, logout tất cả thiết bị).
            Giá trị 0 = chưa bao giờ có refresh token.
    """

    id: str = field(default_factory=lambda: new_ulid("usr_"))
    tenant_id: str = ""
    email: str = ""
    display_name: str = ""
    role: UserRole = UserRole.OPERATOR
    password_hash: str = field(default="")
    is_active: bool = True
    last_login_at: datetime | None = None
    token_version: int = 0

    # -------------------------------------------------------------------------
    # Domain invariants
    # -------------------------------------------------------------------------

    def verify_password(self, plaintext: str, verifier: PasswordVerifier) -> bool:
        """Xác thực mật khẩu plaintext đã hash thành ``password_hash``.

        Args:
            plaintext: Mật khẩu người dùng nhập vào (chưa hash).
            verifier: PasswordHasher protocol — impl nằm ở infrastructure.

        Returns:
            True nếu khớp, False nếu không.
        """
        return verifier.verify(plaintext, self.password_hash)

    def increment_token_version(self) -> int:
        """Tăng token_version và trả về giá trị mới.

        Gọi khi cấp refresh token mới — làm vô hiệu tất cả token cũ.
        """
        self.token_version += 1
        self.touch()
        return self.token_version

    def revoke_all_sessions(self) -> None:
        """Thu hồi mọi session hiện tại bằng cách tăng token_version."""
        self.increment_token_version()

    def deactivate(self) -> None:
        """Vô hiệu hóa user — không thể đăng nhập."""
        self.is_active = False
        self.revoke_all_sessions()
        self.touch()

    def activate(self) -> None:
        """Kích hoạt lại user (admin re-enable)."""
        self.is_active = True
        self.touch()


# -----------------------------------------------------------------------------
# Value objects / Protocols (domain layer — KHÔNG có implementation ở đây)
# -----------------------------------------------------------------------------


class PasswordHasher(Protocol):
    """Protocol cho password hashing.

    Implementation (argon2) ở infrastructure/identity/persistence/.
    """

    def hash(self, plaintext: str) -> str:
        """Băm plaintext → hash string."""
        ...

    def verify(self, plaintext: str, hash_value: str) -> bool:
        """Verify plaintext against hash. Return True nếu khớp."""
        ...


class PasswordVerifier(Protocol):
    """Protocol alias — dùng cho AppUser.verify_password()."""

    def verify(self, plaintext: str, hash_value: str) -> bool:
        """Verify password."""
        ...
