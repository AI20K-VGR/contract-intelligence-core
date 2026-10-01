"""Pydantic schemas for B2B SaaS User Management (admin APIs)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

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
            return value.strip().lower()
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
    "UserInviteRequest",
    "UserPatchRequest",
    "UserRole",
    "UserStatus",
]
