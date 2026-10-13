"""Filtering findings by the conflict kinds AI2 persists on FindingORM.disposition."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from contract_intelligence.conflict.infrastructure.persistence.orm import FindingORM
from contract_intelligence.conflict.infrastructure.persistence.repository_impl import (
    FindingRepositoryImpl,
)
from contract_intelligence.shared.persistence import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models

TENANT_ID = "tenant-filter"
DOSSIER_ID = "dossier-filter"
DISPOSITIONS = ("conflict_candidate", "arithmetic_inconsistency", "amendment_review")


@pytest_asyncio.fixture
async def factory(tmp_path: Path) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    import_all_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'filter.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        for index, disposition in enumerate(DISPOSITIONS):
            session.add(
                FindingORM(
                    id=f"finding-{index}",
                    tenant_id=TENANT_ID,
                    dossier_id=DOSSIER_ID,
                    finding_type="semantic",
                    scope="contract_annex",
                    key_or_topic="payment",
                    disposition=disposition,
                    severity="high",
                    confidence=0.9,
                    method="CLOSED_SYMBOL",
                )
            )
        await session.commit()
    yield session_factory
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        ("conflict_candidate", "conflict_candidate"),
        ("arithmetic_inconsistency", "arithmetic_inconsistency"),
        ("amendment_review", "amendment_review"),
        ("ARITHMETIC_INCONSISTENCY", "arithmetic_inconsistency"),
        ("AMENDMENT_REVIEW", "amendment_review"),
    ],
)
async def test_conflict_kind_filters_match_the_persisted_disposition(
    factory: async_sessionmaker[AsyncSession], requested: str, expected: str
) -> None:
    async with factory() as session:
        rows, total = await FindingRepositoryImpl(session, TENANT_ID).list_by_dossier(
            DOSSIER_ID, disposition=requested
        )

    assert total == 1
    assert [row["disposition"] for row in rows] == [expected]
