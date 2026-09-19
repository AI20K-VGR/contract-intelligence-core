"""Seed dev users — chạy 1 lần để tạo 3 user test trong DB.

Usage:
    # Local dev (PostgreSQL đang chạy ở localhost:5432)
    cd backend
    uv run python scripts/seed_dev_users.py

    # Hoặc với custom DSN
    DATABASE_URL=postgresql+asyncpg://user:pass@host/db \\
        uv run python scripts/seed_dev_users.py

Tạo 3 user cố định:
    tenant_id      email                       password      role
    tenant_vgr_01  admin@vgr.vn                Admin@123     ADMINISTRATOR
    tenant_vgr_01  reviewer@vgr.vn             Reviewer@123  REVIEWER
    tenant_vgr_01  operator@vgr.vn             Operator@123  OPERATOR

Idempotent: nếu user đã tồn tại → skip. Chạy nhiều lần OK.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add backend/src to path so script works without install
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from contract_intelligence.config.settings import get_settings  # noqa: E402
from contract_intelligence.identity.domain.entities.app_user import AppUser, UserRole  # noqa: E402
from contract_intelligence.identity.infrastructure.persistence.orm import AppUserORM  # noqa: E402
from contract_intelligence.identity.infrastructure.persistence.user_repository_impl import (  # noqa: E402
    UserRepositoryImpl,
)
from contract_intelligence.identity.infrastructure.security.password_hasher import (  # noqa: E402
    Argon2PasswordHasher,
)


_DEV_USERS: list[tuple[str, str, str, str, str]] = [
    # (id, tenant_id, email, display_name, plaintext_password, role)
    (
        "usr_dev_admin",
        "tenant_vgr_01",
        "admin@vgr.vn",
        "Nguyễn Quản Trị",
        "Admin@123",
        UserRole.ADMINISTRATOR,
    ),
    (
        "usr_dev_reviewer",
        "tenant_vgr_01",
        "reviewer@vgr.vn",
        "Trần Thị Phê Duyệt",
        "Reviewer@123",
        UserRole.REVIEWER,
    ),
    (
        "usr_dev_operator",
        "tenant_vgr_01",
        "operator@vgr.vn",
        "Lê Văn Vận Hành",
        "Operator@123",
        UserRole.OPERATOR,
    ),
]


async def seed_users(session: AsyncSession) -> None:
    """Insert dev users vào DB nếu chưa tồn tại."""
    hasher = Argon2PasswordHasher()
    repo = UserRepositoryImpl(session)

    for user_id, tenant_id, email, name, password, role in _DEV_USERS:
        # Check existing
        stmt = select(AppUserORM).where(AppUserORM.id == user_id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            print(f"  ⏭  SKIP {user_id} ({email}) — already exists")
            continue

        user = AppUser(
            id=user_id,
            tenant_id=tenant_id,
            email=email,
            display_name=name,
            role=role,
            password_hash=hasher.hash(password),
            is_active=True,
            token_version=0,
        )
        await repo.save(user)
        print(f"  ✅ INSERT {user_id} ({email}, role={role.value})")

    await session.commit()


async def main() -> None:
    """Main entry: bind engine, seed, close."""
    settings = get_settings()
    print(f"🌱 Seeding dev users to {settings.database_url.split('@')[-1]}")
    print()

    engine = create_async_engine()
    AsyncSessionLocal = async_sessionmaker(
        bind=engine, expire_on_commit=False, class_=AsyncSession
    )

    try:
        async with AsyncSessionLocal() as session:
            await seed_users(session)
        print()
        print("🎉 Done. Test với:")
        print("   curl -X POST http://localhost:8000/api/v1/auth/login \\")
        print("        -H 'X-Tenant-Id: tenant_vgr_01' \\")
        print("        -H 'Content-Type: application/json' \\")
        print('        -d \'{"email":"admin@vgr.vn","password":"Admin@123"}\'')
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
