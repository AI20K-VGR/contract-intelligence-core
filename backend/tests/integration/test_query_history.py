"""Q&A history (Sprint 3 task 4): kept across restarts, never shown across users.

- each asker sees only their own history; owner/administrator can see all
- the history survives a restart (new engine on the same database file)
- a failed AI2 call is in the history with its error and no answer
- outsiders (other tenant, expired grant) are refused
- purging the dossier removes the answer text, the audit trace stays
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.integration.test_ai2_review_fixes_flow import (
    DOSSIER_ID,
    OPERATOR,
    REVIEWER,
    TENANT_ID,
    _seed_dossier,
)
from tests.unit.conftest_contract import FakeFileStorage

from contract_intelligence.contract.infrastructure.persistence.dossier_deletion_service import (
    DossierDeletionService,
)
from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM, JobORM
from contract_intelligence.infrastructure.ai_adapters import AiAdapterError
from contract_intelligence.main import app
from contract_intelligence.shared.ai.client import StubAiServiceClient
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
from contract_intelligence.shared.auth.tenant import get_tenant_id
from contract_intelligence.shared.persistence import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models
from contract_intelligence.shared.persistence.session import get_async_session
from contract_intelligence.shared.query_history import QueryAnswerORM
from contract_intelligence.shared.query_policy import QueryTraceORM

pytestmark = pytest.mark.integration

QUERY_AI2 = "contract_intelligence.api.v1.dossiers.query_ai2"


def _user(user_id: str, *, role: str = "OPERATOR", tenant: str = TENANT_ID) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user_id, tenant_id=tenant, email=f"{user_id}@t.vn", display_name=user_id, role=role
    )


def _factory(db: Path) -> tuple[Any, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{db}")
    return engine, async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncGenerator[Path, None]:
    import_all_models()
    path = tmp_path / "history.db"
    engine, factory = _factory(path)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await _seed_dossier(factory)
    async with factory() as session:
        dossier = await session.get(DossierORM, DOSSIER_ID)
        assert dossier is not None
        past = (datetime.now(tz=UTC) - timedelta(hours=1)).isoformat(timespec="seconds")
        metadata = dict(dossier.metadata_json or {})
        metadata["shared_with"] = [
            *metadata.get("shared_with", []),
            {"id": "expired-user", "expires_at": past},
        ]
        dossier.metadata_json = metadata
        # No pending current run: otherwise queries answer BLOCKED without AI2.
        await session.execute(
            update(JobORM).where(JobORM.dossier_id == DOSSIER_ID).values(current_run_id=None)
        )
        await session.commit()
    await engine.dispose()
    yield path


async def _client(db: Path) -> tuple[Any, AsyncClient]:
    """A fresh engine + app client on the same file: what a server restart sees."""
    engine, factory = _factory(db)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_async_session] = override_session
    return engine, AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _as(user: AuthenticatedUser) -> None:
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_tenant_id] = lambda: user.tenant_id


def _answer(text: str) -> dict[str, Any]:
    return {"state": "PASS", "answer": text, "citations": []}


async def _ask(client: AsyncClient, user: AuthenticatedUser, question: str, answer: str) -> None:
    _as(user)
    with patch(QUERY_AI2, new=AsyncMock(return_value=_answer(answer))):
        response = await client.post(f"/api/v1/dossiers/{DOSSIER_ID}/ask", json={"query": question})
    assert response.status_code == 200, response.text


async def _history(client: AsyncClient, user: AuthenticatedUser, **params: Any) -> Any:
    _as(user)
    return await client.get(f"/api/v1/dossiers/{DOSSIER_ID}/queries", params=params)


@pytest.mark.asyncio
async def test_history_is_per_user_and_survives_a_restart(db: Path) -> None:
    engine, client = await _client(db)
    async with client:
        await _ask(client, OPERATOR, "Giá trị hợp đồng là bao nhiêu?", "1.286.400.000 đồng")
        await _ask(client, OPERATOR, "Thời hạn thanh toán?", "30 ngày")
        await _ask(client, REVIEWER, "Phạt vi phạm bao nhiêu?", "8% giá trị phần vi phạm")
    await engine.dispose()
    app.dependency_overrides.clear()

    # "Restart": new engine and client, nothing kept in memory.
    engine, client = await _client(db)
    async with client:
        mine = await _history(client, OPERATOR)
        assert mine.status_code == 200
        body = mine.json()
        assert body["meta"]["total"] == 2
        assert [item["question"] for item in body["data"]] == [
            "Thời hạn thanh toán?",
            "Giá trị hợp đồng là bao nhiêu?",
        ]
        assert body["data"][0]["answer"] == "30 ngày"
        assert {item["actor_id"] for item in body["data"]} == {OPERATOR.user_id}

        reviewer = (await _history(client, REVIEWER)).json()
        assert [item["answer"] for item in reviewer["data"]] == ["8% giá trị phần vi phạm"]

        everyone = await _history(client, OPERATOR, scope="all")
        assert everyone.status_code == 200
        assert everyone.json()["meta"]["total"] == 3

        # Shared with the reviewer, but not theirs to read everyone's questions.
        assert (await _history(client, REVIEWER, scope="all")).status_code == 403
    await engine.dispose()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_failed_query_is_kept_without_an_answer(db: Path) -> None:
    engine, client = await _client(db)
    async with client:
        _as(OPERATOR)
        with patch(QUERY_AI2, new=AsyncMock(side_effect=AiAdapterError("AI2 down"))):
            response = await client.post(
                f"/api/v1/dossiers/{DOSSIER_ID}/query", json={"query": "Còn hiệu lực không?"}
            )
        assert response.status_code == 502
        (item,) = (await _history(client, OPERATOR)).json()["data"]
        assert item["question"] == "Còn hiệu lực không?"
        assert item["answer"] is None
        assert item["error_code"] == "AI2_QUERY_FAILED"
    await engine.dispose()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outsider", "expected"),
    [
        (_user("foreign", role="ADMINISTRATOR", tenant="tenant-other"), {403, 404}),
        (_user("expired-user"), {403}),
        (_user("stranger", role="ADMINISTRATOR"), {403}),
    ],
)
async def test_outsiders_cannot_read_history(
    db: Path, outsider: AuthenticatedUser, expected: set[int]
) -> None:
    engine, client = await _client(db)
    async with client:
        await _ask(client, OPERATOR, "Bên A là ai?", "Công ty A")
        for scope in ("mine", "all"):
            response = await _history(client, outsider, scope=scope)
            assert response.status_code in expected, (scope, response.text)
            assert "Công ty A" not in response.text
    await engine.dispose()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_purge_removes_answers_and_keeps_the_audit_trace(db: Path) -> None:
    engine, client = await _client(db)
    async with client:
        await _ask(client, OPERATOR, "Điều khoản bảo mật?", "Điều 9: bảo mật 5 năm")
    app.dependency_overrides.clear()

    _, factory = _factory(db)
    async with factory() as session:
        service = DossierDeletionService(
            session=session,
            storage=FakeFileStorage(),
            ai_client=StubAiServiceClient(),
            tenant_id=TENANT_ID,
        )
        await service.tombstone(DOSSIER_ID, actor_user_id=OPERATOR.user_id)
        await session.commit()
        await service.purge(DOSSIER_ID)
        await session.commit()

        answers = await session.scalar(select(func.count()).select_from(QueryAnswerORM))
        traces = await session.scalar(select(func.count()).select_from(QueryTraceORM))
    assert answers == 0
    assert traces == 1
    await engine.dispose()
