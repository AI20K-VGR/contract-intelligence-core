"""Chunked dossier upload sessions (issue #145): tables and queries.

Layer: infrastructure/persistence.

A browser behind Cloudflare Free cannot send one request for longer than about
125 s, so a large dossier is sent as numbered chunks of ``upload_chunk_bytes``
(see ``upload_session_router``). Each chunk is a MinIO object under
``uploads/{tenant_id}/{upload_id}/`` and a row in ``upload_session_chunk``; the
session row holds what was declared at the start (files, sizes, metadata) and,
once completed, the dossier it became.

Every query here is scoped to one tenant. :func:`sweep_expired_sessions` is the
one exception: the maintenance loop runs it for every tenant.
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    and_,
    delete,
    func,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from contract_intelligence.shared.base import new_ulid, utcnow
from contract_intelligence.shared.persistence.base import Base

logger = structlog.get_logger(__name__)

# Session states. 'completing' is held while one request builds the dossier, so
# a second /complete for the same session cannot create a second dossier.
OPEN = "open"
COMPLETING = "completing"
COMPLETED = "completed"
CANCELLED = "cancelled"

# A request that died while completing (backend restart) leaves the session in
# 'completing'. After this long another /complete may take it over.
COMPLETING_STALE_AFTER = timedelta(minutes=10)
# At the per-user cap, only an open session that received no chunk for this
# long is cancelled to make room: one still sending is an upload in progress.
EVICT_IDLE_AFTER = timedelta(minutes=5)
# A completed session row (its chunks are already gone) is kept this long after
# it was opened, so a repeated /complete still answers with the dossier.
COMPLETED_KEEP = timedelta(days=7)


class UploadSessionORM(Base):
    __tablename__ = "upload_session"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default=OPEN)
    # The dossier metadata sent at the start (same JSON as POST /dossiers).
    dossier_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    # [{"index", "role", "filename", "size", "chunks"}], contract first.
    files: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    chunk_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    dossier_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_upload_session_owner", "tenant_id", "user_id", "status"),
        CheckConstraint(
            "status IN ('open', 'completing', 'completed', 'cancelled')",
            name="ck_upload_session_status",
        ),
    )


class UploadChunkORM(Base):
    __tablename__ = "upload_session_chunk"

    upload_id: Mapped[str] = mapped_column(
        Text, ForeignKey("upload_session.id", ondelete="CASCADE"), primary_key=True
    )
    file_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    object_path: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


@dataclass(frozen=True, slots=True)
class DeclaredFile:
    """One file as declared when the session opens."""

    index: int
    role: str  # "contract" | "annex"
    filename: str
    size: int
    chunks: int


def chunk_count(size: int, chunk_bytes: int) -> int:
    return max(1, -(-size // chunk_bytes))


def expected_chunk_size(file: DeclaredFile, chunk_no: int, chunk_bytes: int) -> int:
    """Every chunk is ``chunk_bytes`` except the last, which holds the rest."""
    if chunk_no < file.chunks - 1:
        return chunk_bytes
    return file.size - chunk_bytes * (file.chunks - 1)


def declared_files(row: UploadSessionORM) -> list[DeclaredFile]:
    return [
        DeclaredFile(
            index=int(item["index"]),
            role=str(item["role"]),
            filename=str(item["filename"]),
            size=int(item["size"]),
            chunks=int(item["chunks"]),
        )
        for item in row.files
    ]


def chunk_key(tenant_id: str, upload_id: str, file_index: int, chunk_no: int) -> str:
    """A new MinIO key for one send of one chunk, from server-made values only.

    Every send gets its own key and an object is never overwritten: /complete
    reads exactly the objects its chunk rows point to, so a send that was
    refused (session already claimed) cannot change the bytes being joined.
    """
    return f"uploads/{tenant_id}/{upload_id}/{file_index}/{chunk_no:05d}.{secrets.token_hex(8)}"


def aware(value: datetime) -> datetime:
    # SQLite (tests) returns naive datetimes for timezone=True columns.
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


# Fallback for databases without advisory locks (SQLite in tests and local
# runs): one process only, which is all those setups have. Keyed by event loop
# too, because an asyncio.Lock cannot be shared between loops.
_local_owner_locks: dict[tuple[int, str, str], asyncio.Lock] = {}


@asynccontextmanager
async def owner_lock(session: AsyncSession, tenant_id: str, user_id: str) -> AsyncIterator[None]:
    """Serialise "count the user's sessions, evict, open one" per user.

    Without it, concurrent POST /uploads all read the same count and all open a
    session, past the cap. On PostgreSQL this is a transaction-level advisory
    lock, held by every API process until the request commits or rolls back:
    the block must end with the commit. Elsewhere a process-local lock.
    """
    if session.get_bind().dialect.name == "postgresql":
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"upload_session:{tenant_id}:{user_id}"},
        )
        yield
        return
    key = (id(asyncio.get_running_loop()), tenant_id, user_id)
    lock = _local_owner_locks.setdefault(key, asyncio.Lock())
    async with lock:
        yield


class UploadSessionStore:
    """Upload sessions of one tenant, on the request's database session.

    Every change of ``status`` is one conditional UPDATE, so two requests on the
    same session (DELETE and /complete, eviction and a chunk, two /complete)
    cannot both act on what each read earlier: the loser finds 0 rows.
    """

    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def count_open(self, user_id: str) -> int:
        """Sessions of ``user_id`` still accepting chunks and not expired."""
        stmt = select(func.count()).where(
            UploadSessionORM.tenant_id == self._tenant_id,
            UploadSessionORM.user_id == user_id,
            UploadSessionORM.status.in_((OPEN, COMPLETING)),
            UploadSessionORM.expires_at > utcnow(),
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def oldest_open(self, user_id: str, *, limit: int) -> list[UploadSessionORM]:
        """Open sessions of ``user_id`` idle for ``EVICT_IDLE_AFTER``, least recently active first.

        ``updated_at`` moves on every chunk, so an upload still sending (another
        tab, or several dossiers at once) is never returned here.
        """
        now = utcnow()
        stmt = (
            select(UploadSessionORM)
            .where(
                UploadSessionORM.tenant_id == self._tenant_id,
                UploadSessionORM.user_id == user_id,
                UploadSessionORM.status == OPEN,
                UploadSessionORM.expires_at > now,
                UploadSessionORM.updated_at <= now - EVICT_IDLE_AFTER,
            )
            .order_by(UploadSessionORM.updated_at, UploadSessionORM.id)
            .limit(max(limit, 0))
        )
        return list((await self._session.execute(stmt)).scalars())

    async def create(
        self,
        *,
        user_id: str,
        metadata: dict[str, Any],
        files: list[DeclaredFile],
        chunk_bytes: int,
        ttl_seconds: int,
    ) -> UploadSessionORM:
        now = utcnow()
        row = UploadSessionORM(
            id=new_ulid("upl_"),
            tenant_id=self._tenant_id,
            user_id=user_id,
            status=OPEN,
            dossier_metadata=metadata,
            files=[
                {
                    "index": f.index,
                    "role": f.role,
                    "filename": f.filename,
                    "size": f.size,
                    "chunks": f.chunks,
                }
                for f in files
            ],
            chunk_bytes=chunk_bytes,
            created_at=now,
            updated_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get(self, upload_id: str, user_id: str) -> UploadSessionORM | None:
        """The session, only for the user who opened it (others get ``None``, i.e. 404)."""
        stmt = select(UploadSessionORM).where(
            UploadSessionORM.id == upload_id,
            UploadSessionORM.tenant_id == self._tenant_id,
            UploadSessionORM.user_id == user_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_refreshed(self, upload_id: str, user_id: str) -> UploadSessionORM | None:
        """Like ``get`` but re-reads every column, overwriting the identity-map copy.

        Use this after a statement that ran with ``synchronize_session=False`` (e.g.
        ``claim_for_completion``) so that the returned object reflects the current DB
        state instead of the stale cached one.
        """
        stmt = (
            select(UploadSessionORM)
            .where(
                UploadSessionORM.id == upload_id,
                UploadSessionORM.tenant_id == self._tenant_id,
                UploadSessionORM.user_id == user_id,
            )
            .execution_options(populate_existing=True)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def chunks(self, upload_id: str) -> list[UploadChunkORM]:
        stmt = (
            select(UploadChunkORM)
            .where(UploadChunkORM.upload_id == upload_id)
            .order_by(UploadChunkORM.file_index, UploadChunkORM.chunk_no)
        )
        return list((await self._session.execute(stmt)).scalars())

    async def save_chunk(
        self,
        row: UploadSessionORM,
        *,
        file_index: int,
        chunk_no: int,
        size_bytes: int,
        sha256: str,
        object_path: str,
    ) -> str | None:
        """Record one stored chunk; sending the same chunk again replaces it.

        Returns the object of the replaced send (to delete after the commit).
        """
        existing = await self._session.get(UploadChunkORM, (row.id, file_index, chunk_no))
        now = utcnow()
        replaced: str | None = None
        if existing is None:
            self._session.add(
                UploadChunkORM(
                    upload_id=row.id,
                    file_index=file_index,
                    chunk_no=chunk_no,
                    size_bytes=size_bytes,
                    sha256=sha256,
                    object_path=object_path,
                    received_at=now,
                )
            )
        else:
            if existing.object_path != object_path:
                replaced = existing.object_path
            existing.size_bytes = size_bytes
            existing.sha256 = sha256
            existing.object_path = object_path
            existing.received_at = now
        row.updated_at = now
        await self._session.flush()
        return replaced

    async def touch_open(self, upload_id: str) -> bool:
        """Mark the session active, only if it is still ``open``.

        Called before a chunk row is written. On PostgreSQL the UPDATE holds the
        session row until the request commits, so a cancel or a claim that comes
        later waits and then sees the chunk; one that came first makes this
        return False and the chunk is refused.
        """
        result = await self._session.execute(
            update(UploadSessionORM)
            .where(
                UploadSessionORM.id == upload_id,
                UploadSessionORM.tenant_id == self._tenant_id,
                UploadSessionORM.status == OPEN,
            )
            .values(updated_at=utcnow())
            .returning(UploadSessionORM.id)
            .execution_options(synchronize_session=False)
        )
        return result.scalar_one_or_none() is not None

    async def cancel_if_open(
        self, upload_id: str, *, idle_since: datetime | None = None
    ) -> list[str] | None:
        """Cancel the session if it is still ``open``; returns the chunk objects to delete.

        ``idle_since``: only if no chunk arrived after it (eviction). None when
        the session is no longer open (completed, being completed, cancelled)
        or became active: nothing is changed then.
        """
        conditions = [
            UploadSessionORM.id == upload_id,
            UploadSessionORM.tenant_id == self._tenant_id,
            UploadSessionORM.status == OPEN,
        ]
        if idle_since is not None:
            conditions.append(UploadSessionORM.updated_at <= idle_since)
        result = await self._session.execute(
            update(UploadSessionORM)
            .where(*conditions)
            .values(status=CANCELLED, dossier_id=None, job_id=None, updated_at=utcnow())
            .returning(UploadSessionORM.id)
            .execution_options(synchronize_session=False)
        )
        if result.scalar_one_or_none() is None:
            return None
        paths = [chunk.object_path for chunk in await self.chunks(upload_id)]
        await self._session.execute(
            delete(UploadChunkORM).where(UploadChunkORM.upload_id == upload_id)
        )
        await self._session.flush()
        return paths

    async def claim_for_completion(self, upload_id: str) -> bool:
        """Move ``open`` (or a stale ``completing``) → ``completing`` atomically.

        False when another request holds it: only one dossier per session.
        """
        now = utcnow()
        result = await self._session.execute(
            update(UploadSessionORM)
            .where(
                UploadSessionORM.id == upload_id,
                UploadSessionORM.tenant_id == self._tenant_id,
                or_(
                    UploadSessionORM.status == OPEN,
                    and_(
                        UploadSessionORM.status == COMPLETING,
                        UploadSessionORM.updated_at <= now - COMPLETING_STALE_AFTER,
                    ),
                ),
            )
            .values(status=COMPLETING, updated_at=now)
            .returning(UploadSessionORM.id)
            .execution_options(synchronize_session=False)
        )
        return result.scalar_one_or_none() is not None

    async def reopen(self, upload_id: str) -> None:
        """Building the dossier failed: let the client fix it and complete again."""
        await self._session.execute(
            update(UploadSessionORM)
            .where(
                UploadSessionORM.id == upload_id,
                UploadSessionORM.tenant_id == self._tenant_id,
                UploadSessionORM.status == COMPLETING,
            )
            .values(status=OPEN, updated_at=utcnow())
        )

    async def finish(
        self, row: UploadSessionORM, *, status: str, dossier_id: str | None, job_id: str | None
    ) -> list[str]:
        """Close the session and drop its chunk rows; returns the chunk objects to delete.

        The session row stays until it expires, so a repeated /complete still
        answers with the same dossier.
        """
        paths = [chunk.object_path for chunk in await self.chunks(row.id)]
        await self._session.execute(
            delete(UploadChunkORM).where(UploadChunkORM.upload_id == row.id)
        )
        row.status = status
        row.dossier_id = dossier_id
        row.job_id = job_id
        row.updated_at = utcnow()
        await self._session.flush()
        return paths


async def sweep_expired_sessions(session: AsyncSession, *, limit: int = 200) -> list[str]:
    """Delete sessions that are over (any tenant); returns their chunk objects.

    - ``open`` and ``cancelled`` past ``expires_at``;
    - ``completing`` past ``expires_at`` **and** stale (no progress for
      ``COMPLETING_STALE_AFTER``): the request that held it died, and nobody
      came back to complete it. A live one is never touched;
    - ``completed`` rows ``COMPLETED_KEEP`` after they were opened (their chunks
      were deleted at completion). Until then a repeated /complete still
      returns the dossier.

    Commits. The caller deletes the returned MinIO objects afterwards: an object
    left behind by a failed delete is only storage, never reachable again.
    """
    now = utcnow()
    expired = list(
        (
            await session.execute(
                select(UploadSessionORM.id)
                .where(
                    or_(
                        and_(
                            UploadSessionORM.expires_at <= now,
                            UploadSessionORM.status.in_((OPEN, CANCELLED)),
                        ),
                        and_(
                            UploadSessionORM.expires_at <= now,
                            UploadSessionORM.status == COMPLETING,
                            UploadSessionORM.updated_at <= now - COMPLETING_STALE_AFTER,
                        ),
                        and_(
                            UploadSessionORM.status == COMPLETED,
                            UploadSessionORM.created_at <= now - COMPLETED_KEEP,
                        ),
                    )
                )
                .order_by(UploadSessionORM.expires_at)
                .limit(limit)
            )
        ).scalars()
    )
    if not expired:
        return []
    paths = list(
        (
            await session.execute(
                select(UploadChunkORM.object_path).where(UploadChunkORM.upload_id.in_(expired))
            )
        ).scalars()
    )
    await session.execute(delete(UploadChunkORM).where(UploadChunkORM.upload_id.in_(expired)))
    await session.execute(delete(UploadSessionORM).where(UploadSessionORM.id.in_(expired)))
    await session.commit()
    logger.info("upload.sessions.expired_removed", sessions=len(expired), chunks=len(paths))
    return paths


def stale_completing(row: UploadSessionORM) -> bool:
    return row.status == COMPLETING and aware(row.updated_at) <= utcnow() - COMPLETING_STALE_AFTER


async def delete_objects_quietly(paths: list[str]) -> None:
    """Best-effort delete of chunk objects. A leftover only costs storage: no row points at it."""
    from contract_intelligence.infrastructure import storage

    for path in paths:
        try:
            await storage.delete_object(path)
        except Exception:
            logger.warning("upload.chunk.delete_failed", object_path=path, exc_info=True)


async def run_expired_session_sweep() -> int:
    """Maintenance loop: remove expired sessions of every tenant, then their objects."""
    from contract_intelligence.shared.persistence.session import get_session_factory

    async with get_session_factory()() as session:
        paths = await sweep_expired_sessions(session)
    await delete_objects_quietly(paths)
    return len(paths)


__all__ = [
    "CANCELLED",
    "COMPLETED",
    "COMPLETED_KEEP",
    "COMPLETING",
    "EVICT_IDLE_AFTER",
    "OPEN",
    "DeclaredFile",
    "UploadChunkORM",
    "UploadSessionORM",
    "UploadSessionStore",
    "aware",
    "delete_objects_quietly",
    "run_expired_session_sweep",
    "stale_completing",
    "chunk_count",
    "chunk_key",
    "declared_files",
    "expected_chunk_size",
    "owner_lock",
    "sweep_expired_sessions",
]
