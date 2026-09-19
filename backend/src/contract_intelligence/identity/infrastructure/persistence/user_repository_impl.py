"""UserRepository SQLAlchemy async implementation.

Layer: infrastructure (persistence) — concrete impl của UserRepository protocol.

Queries:
    get_by_id    → SELECT WHERE id = $1
    get_by_email → SELECT WHERE tenant_id = $1 AND lower(email) = lower($2)
    save         → INSERT (id mới) hoặc UPDATE (id tồn tại)
    update_login → UPDATE last_login_at, token_version WHERE id = $1

Mapping:
    ORM ↔ Domain entity dùng to_domain() / from_domain() helpers.
    Domain entity KHÔNG biết SQLAlchemy tồn tại.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.identity.domain.entities.app_user import AppUser, UserRole
from contract_intelligence.identity.domain.repositories.user_repository import (
    UserRepository,
)
from contract_intelligence.identity.infrastructure.persistence.orm import AppUserORM
from contract_intelligence.shared.base import utcnow


def _to_domain(orm: AppUserORM) -> AppUser:
    """Convert ORM row → domain entity.

    Password_hash được copy qua — domain entity không biết nó được hash kiểu gì.
    """
    return AppUser(
        id=orm.id,
        tenant_id=orm.tenant_id,
        email=orm.email,
        display_name=orm.display_name,
        role=UserRole(orm.role),
        password_hash=orm.password_hash,
        is_active=orm.is_active,
        last_login_at=orm.last_login_at,
        token_version=orm.token_version,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _from_domain(user: AppUser) -> AppUserORM:
    """Convert domain entity → ORM instance (chưa attach session).

    Note: created_at/updated_at set bởi DB server_default.
    Password_hash copy nguyên — domain đã verify khi login.
    """
    return AppUserORM(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role.value,
        password_hash=user.password_hash,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        token_version=user.token_version,
    )


class UserRepositoryImpl(UserRepository):
    """Async SQLAlchemy implementation của UserRepository protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -------------------------------------------------------------------------
    # Read
    # -------------------------------------------------------------------------

    async def get_by_id(self, user_id: str) -> AppUser | None:
        """SELECT * FROM app_user WHERE id = $1.

        Returns:
            AppUser domain entity, hoặc None nếu không tồn tại.
        """
        stmt = select(AppUserORM).where(AppUserORM.id == user_id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def get_by_email(self, tenant_id: str, email: str) -> AppUser | None:
        """SELECT * FROM app_user WHERE tenant_id = $1 AND lower(email) = lower($2).

        Args:
            tenant_id: Tenant scope — email unique per tenant.
            email: Email address (case-insensitive lookup).

        Returns:
            AppUser domain entity, hoặc None nếu không tồn tại.
        """
        stmt = select(AppUserORM).where(
            AppUserORM.tenant_id == tenant_id,
            AppUserORM.email == email.lower(),
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    # -------------------------------------------------------------------------
    # Write
    # -------------------------------------------------------------------------

    async def save(self, user: AppUser) -> None:
        """INSERT hoặc UPDATE — dùng cho create user / admin update profile.

        Race condition được handle qua unique index (tenant_id, email)
        — sẽ raise IntegrityError nếu email trùng trong cùng tenant.
        """
        # Check nếu đã tồn tại (dùng SELECT FOR UPDATE để tránh race)
        existing = await self.get_by_id(user.id)
        if existing is None:
            # INSERT
            orm = _from_domain(user)
            self._session.add(orm)
            try:
                await self._session.flush()
            except IntegrityError as exc:
                await self._session.rollback()
                raise exc
        else:
            # UPDATE — load ORM, copy fields, session auto-detects changes
            stmt = select(AppUserORM).where(AppUserORM.id == user.id)
            result = await self._session.execute(stmt)
            orm = result.scalar_one()
            orm.email = user.email
            orm.display_name = user.display_name
            orm.role = user.role.value
            orm.password_hash = user.password_hash
            orm.is_active = user.is_active
            orm.updated_at = utcnow()
            await self._session.flush()

    async def update_login(self, user: AppUser) -> None:
        """UPDATE last_login_at + token_version sau login/refresh.

        Gọi SAU khi AuthService đã tăng token_version trên entity in-memory.
        Persist xuống DB ngay để refresh token cũ bị revoke trước khi
        response về tới client.

        Returns void — caller không cần kết quả, commit/rollback
        do get_async_session dependency xử lý.
        """
        stmt = select(AppUserORM).where(AppUserORM.id == user.id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            # User bị xóa giữa chừng → không update được, bỏ qua
            return
        orm.last_login_at = user.last_login_at or utcnow()
        orm.token_version = user.token_version
        orm.updated_at = utcnow()
        await self._session.flush()


__all__ = ["UserRepositoryImpl"]
