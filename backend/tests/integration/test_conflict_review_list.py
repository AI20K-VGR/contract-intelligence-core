"""``list_conflicts_for_review``: filter and page in SQL, enrich only the page."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from contract_intelligence.conflict.infrastructure.persistence.orm import (
    FindingORM,
    FindingSideORM,
)
from contract_intelligence.conflict.infrastructure.persistence.repository_impl import (
    FindingRepositoryImpl,
)
from contract_intelligence.contract.infrastructure.persistence.orm import JobORM
from contract_intelligence.shared.persistence import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models

pytestmark = pytest.mark.asyncio

TENANT_ID = "tenant-review-list"
DOSSIER_ID = "dossier-review-list"
_T0 = datetime(2026, 10, 1, tzinfo=UTC)


def _finding(
    finding_id: str,
    *,
    run_id: str | None,
    minute: int,
    disposition: str = "duplicate",
    confidence: str = "0.9",
) -> FindingORM:
    return FindingORM(
        id=finding_id,
        tenant_id=TENANT_ID,
        dossier_id=DOSSIER_ID,
        run_id=run_id,
        finding_type="semantic",
        scope="contract_annex",
        key_or_topic="payment",
        disposition=disposition,
        severity="medium",
        confidence=confidence,
        method="ai2.canonical",
        created_at=_T0 + timedelta(minutes=minute),
    )


def _side(finding_id: str, *, review_state: str | None = None) -> FindingSideORM:
    snapshot: dict[str, Any] = {"text": "..."}
    if review_state is not None:
        snapshot["semantic"] = {
            "pair": {"disposition": "DUPLICATE", "reason": "r", "review_state": review_state},
            "profile_digest": "p",
            "alias_version": "1",
            "alias_digest": "a",
        }
    return FindingSideORM(
        id=f"{finding_id}-a",
        tenant_id=TENANT_ID,
        finding_id=finding_id,
        side="a",
        document_id="doc-contract",
        value_snapshot=json.dumps(snapshot),
    )


@pytest_asyncio.fixture
async def factory(tmp_path: Path) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    import_all_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'review-list.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        session.add_all(
            [
                # Older run: hidden whatever its disposition.
                _finding(
                    "old-conflict", run_id="run-1", minute=0, disposition="conflict_candidate"
                ),
                # Current run.
                _finding(
                    "by-disposition", run_id="run-2", minute=10, disposition="conflict_candidate"
                ),
                _finding("by-confidence", run_id="run-2", minute=11, confidence="0.55"),
                _finding("by-semantic", run_id="run-2", minute=12),
                _finding("semantic-ok", run_id="run-2", minute=13),
                _finding("plain", run_id="run-2", minute=14),
                _finding("at-threshold", run_id="run-2", minute=15, confidence="0.6"),
                _side("by-disposition"),
                _side("by-semantic", review_state="NEEDS_REVIEW"),
                _side("semantic-ok", review_state="AUTO_ACCEPTED"),
            ]
        )
        await session.commit()
    yield session_factory
    await engine.dispose()


async def _list(
    factory: async_sessionmaker[AsyncSession], *, limit: int = 50, offset: int = 0
) -> tuple[list[dict[str, Any]], int]:
    async with factory() as session:
        return await FindingRepositoryImpl(session, TENANT_ID).list_conflicts_for_review(
            DOSSIER_ID, limit=limit, offset=offset
        )


async def test_latest_run_findings_needing_review_newest_first(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    rows, total = await _list(factory)

    assert total == 3
    assert [row["id"] for row in rows] == ["by-semantic", "by-confidence", "by-disposition"]
    assert rows[0]["semantic"]["review_state"] == "NEEDS_REVIEW"
    assert [side["side"] for side in rows[2]["sides"]] == ["a"]


async def test_pages_keep_the_total_of_every_match(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    first, total_first = await _list(factory, limit=2)
    rest, total_rest = await _list(factory, limit=2, offset=2)
    beyond, total_beyond = await _list(factory, limit=2, offset=10)

    assert [row["id"] for row in first] == ["by-semantic", "by-confidence"]
    assert [row["id"] for row in rest] == ["by-disposition"]
    assert beyond == []
    assert total_first == total_rest == total_beyond == 3


async def test_job_run_wins_over_the_newest_finding(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as session:
        session.add(
            JobORM(id="job-1", tenant_id=TENANT_ID, dossier_id=DOSSIER_ID, current_run_id="run-1")
        )
        await session.commit()

    rows, total = await _list(factory)

    assert total == 1
    assert [row["id"] for row in rows] == ["old-conflict"]


async def test_job_without_a_run_lists_nothing(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as session:
        session.add(JobORM(id="job-1", tenant_id=TENANT_ID, dossier_id=DOSSIER_ID))
        await session.commit()

    assert await _list(factory) == ([], 0)
