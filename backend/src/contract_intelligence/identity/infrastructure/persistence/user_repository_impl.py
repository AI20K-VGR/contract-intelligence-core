"""UserRepository SQLAlchemy async implementation.

Layer: infrastructure (persistence) — concrete impl của UserRepository protocol.

Queries (sau refactor Keycloak SSO):
    get_by_id             → SELECT WHERE id = $1
    get_by_keycloak_sub   → SELECT WHERE keycloak_sub = $1
    upsert_from_keycloak  → INSERT (nếu chưa có) hoặc UPDATE profile (nếu có)
    save                  → INSERT hoặc UPDATE — cho admin operations

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
    """Convert ORM row → domain entity."""
    return AppUser(
        id=orm.id,
        tenant_id=orm.tenant_id,
        email=orm.email,
        display_name=orm.display_name,
        role=UserRole(orm.role),
        is_active=orm.is_active,
        keycloak_sub=orm.keycloak_sub,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _from_domain(user: AppUser) -> AppUserORM:
    """Convert domain entity → ORM instance (chưa attach session)."""
    return AppUserORM(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role.value,
        is_active=user.is_active,
        keycloak_sub=user.keycloak_sub,
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

    async def get_by_keycloak_sub(self, keycloak_sub: str) -> AppUser | None:
        """SELECT * FROM app_user WHERE keycloak_sub = $1.

        Args:
            keycloak_sub: Original `sub` claim từ Keycloak JWT.

        Returns:
            AppUser nếu đã provision, None nếu chưa.
        """
        stmt = select(AppUserORM).where(AppUserORM.keycloak_sub == keycloak_sub)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    # -------------------------------------------------------------------------
    # Write
    # -------------------------------------------------------------------------

    async def save(self, user: AppUser) -> None:
        """INSERT hoặc UPDATE — dùng cho admin operations (deactivate/activate).

        Race condition được handle qua unique index (keycloak_sub).
        """
        existing = await self.get_by_id(user.id)
        if existing is None:
            orm = _from_domain(user)
            self._session.add(orm)
            try:
                await self._session.flush()
            except IntegrityError as exc:
                await self._session.rollback()
                raise exc
        else:
            stmt = select(AppUserORM).where(AppUserORM.id == user.id)
            result = await self._session.execute(stmt)
            orm = result.scalar_one()
            orm.email = user.email
            orm.display_name = user.display_name
            orm.role = user.role.value
            orm.is_active = user.is_active
            orm.keycloak_sub = user.keycloak_sub or user.id
            orm.updated_at = utcnow()
            await self._session.flush()

    async def upsert_from_keycloak(
        self,
        *,
        keycloak_sub: str,
        tenant_id: str,
        email: str,
        display_name: str,
        role: str,
    ) -> AppUser:
        """Tạo mới hoặc cập nhật user từ Keycloak claims.

        Idempotent:
            - Nếu keycloak_sub chưa tồn tại → INSERT với id = usr_<keycloak_sub>
            - Nếu đã tồn tại → UPDATE profile (email, display_name, role, tenant)

        Args:
            keycloak_sub: `sub` claim từ Keycloak JWT (unique).
            tenant_id: Tenant scope — từ custom claim hoặc realm.
            email: Email từ Keycloak.
            display_name: Tên hiển thị từ Keycloak.
            role: RBAC role đã map (OPERATOR | REVIEWER | ADMINISTRATOR).

        Returns:
            AppUser đã được persist (existing hoặc newly created).
        """
        existing = await self.get_by_keycloak_sub(keycloak_sub)
        if existing is not None:
            # UPDATE profile — không đổi id, is_active giữ nguyên
            stmt = select(AppUserORM).where(AppUserORM.keycloak_sub == keycloak_sub)
            result = await self._session.execute(stmt)
            orm = result.scalar_one()
            orm.email = email
            orm.display_name = display_name
            orm.role = role
            orm.tenant_id = tenant_id
            orm.updated_at = utcnow()
            await self._session.flush()
            existing.update_profile(
                email=email,
                display_name=display_name,
                role=UserRole(role),
                tenant_id=tenant_id,
            )
            return existing

        # INSERT — tạo mới với id deterministic từ keycloak_sub để idempotent
        new_user = AppUser(
            id=f"usr_{keycloak_sub}" if not keycloak_sub.startswith("usr_") else keycloak_sub,
            tenant_id=tenant_id,
            email=email,
            display_name=display_name,
            role=UserRole(role),
            is_active=True,
            keycloak_sub=keycloak_sub,
        )
        orm = _from_domain(new_user)
        self._session.add(orm)
        try:
            await self._session.flush()
        except IntegrityError:
            # Race condition: user khác vừa insert — rollback và re-fetch
            await self._session.rollback()
            existing = await self.get_by_keycloak_sub(keycloak_sub)
            if existing is not None:
                return existing
            raise  # pragma: no cover — không thể xảy ra nếu logic trên đúng
        return new_user


__all__ = ["UserRepositoryImpl"]
