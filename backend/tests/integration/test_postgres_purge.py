"""Dossier purge on PostgreSQL (the SQL function path sqlite cannot reach).

- a dossier with several documents purges (sha256 marker unique per document)
- saved Q&A answers are removed, the append-only query trace stays
Skipped unless ``CI_TEST_POSTGRES_URL`` points at a disposable database.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.unit.conftest_contract import FakeFileStorage

from contract_intelligence.contract.infrastructure.persistence.dossier_deletion_service import (
    DossierDeletionService,
)
from contract_intelligence.contract.infrastructure.persistence.orm import (
    DocumentORM,
    DossierORM,
    JobORM,
)
from contract_intelligence.shared.ai.client import StubAiServiceClient
from contract_intelligence.shared.query_history import QueryAnswerORM
from contract_intelligence.shared.query_policy import QueryTraceORM, save_query_trace

PG_URL = os.environ.get("CI_TEST_POSTGRES_URL", "")
TENANT = "tenant-pg-purge"
DOSSIER = "dossier-pg-purge"
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


async def test_purges_a_dossier_with_two_documents_and_its_answers(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as session:
        session.add(DossierORM(id=DOSSIER, tenant_id=TENANT, name="Hợp đồng + phụ lục"))
        await session.flush()
        session.add(JobORM(id="job-pg-purge", tenant_id=TENANT, dossier_id=DOSSIER))
        for index, role in enumerate(("contract", "annex")):
            session.add(
                DocumentORM(
                    id=f"doc-pg-purge-{index}",
                    tenant_id=TENANT,
                    dossier_id=DOSSIER,
                    role=role,
                    order_index=index,
                    filename=f"{role}.pdf",
                    sha256=str(index) * 64,
                )
            )
        trace = await save_query_trace(
            session,
            tenant_id=TENANT,
            dossier_id=DOSSIER,
            actor_id="owner",
            endpoint="ask",
            query="Giá trị hợp đồng?",
            snapshot_version="latest",
            snapshot_digest=None,
            query_contract_version="ai2.query.v1",
            state="PASS",
            citations=[],
            acl=None,
        )
        session.add(
            QueryAnswerORM(
                trace_id=trace.id,
                tenant_id=TENANT,
                dossier_id=DOSSIER,
                actor_id="owner",
                answer="1.286.400.000 đồng",
            )
        )
        await session.commit()

    async with factory() as session:
        service = DossierDeletionService(
            session=session,
            storage=FakeFileStorage(),
            ai_client=StubAiServiceClient(),
            tenant_id=TENANT,
        )
        await service.tombstone(DOSSIER, actor_user_id="owner")
        await session.commit()
        await service.purge(DOSSIER)
        await session.commit()

    async with factory() as session:
        dossier = await session.get(DossierORM, DOSSIER)
        shas = (
            await session.scalars(
                select(DocumentORM.sha256).where(DocumentORM.dossier_id == DOSSIER)
            )
        ).all()
        answers = await session.scalar(select(func.count()).select_from(QueryAnswerORM))
        traces = await session.scalar(select(func.count()).select_from(QueryTraceORM))
    assert dossier is not None and dossier.purge_status == "completed"
    assert sorted(shas) == ["[purged]:doc-pg-purge-0", "[purged]:doc-pg-purge-1"]
    assert answers == 0
    assert traces == 1
