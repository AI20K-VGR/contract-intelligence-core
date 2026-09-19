"""Argon2 password hashing infrastructure — impl cho domain PasswordHasher/Verifier.

Layer: infrastructure (security) — concrete impl dùng passlib + argon2-cffi.

Argon2id là OWASP recommended:
    - memory: 65536 KiB (64 MiB)
    - iterations: 3
    - parallelism: 4
    - hash_len: 32 bytes
    - salt_len: 16 bytes

Đổi constants qua env var nếu cần tune performance vs security.
"""

from __future__ import annotations

from passlib.context import CryptContext

from contract_intelligence.identity.domain.entities.app_user import (
    PasswordHasher,
    PasswordVerifier,
)

# Argon2id — OWASP recommended defaults
_argon2_context = CryptContext(
    schemes=["argon2"],
    argon2__memory_cost=65536,  # 64 MiB
    argon2__time_cost=3,  # iterations
    argon2__parallelism=4,
    deprecated="auto",
)


class Argon2PasswordHasher(PasswordHasher):
    """Concrete Argon2id password hasher.

    Implementation của ``PasswordHasher`` Protocol từ domain layer.
    """

    def hash(self, plaintext: str) -> str:
        """Băm plaintext password thành Argon2id hash string.

        Output format: ``$argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>``

        Args:
            plaintext: Plaintext password — KHÔNG bao giờ log giá trị này.

        Returns:
            Argon2id hash string để lưu DB.
        """
        return str(_argon2_context.hash(plaintext))

    def verify(self, plaintext: str, hash_value: str) -> bool:
        """Verify plaintext password against Argon2 hash.

        Args:
            plaintext: Plaintext password nhập vào từ user.
            hash_value: Argon2 hash đã lưu trong DB.

        Returns:
            True nếu khớp, False nếu không (an toàn với timing attacks).
        """
        return bool(_argon2_context.verify(plaintext, hash_value))


class Argon2PasswordVerifier(PasswordVerifier):
    """Argon2 verifier — chỉ verify, không hash.

    Sprint 2 tách riêng Hasher (dùng cho seed/admin) và Verifier
    (dùng cho login flow) để giảm attack surface.
    """

    def verify(self, plaintext: str, hash_value: str) -> bool:
        """Verify plaintext password against Argon2 hash.

        Safe với timing attacks — passlib internally uses constant-time compare.
        """
        return bool(_argon2_context.verify(plaintext, hash_value))


__all__ = ["Argon2PasswordHasher", "Argon2PasswordVerifier"]
