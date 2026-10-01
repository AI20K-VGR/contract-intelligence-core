"""Dossier list on PostgreSQL hides expired and disabled share grants.

The list filter has separate SQL for PostgreSQL (json_array_elements); sqlite
tests cannot reach it. Skipped unless ``CI_TEST_POSTGRES_URL`` points at a
disposable database (see test_postgres_invariants.py).
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM
from contract_intelligence.contract.infrastructure.persistence.repository_impl import (
    DossierRepositoryImpl,
)

PG_URL = os.environ.get("CI_TEST_POSTGRES_URL", "")
TENANT = "tenant-pg-share"
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
        tables = (
            await connection.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
                )
            )
        ).scalars()
        await connection.execute(text(f"TRUNCATE {', '.join(tables)} CASCADE"))
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


def _iso(delta: timedelta) -> str:
    return (datetime.now(tz=UTC) + delta).isoformat(timespec="seconds")


async def test_list_applies_expiry_and_status_on_postgres(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    grants: dict[str, dict[str, Any]] = {
        "dos_live": {"permission": "read", "expires_at": _iso(timedelta(days=1))},
        "dos_forever": {"permission": "edit"},
        "dos_by_email": {"email": "GUEST@test.vn"},
        "dos_expired": {"permission": "edit", "expires_at": _iso(-timedelta(minutes=1))},
        "dos_disabled": {"permission": "edit", "status": "disabled"},
        "dos_mine": {},
    }
    async with factory() as session:
        for dossier_id, grant in grants.items():
            shared = [] if dossier_id == "dos_mine" else [{"id": "guest", **grant}]
            if dossier_id == "dos_by_email":
                shared = [grant]
            session.add(
                DossierORM(
                    id=dossier_id,
                    tenant_id=TENANT,
                    name=dossier_id,
                    metadata_json={
                        "created_by": "owner",
                        "access_scope": "mine" if dossier_id == "dos_mine" else "shared_out",
                        "shared_with": shared,
                    },
                )
            )
        await session.commit()

    async with factory() as session:
        page = await DossierRepositoryImpl(session, TENANT).list(
            viewer_id="guest", viewer_email="guest@test.vn"
        )
    assert sorted(d.id for d in page.items) == ["dos_by_email", "dos_forever", "dos_live"]
