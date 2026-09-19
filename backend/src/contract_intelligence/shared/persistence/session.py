"""AsyncSession factory + FastAPI Depends() cho database session.

Pattern:
    1. create_async_engine() — singleton engine, lifecycle gắn với app
    2. create_session_factory() — AsyncSessionLocal = async_sessionmaker(engine)
    3. get_async_session() — FastAPI dependency tạo AsyncSession per-request

Engine reuse giữa requests → tránh overhead tạo connection pool mỗi request.
Session per-request → đảm bảo rollback tự động nếu có exception.

Production: asyncpg driver qua postgresql+asyncpg://
Test:        aiosqlite driver qua sqlite+aiosqlite:// (in-memory)
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine as _create_async_engine,
)

from contract_intelligence.config.settings import get_settings


def create_async_engine() -> AsyncEngine:
    """Tạo AsyncEngine singleton từ settings.database_url.

    Returns:
        AsyncEngine configured với pool size + echo từ settings.

    Note:
        Echo SQL khi settings.database_echo = True (debug only).
    """
    settings = get_settings()
    return _create_async_engine(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        echo=settings.database_echo,
        future=True,
    )


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Tạo session factory gắn với engine.

    Usage:
        engine = create_async_engine()
        AsyncSessionLocal = create_session_factory(engine)

        async with AsyncSessionLocal() as session:
            await session.execute(...)
    """
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,  # Pydantic serialize sau commit
        autoflush=False,
        class_=AsyncSession,
    )


# -----------------------------------------------------------------------------
# FastAPI dependency — inject AsyncSession vào router
# -----------------------------------------------------------------------------

# Module-level singleton — main.py set trong lifespan
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def bind_engine(engine: AsyncEngine) -> None:
    """Bind engine singleton — gọi 1 lần trong main.py lifespan startup."""
    global _engine, _session_factory  # noqa: PLW0603
    _engine = engine
    _session_factory = create_session_factory(engine)


def get_engine() -> AsyncEngine:
    """Lấy engine singleton — dùng cho background workers (orchestrator).

    Background tasks (FastAPI BackgroundTasks, Celery, Arq...) không thể dùng
    request-scoped ``get_async_session`` dependency. Module này cung cấp
    accessor cho engine + factory để worker tự mở session mới.
    """
    if _engine is None:
        msg = (
            "Database engine chưa được bind. "
            "Gọi bind_engine() trong main.py lifespan startup, "
            "hoặc trong test fixture."
        )
        raise RuntimeError(msg)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Lấy session factory singleton — dùng cho background workers."""
    if _session_factory is None:
        msg = (
            "Session factory chưa được bind. "
            "Gọi bind_engine() trong main.py lifespan startup."
        )
        raise RuntimeError(msg)
    return _session_factory


def reset_engine() -> None:
    """Reset engine singleton — gọi 1 lần trong lifespan shutdown.

    Test fixture cũng dùng cái này để cleanup giữa các test.
    """
    global _engine, _session_factory  # noqa: PLW0603
    _engine = None
    _session_factory = None


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: tạo AsyncSession per-request, auto-commit/rollback.

    Usage trong router:
        async def endpoint(
            session: AsyncSession = Depends(get_async_session),
            user: AuthenticatedUser = Depends(get_current_user),
        ):
            repo = UserRepositoryImpl(session)
            ...

    Lifecycle:
        - START: tạo AsyncSession mới
        - END: commit nếu không exception, rollback nếu có, close session

    Yields:
        AsyncSession bound to engine — caller dùng async with.
    """
    if _session_factory is None:
        msg = (
            "Database engine chưa được bind. "
            "Gọi bind_engine() trong main.py lifespan startup, "
            "hoặc trong test fixture."
        )
        raise RuntimeError(msg)

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Re-export để caller dùng: `Depends(SessionDep)`
SessionDep = Depends(get_async_session)


__all__ = [
    "SessionDep",
    "bind_engine",
    "create_async_engine",
    "create_session_factory",
    "get_async_session",
    "reset_engine",
]

