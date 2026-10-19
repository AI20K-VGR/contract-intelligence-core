"""Pydantic schemas for B2B SaaS User Management (admin APIs)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pydantic_core import PydanticCustomError

from contract_intelligence.shared.email_delivery import (
    UNDELIVERABLE_MESSAGE,
    email_domain,
    is_undeliverable_email,
)

UserRole = Literal["OPERATOR", "REVIEWER", "ADMINISTRATOR"]
UserStatus = Literal["invited", "active", "disabled"]


class UserDTO(BaseModel):
    """User representation returned by user-management APIs."""

    model_config = ConfigDict(extra="forbid")

    id: str
    email: str
    display_name: str
    role: UserRole
    status: UserStatus
    created_at: datetime | None = None
    invited_at: datetime | None = None
    last_login_at: datetime | None = None


class UserDirectoryEntryDTO(BaseModel):
    """A tenant member as other members may see them: who to share a dossier with.

    Deliberately not ``UserDTO``: no status, invite or login fields.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    email: str
    display_name: str
    role: UserRole


class UserCreateRequest(BaseModel):
    """POST /api/v1/users — invite a new user."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr
    display_name: str = Field(..., min_length=1, max_length=255)
    role: UserRole

    @field_validator("email", mode="before")
    @classmethod
    def _lowercase_email(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip().lower()
            # Before EmailStr, which rejects .local/.test with a generic English error.
            if email_domain(value) and is_undeliverable_email(value):
                raise PydanticCustomError("email_domain_undeliverable", UNDELIVERABLE_MESSAGE)
        return value


class UserPatchRequest(BaseModel):
    """PATCH /api/v1/users/{id} — update realm role."""

    model_config = ConfigDict(extra="forbid")

    role: UserRole


# Kept for backward-compatible imports / tests that referenced the Sprint-2 invite body.
class UserInviteRequest(BaseModel):
    """Legacy invite payload — prefer ``UserCreateRequest``."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    role: str = Field(..., min_length=1)


__all__ = [
    "UserCreateRequest",
    "UserDTO",
    "UserDirectoryEntryDTO",
    "UserInviteRequest",
    "UserPatchRequest",
    "UserRole",
    "UserStatus",
]
