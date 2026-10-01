"""Identity domain repositories — abstract protocols, no ORM."""

from contract_intelligence.identity.domain.repositories.user_repository import (
    UserRepository,
)

__all__ = ["UserRepository"]
