"""The ai2 role reaches schema ai2 only (ADR-14, issue #52).

Runs ``ensure_ai2_role`` on a migrated Postgres, then connects as ``ai2``: it
can build tables (with pgvector columns) in its schema but cannot read or write
business tables, create objects in ``public`` or run the backend's SECURITY
DEFINER purge. Skipped unless ``CI_TEST_POSTGRES_URL`` points at a disposable
database on an image with pgvector (see test_postgres_invariants.py).
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import make_url, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from contract_intelligence.infrastructure.ai2_db_role import ensure_ai2_role

PG_URL = os.environ.get("CI_TEST_POSTGRES_URL", "")
BACKEND_DIR = Path(__file__).resolve().parents[2]
PASSWORD = "ai2_test_password"

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


async def _ensure(password: str) -> None:
    engine = create_async_engine(PG_URL)
    try:
        async with engine.begin() as connection:
            await ensure_ai2_role(connection, password)
    finally:
        await engine.dispose()


def _ai2_engine(password: str = PASSWORD) -> AsyncEngine:
    url = make_url(PG_URL).set(username="ai2", password=password)
    return create_async_engine(url)


@pytest_asyncio.fixture
async def ai2(migrated: None) -> AsyncGenerator[AsyncEngine, None]:
    await _ensure(PASSWORD)
    engine = _ai2_engine()
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text("DROP TABLE IF EXISTS ai2.probe_vector"))
    await engine.dispose()


async def _denied(engine: AsyncEngine, statement: str) -> None:
    with pytest.raises(DBAPIError, match="permission denied"):
        async with engine.begin() as connection:
            await connection.execute(text(statement))


async def test_ai2_owns_its_schema_with_pgvector(ai2: AsyncEngine) -> None:
    async with ai2.begin() as connection:
        # search_path puts unqualified tables in ai2; vector resolves from public.
        await connection.execute(text("CREATE TABLE probe_vector (id int, v vector(3))"))
        await connection.execute(text("INSERT INTO probe_vector VALUES (1, '[1,2,3]')"))
        schema = (
            await connection.execute(
                text("SELECT schemaname FROM pg_tables WHERE tablename = 'probe_vector'")
            )
        ).scalar_one()
        distance = (
            await connection.execute(text("SELECT v <-> '[1,2,4]' FROM probe_vector"))
        ).scalar_one()
    assert schema == "ai2"
    assert distance == 1.0


async def test_ai2_cannot_touch_business_tables(ai2: AsyncEngine) -> None:
    await _denied(ai2, "SELECT 1 FROM dossier LIMIT 1")
    await _denied(ai2, "SELECT 1 FROM public.alembic_version")
    await _denied(ai2, "DELETE FROM public.dossier")
    await _denied(ai2, "CREATE TABLE public.ai2_probe (id int)")


async def test_ai2_cannot_run_the_security_definer_purge(ai2: AsyncEngine) -> None:
    await _denied(ai2, "SELECT purge_dossier_contract_content('dos_missing')")


async def test_ai2_takes_over_tables_the_backend_role_created(migrated: None) -> None:
    # Before the ai2 role existed, AI2 ran its migrations over the backend's
    # connection, so schema ai2 already holds tables owned by that role.
    backend = create_async_engine(PG_URL)
    try:
        async with backend.begin() as connection:
            await connection.execute(text("CREATE SCHEMA IF NOT EXISTS ai2"))
            await connection.execute(
                text("CREATE TABLE ai2.legacy_version (id serial PRIMARY KEY, num text)")
            )
            await connection.execute(text("INSERT INTO ai2.legacy_version (num) VALUES ('a1')"))
        await _ensure(PASSWORD)
        ai2 = _ai2_engine()
        try:
            async with ai2.begin() as connection:
                await connection.execute(text("INSERT INTO legacy_version (num) VALUES ('a2')"))
                count = await connection.execute(text("SELECT count(*) FROM legacy_version"))
                rows = count.scalar_one()
        finally:
            await ai2.dispose()
        assert rows == 2
    finally:
        async with backend.begin() as connection:
            await connection.execute(text("DROP TABLE IF EXISTS ai2.legacy_version"))
        await backend.dispose()


async def test_ai2_role_is_idempotent_and_follows_the_password(ai2: AsyncEngine) -> None:
    await _ensure("ai2_rotated_password")
    rotated = _ai2_engine("ai2_rotated_password")
    try:
        async with rotated.connect() as connection:
            assert (await connection.execute(text("SELECT current_user"))).scalar_one() == "ai2"
    finally:
        await rotated.dispose()
        await _ensure(PASSWORD)
