"""Durable list of ended Keycloak sessions, behind ``shared.auth.revoked_sessions``.

Keycloak calls ``POST /api/v1/auth/backchannel-logout`` once when a session
ends. The row written here lets the API refuse that session's access tokens
after a restart too; the in-memory registry answers each request without a
query. Rows are kept until no token of the session can still be valid
(``auth_revoked_session_ttl_seconds``) and deleted on the next write or load.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import DateTime, Text, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from contract_intelligence.config.settings import get_settings
from contract_intelligence.shared.auth.revoked_sessions import revoked_sessions
from contract_intelligence.shared.base import utcnow
from contract_intelligence.shared.persistence.base import Base


class RevokedSessionORM(Base):
    __tablename__ = "revoked_session"

    sid: Mapped[str] = mapped_column(Text, primary_key=True)
    sub: Mapped[str | None] = mapped_column(Text, nullable=True)
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


async def revoke_session(session: AsyncSession, *, sid: str, sub: str | None) -> datetime:
    """Persist and apply a revocation; idempotent (Keycloak may retry). Commits."""
    now = utcnow()
    expires_at = now + timedelta(seconds=get_settings().auth_revoked_session_ttl_seconds)
    await session.execute(delete(RevokedSessionORM).where(RevokedSessionORM.expires_at <= now))
    row = await session.get(RevokedSessionORM, sid)
    if row is None:
        session.add(RevokedSessionORM(sid=sid, sub=sub, revoked_at=now, expires_at=expires_at))
    else:
        row.revoked_at = now
        row.expires_at = expires_at
    await session.commit()
    # Memory only after the commit, so a failed write is reported to Keycloak
    # as a failure instead of a revocation that vanishes on the next restart.
    revoked_sessions.add(sid, expires_at.timestamp())
    return expires_at


async def load_revoked_sessions(session: AsyncSession) -> int:
    """Fill the in-memory registry from the table (startup); drop expired rows."""
    now = utcnow()
    await session.execute(delete(RevokedSessionORM).where(RevokedSessionORM.expires_at <= now))
    rows = (
        await session.execute(
            select(RevokedSessionORM.sid, RevokedSessionORM.expires_at).where(
                RevokedSessionORM.expires_at > now
            )
        )
    ).all()
    await session.commit()
    revoked_sessions.replace({sid: _aware(expires_at).timestamp() for sid, expires_at in rows})
    return len(rows)


def _aware(value: datetime) -> datetime:
    # SQLite (tests) returns naive datetimes for timezone=True columns.
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


__all__ = ["RevokedSessionORM", "load_revoked_sessions", "revoke_session"]
