"""Postgres-only invariants: row locks, the review unique index, append-only triggers.

SQLite has no FOR UPDATE / FOR SHARE and no triggers from the migrations, so these
run against a real Postgres migrated with ``alembic upgrade head``. Skipped unless
``CI_TEST_POSTGRES_URL`` points at a disposable database, e.g.::

    docker run -d --rm --name ci-pg-test -e POSTGRES_USER=ci -e POSTGRES_PASSWORD=ci \
        -e POSTGRES_DB=ci_test -p 55432:5432 postgres:16-alpine
    $env:CI_TEST_POSTGRES_URL="postgresql+asyncpg://ci:ci@127.0.0.1:55432/ci_test"
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM, JobORM
from contract_intelligence.extraction.infrastructure.persistence.orm import PipelineRunORM
from contract_intelligence.review.domain.entities.review_action import ReviewActionType
from contract_intelligence.review.infrastructure.persistence.orm import (
    ReviewActionORM,
    ReviewItemORM,
)
from contract_intelligence.review.infrastructure.persistence.repository_impl import (
    ReviewRepositoryImpl,
    _is_base_version_race,
)
from contract_intelligence.shared.audit import AuditEventORM, add_audit_event
from contract_intelligence.shared.base import utcnow
from contract_intelligence.shared.exceptions import InvariantViolation, ReviewVersionConflict
from contract_intelligence.shared.query_policy import QueryTraceORM

PG_URL = os.environ.get("CI_TEST_POSTGRES_URL", "")
TENANT_ID = "tenant-pg"
DOSSIER_ID = "dossier-pg"
JOB_ID = "job-pg"
RUN_ID = "run-pg"
ITEM_ID = "ri_pg"
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
        # TRUNCATE does not fire the row-level append-only triggers.
        await connection.execute(text(f"TRUNCATE {', '.join(tables)} CASCADE"))
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        session.add(DossierORM(id=DOSSIER_ID, tenant_id=TENANT_ID, name="pg invariants"))
        await session.flush()
        session.add(JobORM(id=JOB_ID, tenant_id=TENANT_ID, dossier_id=DOSSIER_ID))
        await session.flush()
        session.add(
            PipelineRunORM(
                id=RUN_ID,
                tenant_id=TENANT_ID,
                job_id=JOB_ID,
                dossier_id=DOSSIER_ID,
                status="running",
                pipeline_version="test-v1",
            )
        )
        await session.flush()
        session.add(
            ReviewItemORM(
                id=ITEM_ID,
                tenant_id=TENANT_ID,
                dossier_id=DOSSIER_ID,
                run_id=RUN_ID,
                target_type="finding",
                target_id="finding-1",
                reason="conflict",
                priority="P1",
                status="open",
                version=1,
            )
        )
        await session.commit()
    yield session_factory
    await engine.dispose()


async def _submit(session: AsyncSession, reviewer: str) -> dict[str, object]:
    return await ReviewRepositoryImpl(session, TENANT_ID).submit_action(
        item_id=ITEM_ID,
        action_type=ReviewActionType.CONFIRM,
        base_version=1,
        reviewer_id=reviewer,
    )


async def test_concurrent_actions_on_same_version_serialize(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as first, factory() as second:
        await _submit(first, "reviewer-a")
        loser = asyncio.create_task(_submit(second, "reviewer-b"))
        await asyncio.sleep(0.5)
        assert not loser.done(), "item row lock must block the second reviewer"

        await first.commit()
        with pytest.raises(ReviewVersionConflict) as conflict:
            await loser
        await second.rollback()

    assert conflict.value.details["current_version"] == 2
    async with factory() as session:
        actions = list((await session.execute(select(ReviewActionORM))).scalars())
        item = await session.get(ReviewItemORM, ITEM_ID)
    assert [a.reviewer_id for a in actions] == ["reviewer-a"]
    assert item is not None and item.version == 2


async def test_approval_holding_dossier_blocks_then_refuses_action(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as approver, factory() as reviewer:
        dossier = (
            await approver.execute(
                select(DossierORM).where(DossierORM.id == DOSSIER_ID).with_for_update()
            )
        ).scalar_one()
        action = asyncio.create_task(_submit(reviewer, "reviewer-a"))
        await asyncio.sleep(0.5)
        assert not action.done(), "dossier FOR UPDATE must block the FOR SHARE in submit"

        dossier.is_approved = True
        await approver.commit()
        with pytest.raises(InvariantViolation):
            await action
        await reviewer.rollback()

    async with factory() as session:
        assert list((await session.execute(select(ReviewActionORM))).scalars()) == []


async def test_unique_index_rejects_duplicate_base_version(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    def action(action_id: str) -> ReviewActionORM:
        return ReviewActionORM(
            id=action_id,
            tenant_id=TENANT_ID,
            review_item_id=ITEM_ID,
            target_type="finding",
            target_id="finding-1",
            action="confirm",
            base_version=1,
            reviewer_id="reviewer-a",
        )

    async with factory() as session:
        session.add(action("ra_1"))
        await session.commit()
        session.add(action("ra_2"))
        with pytest.raises(IntegrityError) as exc:
            await session.commit()
    assert _is_base_version_race(exc.value)


async def _seed_append_only_rows(session: AsyncSession) -> None:
    add_audit_event(
        session,
        tenant_id=TENANT_ID,
        action="test.event",
        entity_type="dossier",
        entity_id=DOSSIER_ID,
    )
    session.add(
        QueryTraceORM(
            id="qt_1",
            tenant_id=TENANT_ID,
            dossier_id=DOSSIER_ID,
            actor_id="reviewer-a",
            endpoint="ask",
            query="q",
            snapshot_version="v1",
            query_contract_version="v1",
            acl_decision="allow",
            created_at=utcnow(),
        )
    )
    await _submit(session, "reviewer-a")
    await session.commit()


@pytest.mark.parametrize("table", ["audit_event", "query_trace", "review_action"])
@pytest.mark.parametrize("statement", ["UPDATE {table} SET tenant_id = 'x'", "DELETE FROM {table}"])
async def test_append_only_tables_refuse_update_and_delete(
    factory: async_sessionmaker[AsyncSession], table: str, statement: str
) -> None:
    async with factory() as session:
        await _seed_append_only_rows(session)

    async with factory() as session:
        with pytest.raises(DBAPIError, match="append-only"):
            await session.execute(text(statement.format(table=table)))
        await session.rollback()

    async with factory() as session:
        for orm in (AuditEventORM, QueryTraceORM, ReviewActionORM):
            rows = list((await session.execute(select(orm))).scalars())
            assert rows and all(row.tenant_id == TENANT_ID for row in rows)
