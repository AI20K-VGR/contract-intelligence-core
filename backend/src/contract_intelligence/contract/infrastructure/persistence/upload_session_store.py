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
    """MinIO key from server-made values only (never the client's file name)."""
    return f"uploads/{tenant_id}/{upload_id}/{file_index}/{chunk_no:05d}"


def aware(value: datetime) -> datetime:
    # SQLite (tests) returns naive datetimes for timezone=True columns.
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class UploadSessionStore:
    """Upload sessions of one tenant, on the request's database session."""

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
        """Up to ``limit`` of the user's ``open`` (not completing) sessions, least-recently active first.

        Ordering by ``updated_at`` avoids evicting a session that is still sending
        chunks (the user's other tabs may be uploading in parallel).  A session that
        received a chunk most recently stays alive; one that has been idle the
        longest is evicted to make room.
        """
        stmt = (
            select(UploadSessionORM)
            .where(
                UploadSessionORM.tenant_id == self._tenant_id,
                UploadSessionORM.user_id == user_id,
                UploadSessionORM.status == OPEN,
                UploadSessionORM.expires_at > utcnow(),
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
    ) -> None:
        """Record one stored chunk; sending the same chunk again replaces it."""
        existing = await self._session.get(UploadChunkORM, (row.id, file_index, chunk_no))
        now = utcnow()
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
            existing.size_bytes = size_bytes
            existing.sha256 = sha256
            existing.object_path = object_path
            existing.received_at = now
        row.updated_at = now
        await self._session.flush()

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
    """Delete expired ``open`` and ``cancelled`` sessions (any tenant); returns their chunk objects.

    Commits. The caller deletes the returned MinIO objects afterwards: an object
    left behind by a failed delete is only storage, never reachable again.

    ``completed`` sessions are kept (repeated /complete must still return the
    dossier).  ``completing`` sessions are excluded: the claim timeout
    (``COMPLETING_STALE_AFTER``) lets another request take over a dead one.
    """
    now = utcnow()
    expired = list(
        (
            await session.execute(
                select(UploadSessionORM.id)
                .where(
                    UploadSessionORM.expires_at <= now,
                    UploadSessionORM.status.in_((OPEN, CANCELLED)),
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
    "COMPLETING",
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
    "sweep_expired_sessions",
]
