"""Chunked upload sessions on a real Postgres (issue #145).

SQLite serialises every write, so it cannot show that two concurrent
``/complete`` calls race for the same session. Here two connections claim the
same session at once and exactly one wins, on the schema from
``alembic upgrade head`` (v26). Skipped unless ``CI_TEST_POSTGRES_URL`` is set
(see test_postgres_invariants.py).
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncGenerator
from datetime import timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from contract_intelligence.contract.infrastructure.persistence.upload_session_store import (
    CANCELLED,
    COMPLETING,
    OPEN,
    DeclaredFile,
    UploadChunkORM,
    UploadSessionORM,
    UploadSessionStore,
    owner_lock,
    sweep_expired_sessions,
)
from contract_intelligence.shared.base import utcnow

PG_URL = os.environ.get("CI_TEST_POSTGRES_URL", "")
TENANT_ID = "tenant-pg"
USER_ID = "usr-pg"
BACKEND_DIR = Path(__file__).resolve().parents[2]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not PG_URL, reason="CI_TEST_POSTGRES_URL not set"),
]


@pytest.fixture(scope="module")
def migrated() -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": PG_URL},
        check=True,
    )


@pytest_asyncio.fixture
async def factory(migrated: None) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    engine = create_async_engine(PG_URL)
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE upload_session, upload_session_chunk CASCADE"))
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


async def _open_session(factory: async_sessionmaker[AsyncSession]) -> str:
    async with factory() as session:
        row = await UploadSessionStore(session, TENANT_ID).create(
            user_id=USER_ID,
            metadata={"name": "pg"},
            files=[DeclaredFile(index=0, role="contract", filename="c.pdf", size=10, chunks=1)],
            chunk_bytes=1024,
            ttl_seconds=3600,
        )
        await session.commit()
        return row.id


@pytest.mark.asyncio
async def test_two_concurrent_completes_claim_the_session_once(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    upload_id = await _open_session(factory)

    async def claim() -> bool:
        async with factory() as session:
            won = await UploadSessionStore(session, TENANT_ID).claim_for_completion(upload_id)
            await asyncio.sleep(0.2)  # hold the row while the other claim waits
            await session.commit()
            return won

    results = await asyncio.gather(*(claim() for _ in range(5)))
    assert sorted(results) == [False, False, False, False, True]
    async with factory() as session:
        status = (
            await session.execute(
                select(UploadSessionORM.status).where(UploadSessionORM.id == upload_id)
            )
        ).scalar_one()
    assert status == COMPLETING


@pytest.mark.asyncio
async def test_reopen_after_a_failed_build_lets_a_later_complete_claim_again(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    upload_id = await _open_session(factory)
    async with factory() as session:
        store = UploadSessionStore(session, TENANT_ID)
        assert await store.claim_for_completion(upload_id)
        await store.reopen(upload_id)
        await session.commit()
        row = await store.get(upload_id, USER_ID)
        assert row is not None
        await session.refresh(row)
        assert row.status == OPEN
        assert await store.claim_for_completion(upload_id)


@pytest.mark.asyncio
async def test_status_check_and_chunk_key_hold_in_the_schema(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    upload_id = await _open_session(factory)
    async with factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                text("UPDATE upload_session SET status = 'bogus' WHERE id = :id"), {"id": upload_id}
            )
        await session.rollback()

    async with factory() as session:
        for _ in range(2):
            session.add(
                UploadChunkORM(
                    upload_id=upload_id,
                    file_index=0,
                    chunk_no=0,
                    size_bytes=10,
                    sha256="0" * 64,
                    object_path="s3://dossiers/x",
                    received_at=utcnow(),
                )
            )
        with pytest.raises(IntegrityError):
            await session.flush()


@pytest.mark.asyncio
async def test_sweep_removes_expired_sessions_of_every_tenant_and_cascades_chunks(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    upload_id = await _open_session(factory)
    async with factory() as session:
        session.add(
            UploadChunkORM(
                upload_id=upload_id,
                file_index=0,
                chunk_no=0,
                size_bytes=10,
                sha256="0" * 64,
                object_path="s3://dossiers/uploads/x/0/00000",
                received_at=utcnow(),
            )
        )
        row = await session.get(UploadSessionORM, upload_id)
        assert row is not None
        row.expires_at = utcnow() - timedelta(seconds=1)
        await session.commit()

    async with factory() as session:
        paths = await sweep_expired_sessions(session)
    assert paths == ["s3://dossiers/uploads/x/0/00000"]
    async with factory() as session:
        assert (await session.execute(select(UploadSessionORM))).first() is None
        assert (await session.execute(select(UploadChunkORM))).first() is None


@pytest.mark.asyncio
async def test_concurrent_opens_by_one_user_stay_within_the_cap(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """Count -> create under owner_lock, as POST /uploads does, from 5 connections at once."""

    async def open_one() -> bool:
        async with factory() as session:
            store = UploadSessionStore(session, TENANT_ID)
            async with owner_lock(session, TENANT_ID, USER_ID):
                count = await store.count_open(USER_ID)
                await asyncio.sleep(0.1)  # without the lock every request reads 0 here
                if count >= 3:
                    await session.rollback()
                    return False
                await store.create(
                    user_id=USER_ID,
                    metadata={"name": "pg"},
                    files=[
                        DeclaredFile(index=0, role="contract", filename="c.pdf", size=10, chunks=1)
                    ],
                    chunk_bytes=1024,
                    ttl_seconds=3600,
                )
                await session.commit()
                return True

    results = await asyncio.gather(*(open_one() for _ in range(5)))
    assert sorted(results) == [False, False, True, True, True]
    async with factory() as session:
        assert await UploadSessionStore(session, TENANT_ID).count_open(USER_ID) == 3
        # Another user is not held by this user's lock.
        async with owner_lock(session, TENANT_ID, "usr-other"):
            pass


@pytest.mark.asyncio
async def test_cancel_and_complete_at_once_one_wins_and_the_other_changes_nothing(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    for _ in range(5):
        upload_id = await _open_session(factory)

        async def claim(upload_id: str = upload_id) -> bool:
            async with factory() as session:
                won = await UploadSessionStore(session, TENANT_ID).claim_for_completion(upload_id)
                await asyncio.sleep(0.05)
                await session.commit()
                return won

        async def cancel(upload_id: str = upload_id) -> bool:
            async with factory() as session:
                paths = await UploadSessionStore(session, TENANT_ID).cancel_if_open(upload_id)
                await asyncio.sleep(0.05)
                await session.commit()
                return paths is not None

        claimed, cancelled = await asyncio.gather(claim(), cancel())
        assert claimed != cancelled
        async with factory() as session:
            status = (
                await session.execute(
                    select(UploadSessionORM.status).where(UploadSessionORM.id == upload_id)
                )
            ).scalar_one()
        assert status == (COMPLETING if claimed else CANCELLED)


@pytest.mark.asyncio
async def test_a_chunk_written_while_cancelling_is_deleted_with_the_session(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """PUT holds the session row (touch_open) until it commits; the cancel waits for it."""
    upload_id = await _open_session(factory)
    async with factory() as put_session:
        put_store = UploadSessionStore(put_session, TENANT_ID)
        assert await put_store.touch_open(upload_id)

        async def cancel() -> list[str] | None:
            async with factory() as session:
                paths = await UploadSessionStore(session, TENANT_ID).cancel_if_open(upload_id)
                await session.commit()
                return paths

        cancelling = asyncio.create_task(cancel())
        await asyncio.sleep(0.2)
        assert not cancelling.done()  # blocked on the row the PUT holds
        put_session.add(
            UploadChunkORM(
                upload_id=upload_id,
                file_index=0,
                chunk_no=0,
                size_bytes=10,
                sha256="0" * 64,
                object_path="s3://dossiers/uploads/late/0/00000",
                received_at=utcnow(),
            )
        )
        await put_session.commit()

    assert await cancelling == ["s3://dossiers/uploads/late/0/00000"]
    async with factory() as session:
        assert (await session.execute(select(UploadChunkORM))).first() is None
        # And a chunk after the cancel is refused.
        assert not await UploadSessionStore(session, TENANT_ID).touch_open(upload_id)
