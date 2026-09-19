"""SQLAlchemy ORM model cho bảng ``app_user``.

Layer: infrastructure (persistence) — import SQLAlchemy 2.0 typed Mapped API.

Schema reference: ``docs/DOC-04b-postgres-schema.sql`` §2 + alembic v2__create_app_user.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from contract_intelligence.shared.persistence.base import Base


class AppUserORM(Base):
    """ORM mapping cho ``app_user`` table.

    Columns mapping với entity ``AppUser`` (xem ``identity/domain/entities/app_user.py``):
        id           → TEXT PK (prefix "usr_")
        tenant_id    → TEXT NOT NULL
        email        → TEXT NOT NULL
        display_name → TEXT NOT NULL
        role         → TEXT NOT NULL (CHECK constraint)
        password_hash → TEXT NOT NULL (Argon2id)
        is_active    → BOOLEAN DEFAULT true
        last_login_at → TIMESTAMPTZ NULL
        token_version → INTEGER DEFAULT 0
        created_at   → TIMESTAMPTZ DEFAULT now()
        updated_at   → TIMESTAMPTZ DEFAULT now() ON UPDATE now()

    Indexes (matching alembic migration):
        ix_app_user_tenant        — (tenant_id)
        ix_app_user_tenant_email  — UNIQUE (tenant_id, email)
        ix_app_user_is_active     — (is_active)
    """

    __tablename__ = "app_user"

    # Primary key
    id: Mapped[str] = mapped_column(Text, primary_key=True)

    # Tenant isolation
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # Identity
    email: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)

    # Credentials
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    # Lifecycle
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", index=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Constraints — must match alembic v2__create_app_user migration
    __table_args__ = (
        CheckConstraint(
            "role IN ('OPERATOR', 'REVIEWER', 'ADMINISTRATOR')",
            name="ck_app_user_role",
        ),
        Index("ix_app_user_tenant_email", "tenant_id", "email", unique=True),
    )

    def __repr__(self) -> str:  # pragma: no cover — debug only
        return (
            f"<AppUserORM id={self.id!r} tenant_id={self.tenant_id!r} "
            f"email={self.email!r} role={self.role!r}>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize thành dict — dùng trong seed script / debug log."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role,
            "is_active": self.is_active,
            "last_login_at": self.last_login_at.isoformat()
            if self.last_login_at
            else None,
            "token_version": self.token_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


__all__ = ["AppUserORM"]


# Marker import để type checker biết UTC được dùng
_ = UTC
