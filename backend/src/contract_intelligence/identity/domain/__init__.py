"""Identity domain — pure Python, no framework dependencies."""

from contract_intelligence.identity.domain.entities.app_user import (
    AppUser,
    UserRole,
)

__all__ = ["AppUser", "UserRole"]
