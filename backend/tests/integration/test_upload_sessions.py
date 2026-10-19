"""Chunked dossier upload (/api/v1/uploads, issue #145) — FastAPI + SQLite.

Cloudflare Free cuts a request still sending its body after ~125 s, so large
dossiers go up as numbered chunks. These tests drive the real routes with a
tiny chunk size, so a one-page PDF already spans many chunks.

    cd backend
    uv run pytest tests/integration/test_upload_sessions.py -v
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncGenerator
from datetime import timedelta
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.pdf_bytes import make_pdf
from tests.unit.conftest_contract import FakeFileStorage

from contract_intelligence.config.settings import get_settings
from contract_intelligence.contract.application.services.contract_service import (
    ContractService,
)
from contract_intelligence.contract.infrastructure.persistence import upload_session_store
from contract_intelligence.contract.infrastructure.persistence.upload_session_store import (
    UploadChunkORM,
    UploadSessionORM,
)
from contract_intelligence.contract.interfaces.api.routers import upload_session_router
from contract_intelligence.infrastructure import messaging, storage
from contract_intelligence.main import app
from contract_intelligence.shared.base import utcnow
from contract_intelligence.shared.persistence import Base, bind_engine, reset_engine
from contract_intelligence.shared.persistence.session import get_async_session

CHUNK = 256  # bytes; a blank one-page PDF is ~600 bytes, so several chunks


@pytest.fixture(autouse=True)
def _settings(monkeypatch: pytest.MonkeyPatch) -> Any:
    settings = get_settings()
    monkeypatch.setattr(settings, "database_url", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(settings, "auth_mode", "keycloak")
    monkeypatch.setattr(settings, "keycloak_server_url", "https://test-keycloak.local")
    monkeypatch.setattr(settings, "keycloak_realm", "test-realm")
    monkeypatch.setattr(settings, "keycloak_client_id", "ci-backend")
    monkeypatch.setattr(settings, "keycloak_audience", "ci-backend")
    monkeypatch.setattr(
        settings,
        "keycloak_role_map",
        {
            "ci_operator": "OPERATOR",
            "ci_reviewer": "REVIEWER",
            "ci_administrator": "ADMINISTRATOR",
        },
    )
    monkeypatch.setattr(settings, "env", "test")
    monkeypatch.setattr(settings, "job_queue_enabled", False)
    monkeypatch.setattr(settings, "upload_chunk_bytes", CHUNK)
    monkeypatch.setattr(settings, "upload_sessions_per_user", 3)
    return settings


@pytest_asyncio.fixture
async def db(tmp_path: Any) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'uploads.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    bind_engine(engine)
    yield async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    reset_engine()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(
    db: async_sessionmaker[AsyncSession],
    cached_keycloak_jwks: str,
    mock_keycloak_settings: Any,
) -> AsyncGenerator[AsyncClient, None]:
    from contract_intelligence.shared.storage import reset_file_storage, set_file_storage

    set_file_storage(FakeFileStorage())

    async def session_override() -> AsyncGenerator[AsyncSession, None]:
        async with db() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_async_session] = session_override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    reset_file_storage()


@pytest.fixture
def headers(make_keycloak_token: Any) -> Any:
    def _headers(*, role: str = "OPERATOR", user_id: str = "usr_01HZ_TEST") -> dict[str, str]:
        token = make_keycloak_token(role=role, user_id=user_id)
        return {"Authorization": f"Bearer {token}", "X-Tenant-Id": "tenant_vgr_01"}

    return _headers


def _code(response: Any) -> str:
    """The domain error code of a failed call ({"error": {"code": ...}})."""
    return response.json()["error"]["code"]


def _chunks(data: bytes) -> list[bytes]:
    return [data[i : i + CHUNK] for i in range(0, len(data), CHUNK)]


async def _open(
    client: AsyncClient,
    headers: dict[str, str],
    files: list[tuple[str, str, bytes]],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/uploads",
        json={
            "metadata": metadata if metadata is not None else {"name": "Hồ sơ chia khúc"},
            "files": [
                {"role": role, "filename": name, "size": len(data)} for role, name, data in files
            ],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _put(
    client: AsyncClient, headers: dict[str, str], upload_id: str, index: int, n: int, body: bytes
) -> Any:
    return await client.put(
        f"/api/v1/uploads/{upload_id}/files/{index}/chunks/{n}",
        content=body,
        headers={**headers, "Content-Type": "application/octet-stream"},
    )


async def _send_all(
    client: AsyncClient, headers: dict[str, str], upload_id: str, files: list[bytes]
) -> None:
    for index, data in enumerate(files):
        # Out of order on purpose: the server joins by chunk number.
        for n, part in reversed(list(enumerate(_chunks(data)))):
            response = await _put(client, headers, upload_id, index, n, part)
            assert response.status_code == 204, response.text


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_chunks_become_the_same_dossier_as_a_multipart_upload(
        self, client: AsyncClient, headers: Any
    ) -> None:
        h = headers()
        contract = make_pdf(pages=2, marker="contract")
        annex = make_pdf(marker="annex")
        session = await _open(
            client, h, [("annex", "phu-luc.pdf", annex), ("contract", "hop-dong.pdf", contract)]
        )
        # Contract first whatever the declared order; chunk counts from the size.
        assert [f["role"] for f in session["files"]] == ["contract", "annex"]
        assert session["files"][0]["chunks"] == len(_chunks(contract))
        assert session["chunk_size"] == CHUNK
        assert session["status"] == "open"

        await _send_all(client, h, session["upload_id"], [contract, annex])

        state = (await client.get(f"/api/v1/uploads/{session['upload_id']}", headers=h)).json()
        assert state["data"]["files"][0]["received"] == list(range(len(_chunks(contract))))

        messaging.publish_event.reset_mock()  # type: ignore[attr-defined]
        done = await client.post(f"/api/v1/uploads/{session['upload_id']}/complete", headers=h)
        assert done.status_code == 202, done.text
        dossier_id = done.json()["data"]["dossier_id"]
        assert dossier_id.startswith("dos_")
        assert done.json()["data"]["job_id"].startswith("job_")

        docs = (await client.get(f"/api/v1/dossiers/{dossier_id}/documents", headers=h)).json()[
            "data"
        ]
        assert [(d["role"].lower(), d["filename"]) for d in docs] == [
            ("contract", "hop-dong.pdf"),
            ("annex", "phu-luc.pdf"),
        ]
        dossier = (await client.get(f"/api/v1/dossiers/{dossier_id}", headers=h)).json()["data"]
        assert dossier["name"] == "Hồ sơ chia khúc"

        # OCR starts as for POST /dossiers.
        events = [c.args for c in messaging.publish_event.await_args_list]  # type: ignore[attr-defined]
        assert events[0][:1] == ("dossier_events",)
        assert events[0][1]["event"] == "dossier.uploaded"
        assert events[0][1]["dossier_id"] == dossier_id

    @pytest.mark.asyncio
    async def test_complete_again_returns_the_same_dossier(
        self, client: AsyncClient, headers: Any
    ) -> None:
        h = headers()
        pdf = make_pdf()
        session = await _open(client, h, [("contract", "a.pdf", pdf)])
        await _send_all(client, h, session["upload_id"], [pdf])
        first = await client.post(f"/api/v1/uploads/{session['upload_id']}/complete", headers=h)
        second = await client.post(f"/api/v1/uploads/{session['upload_id']}/complete", headers=h)
        assert first.status_code == second.status_code == 202
        assert first.json()["data"] == second.json()["data"]
        listed = (await client.get("/api/v1/dossiers", headers=h)).json()["data"]
        assert len(listed) == 1

    @pytest.mark.asyncio
    async def test_completed_session_drops_its_chunk_objects(
        self, client: AsyncClient, headers: Any, db: async_sessionmaker[AsyncSession]
    ) -> None:
        h = headers()
        pdf = make_pdf()
        session = await _open(client, h, [("contract", "a.pdf", pdf)])
        await _send_all(client, h, session["upload_id"], [pdf])
        async with db() as s:
            paths = list((await s.execute(select(UploadChunkORM.object_path))).scalars())
        assert paths and all(f"/uploads/tenant_vgr_01/{session['upload_id']}/" in p for p in paths)

        await client.post(f"/api/v1/uploads/{session['upload_id']}/complete", headers=h)
        async with db() as s:
            assert (await s.execute(select(UploadChunkORM))).first() is None
        for path in paths:
            with pytest.raises(FileNotFoundError):
                await storage.download_object(path)

    @pytest.mark.asyncio
    async def test_split_pending_waits_for_the_split_like_post_dossiers(
        self, client: AsyncClient, headers: Any
    ) -> None:
        h = headers()
        pdf = make_pdf(pages=3)
        session = await _open(
            client, h, [("contract", "tron.pdf", pdf)], {"name": "Trộn", "split_pending": True}
        )
        await _send_all(client, h, session["upload_id"], [pdf])
        messaging.publish_event.reset_mock()  # type: ignore[attr-defined]
        done = await client.post(f"/api/v1/uploads/{session['upload_id']}/complete", headers=h)
        assert done.status_code == 202
        assert messaging.publish_event.await_count == 0  # type: ignore[attr-defined]


class TestChunks:
    @pytest.mark.asyncio
    async def test_resending_a_chunk_replaces_it(self, client: AsyncClient, headers: Any) -> None:
        h = headers()
        pdf = make_pdf()
        session = await _open(client, h, [("contract", "a.pdf", pdf)])
        first = _chunks(pdf)[0]
        assert (
            await _put(client, h, session["upload_id"], 0, 0, b"x" * len(first))
        ).status_code == 204
        await _send_all(client, h, session["upload_id"], [pdf])  # sends chunk 0 again, right bytes
        done = await client.post(f"/api/v1/uploads/{session['upload_id']}/complete", headers=h)
        assert done.status_code == 202, done.text

    @pytest.mark.asyncio
    async def test_a_chunk_of_the_wrong_size_is_refused(
        self, client: AsyncClient, headers: Any
    ) -> None:
        h = headers()
        pdf = make_pdf()
        session = await _open(client, h, [("contract", "a.pdf", pdf)])
        too_short = await _put(client, h, session["upload_id"], 0, 0, b"x" * (CHUNK - 1))
        too_long = await _put(client, h, session["upload_id"], 0, 0, b"x" * (CHUNK + 1))
        last = len(_chunks(pdf)) - 1
        last_padded = await _put(client, h, session["upload_id"], 0, last, b"x" * CHUNK)
        assert too_short.status_code == too_long.status_code == 422
        assert len(pdf) % CHUNK != 0  # the last chunk is short
        assert last_padded.status_code == 422

    @pytest.mark.asyncio
    async def test_unknown_file_or_chunk_is_404(self, client: AsyncClient, headers: Any) -> None:
        h = headers()
        pdf = make_pdf()
        session = await _open(client, h, [("contract", "a.pdf", pdf)])
        beyond = len(_chunks(pdf))
        assert (await _put(client, h, session["upload_id"], 1, 0, b"x")).status_code == 404
        assert (await _put(client, h, session["upload_id"], 0, beyond, b"x")).status_code == 404

    @pytest.mark.asyncio
    async def test_complete_with_missing_chunks_lists_them(
        self, client: AsyncClient, headers: Any
    ) -> None:
        h = headers()
        pdf = make_pdf()
        session = await _open(client, h, [("contract", "a.pdf", pdf)])
        parts = _chunks(pdf)
        for n, part in enumerate(parts[:-1]):
            await _put(client, h, session["upload_id"], 0, n, part)
        done = await client.post(f"/api/v1/uploads/{session['upload_id']}/complete", headers=h)
        assert done.status_code == 409
        assert _code(done) == "UPLOAD_MISSING_CHUNKS"
        assert done.json()["error"]["details"]["missing_chunks"] == {"0": [len(parts) - 1]}
        # Still open: send the last chunk and complete.
        await _put(client, h, session["upload_id"], 0, len(parts) - 1, parts[-1])
        again = await client.post(f"/api/v1/uploads/{session['upload_id']}/complete", headers=h)
        assert again.status_code == 202, again.text


class TestOpening:
    @pytest.mark.asyncio
    async def test_more_than_six_files_is_refused_before_any_byte(
        self, client: AsyncClient, headers: Any
    ) -> None:
        files = [{"role": "contract", "filename": "c.pdf", "size": 10}] + [
            {"role": "annex", "filename": f"a{i}.pdf", "size": 10} for i in range(6)
        ]
        response = await client.post(
            "/api/v1/uploads", json={"metadata": {}, "files": files}, headers=headers()
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "DOSSIER_TOO_MANY_DOCUMENTS"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("roles", [["annex"], ["contract", "contract"]])
    async def test_exactly_one_contract(
        self, client: AsyncClient, headers: Any, roles: list[str]
    ) -> None:
        files = [{"role": r, "filename": f"{i}.pdf", "size": 10} for i, r in enumerate(roles)]
        response = await client.post(
            "/api/v1/uploads", json={"metadata": {}, "files": files}, headers=headers()
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_a_file_over_the_size_cap_is_413(
        self, client: AsyncClient, headers: Any, _settings: Any
    ) -> None:
        size = _settings.upload_max_file_bytes + 1
        response = await client.post(
            "/api/v1/uploads",
            json={
                "metadata": {},
                "files": [{"role": "contract", "filename": "c.pdf", "size": size}],
            },
            headers=headers(),
        )
        assert response.status_code == 413

    @pytest.mark.asyncio
    async def test_invalid_metadata_is_refused_at_open(
        self, client: AsyncClient, headers: Any
    ) -> None:
        response = await client.post(
            "/api/v1/uploads",
            json={
                "metadata": {"tags": "not-a-list"},
                "files": [{"role": "contract", "filename": "c.pdf", "size": 10}],
            },
            headers=headers(),
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_at_the_cap_the_oldest_abandoned_session_makes_room(
        self, client: AsyncClient, headers: Any, db: async_sessionmaker[AsyncSession]
    ) -> None:
        """Three uploads cut off (tab closed, reload) must not lock the user out for 24 h."""
        h = headers()
        pdf = make_pdf()
        oldest = await _open(client, h, [("contract", "a.pdf", pdf)])
        await _put(client, h, oldest["upload_id"], 0, 0, _chunks(pdf)[0])
        async with db() as s:
            path = (await s.execute(select(UploadChunkORM.object_path))).scalar_one()
        kept = [await _open(client, h, [("contract", "c.pdf", b"x" * 10)]) for _ in range(2)]
        async with db() as s:
            # Only the abandoned upload has been idle (no chunk) for over 5 minutes.
            await s.execute(
                update(UploadSessionORM)
                .where(UploadSessionORM.id == oldest["upload_id"])
                .values(updated_at=utcnow() - timedelta(minutes=6))
            )
            await s.commit()

        newest = await _open(client, h, [("contract", "d.pdf", b"x" * 10)])

        old_state = (await client.get(f"/api/v1/uploads/{oldest['upload_id']}", headers=h)).json()
        assert old_state["data"]["status"] == "cancelled"
        with pytest.raises(FileNotFoundError):
            await storage.download_object(path)
        for session in [*kept, newest]:
            state = (await client.get(f"/api/v1/uploads/{session['upload_id']}", headers=h)).json()
            assert state["data"]["status"] == "open"
        # Sending into the evicted session says why.
        late = await _put(client, h, oldest["upload_id"], 0, 1, _chunks(pdf)[1])
        assert late.status_code == 409
        assert _code(late) == "UPLOAD_CANCELLED"
        # Another user is not affected.
        await _open(client, headers(user_id="usr_other"), [("contract", "c.pdf", b"x" * 10)])

    @pytest.mark.asyncio
    async def test_uploads_still_sending_are_never_evicted(
        self, client: AsyncClient, headers: Any, db: async_sessionmaker[AsyncSession]
    ) -> None:
        """Several dossiers uploading at once: the 4th waits (429), none is cut off."""
        h = headers()
        sessions = [await _open(client, h, [("contract", "c.pdf", b"x" * 10)]) for _ in range(3)]

        response = await client.post(
            "/api/v1/uploads",
            json={"metadata": {}, "files": [{"role": "contract", "filename": "c.pdf", "size": 10}]},
            headers=h,
        )
        assert response.status_code == 429
        for session in sessions:
            state = (await client.get(f"/api/v1/uploads/{session['upload_id']}", headers=h)).json()
            assert state["data"]["status"] == "open"

    @pytest.mark.asyncio
    async def test_sessions_being_completed_are_never_evicted(
        self, client: AsyncClient, headers: Any, db: async_sessionmaker[AsyncSession]
    ) -> None:
        h = headers()
        for _ in range(3):
            await _open(client, h, [("contract", "c.pdf", b"x" * 10)])
        async with db() as s:
            await s.execute(update(UploadSessionORM).values(status="completing"))
            await s.commit()

        response = await client.post(
            "/api/v1/uploads",
            json={"metadata": {}, "files": [{"role": "contract", "filename": "c.pdf", "size": 10}]},
            headers=h,
        )
        assert response.status_code == 429
        async with db() as s:
            statuses = set((await s.execute(select(UploadSessionORM.status))).scalars())
        assert statuses == {"completing"}

    @pytest.mark.asyncio
    async def test_reviewer_cannot_upload(self, client: AsyncClient, headers: Any) -> None:
        response = await client.post(
            "/api/v1/uploads",
            json={"metadata": {}, "files": [{"role": "contract", "filename": "c.pdf", "size": 10}]},
            headers=headers(role="REVIEWER"),
        )
        assert response.status_code == 403


class TestOwnershipAndLifecycle:
    @pytest.mark.asyncio
    async def test_another_user_sees_404(self, client: AsyncClient, headers: Any) -> None:
        pdf = make_pdf()
        session = await _open(client, headers(), [("contract", "a.pdf", pdf)])
        other = headers(user_id="usr_other")
        upload_id = session["upload_id"]
        assert (await client.get(f"/api/v1/uploads/{upload_id}", headers=other)).status_code == 404
        assert (await _put(client, other, upload_id, 0, 0, _chunks(pdf)[0])).status_code == 404
        assert (
            await client.post(f"/api/v1/uploads/{upload_id}/complete", headers=other)
        ).status_code == 404
        assert (
            await client.delete(f"/api/v1/uploads/{upload_id}", headers=other)
        ).status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_drops_chunks_and_closes_the_session(
        self, client: AsyncClient, headers: Any, db: async_sessionmaker[AsyncSession]
    ) -> None:
        h = headers()
        pdf = make_pdf()
        session = await _open(client, h, [("contract", "a.pdf", pdf)])
        upload_id = session["upload_id"]
        await _put(client, h, upload_id, 0, 0, _chunks(pdf)[0])
        async with db() as s:
            path = (await s.execute(select(UploadChunkORM.object_path))).scalar_one()

        assert (await client.delete(f"/api/v1/uploads/{upload_id}", headers=h)).status_code == 204
        assert (await client.delete(f"/api/v1/uploads/{upload_id}", headers=h)).status_code == 204
        with pytest.raises(FileNotFoundError):
            await storage.download_object(path)
        late = await _put(client, h, upload_id, 0, 0, _chunks(pdf)[0])
        assert late.status_code == 409
        assert _code(late) == "UPLOAD_CANCELLED"
        done = await client.post(f"/api/v1/uploads/{upload_id}/complete", headers=h)
        assert done.status_code == 409
        assert _code(done) == "UPLOAD_CANCELLED"
        state = (await client.get(f"/api/v1/uploads/{upload_id}", headers=h)).json()["data"]
        assert state["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_a_completed_upload_cannot_be_cancelled(
        self, client: AsyncClient, headers: Any
    ) -> None:
        h = headers()
        pdf = make_pdf()
        session = await _open(client, h, [("contract", "a.pdf", pdf)])
        await _send_all(client, h, session["upload_id"], [pdf])
        await client.post(f"/api/v1/uploads/{session['upload_id']}/complete", headers=h)
        response = await client.delete(f"/api/v1/uploads/{session['upload_id']}", headers=h)
        assert response.status_code == 409
        assert _code(response) == "UPLOAD_COMPLETED"
        assert response.json()["error"]["details"]["dossier_id"].startswith("dos_")
        late = await _put(client, h, session["upload_id"], 0, 0, _chunks(pdf)[0])
        assert _code(late) == "UPLOAD_COMPLETED"

    @pytest.mark.asyncio
    async def test_a_chunk_changed_in_storage_is_a_size_mismatch(
        self, client: AsyncClient, headers: Any, db: async_sessionmaker[AsyncSession]
    ) -> None:
        h = headers()
        pdf = make_pdf()
        session = await _open(client, h, [("contract", "a.pdf", pdf)])
        await _send_all(client, h, session["upload_id"], [pdf])
        async with db() as s:
            path = (
                await s.execute(
                    select(UploadChunkORM.object_path).where(UploadChunkORM.chunk_no == 0)
                )
            ).scalar_one()
        await storage.upload_file(path.removeprefix("s3://dossiers/"), b"short")

        done = await client.post(f"/api/v1/uploads/{session['upload_id']}/complete", headers=h)
        assert done.status_code == 409
        assert _code(done) == "UPLOAD_SIZE_MISMATCH"
        assert done.json()["error"]["details"]["declared_bytes"] == len(pdf)

    @pytest.mark.asyncio
    async def test_not_a_pdf_is_422_and_the_session_stays_open(
        self, client: AsyncClient, headers: Any
    ) -> None:
        h = headers()
        junk = b"not a pdf at all " * 40
        session = await _open(client, h, [("contract", "a.pdf", junk)])
        await _send_all(client, h, session["upload_id"], [junk])
        done = await client.post(f"/api/v1/uploads/{session['upload_id']}/complete", headers=h)
        assert done.status_code == 422
        state = (await client.get(f"/api/v1/uploads/{session['upload_id']}", headers=h)).json()
        assert state["data"]["status"] == "open"
        assert (await client.get("/api/v1/dossiers", headers=h)).json()["data"] == []

    @pytest.mark.asyncio
    async def test_expired_session_is_gone_then_swept(
        self, client: AsyncClient, headers: Any, db: async_sessionmaker[AsyncSession]
    ) -> None:
        h = headers()
        pdf = make_pdf()
        session = await _open(client, h, [("contract", "a.pdf", pdf)])
        upload_id = session["upload_id"]
        await _put(client, h, upload_id, 0, 0, _chunks(pdf)[0])
        async with db() as s:
            path = (await s.execute(select(UploadChunkORM.object_path))).scalar_one()
            await s.execute(
                update(UploadSessionORM).values(expires_at=utcnow() - timedelta(seconds=1))
            )
            await s.commit()

        gone = await _put(client, h, upload_id, 0, 1, _chunks(pdf)[1])
        assert gone.status_code == 410
        assert _code(gone) == "UPLOAD_EXPIRED"
        assert (await client.get(f"/api/v1/uploads/{upload_id}", headers=h)).status_code == 410
        # Expired sessions no longer count toward the per-user cap.
        for _ in range(3):
            await _open(client, h, [("contract", "c.pdf", b"x" * 10)])

        removed = await upload_session_store.run_expired_session_sweep()
        assert removed == 1
        async with db() as s:
            assert (
                await s.execute(select(UploadSessionORM).where(UploadSessionORM.id == upload_id))
            ).first() is None
            assert (await s.execute(select(UploadChunkORM))).first() is None
        with pytest.raises(FileNotFoundError):
            await storage.download_object(path)
        assert (await client.get(f"/api/v1/uploads/{upload_id}", headers=h)).status_code == 404

    @pytest.mark.asyncio
    async def test_a_stuck_completing_session_can_be_completed_later(
        self, client: AsyncClient, headers: Any, db: async_sessionmaker[AsyncSession]
    ) -> None:
        h = headers()
        pdf = make_pdf()
        session = await _open(client, h, [("contract", "a.pdf", pdf)])
        upload_id = session["upload_id"]
        await _send_all(client, h, upload_id, [pdf])
        async with db() as s:
            await s.execute(update(UploadSessionORM).values(status="completing"))
            await s.commit()
        busy = await client.post(f"/api/v1/uploads/{upload_id}/complete", headers=h)
        assert busy.status_code == 409  # another request may still be building it
        assert _code(busy) == "UPLOAD_COMPLETING"

        async with db() as s:
            await s.execute(
                update(UploadSessionORM).values(updated_at=utcnow() - timedelta(minutes=11))
            )
            await s.commit()
        done = await client.post(f"/api/v1/uploads/{upload_id}/complete", headers=h)
        assert done.status_code == 202, done.text


class TestJoinOrder:
    """`_join_chunks` rebuilds the PDF that OCR reads: bytes, not just length, must match."""

    @staticmethod
    def _fake_store(monkeypatch: pytest.MonkeyPatch, blobs: dict[str, bytes], delay) -> None:
        async def download(path: str) -> bytes:
            await asyncio.sleep(delay(path))
            return blobs[path]

        monkeypatch.setattr(storage, "download_object", download)

    @pytest.mark.asyncio
    async def test_first_chunk_slowest_still_joins_in_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        parts = [bytes([i]) * 97 for i in range(40)]
        blobs = {f"s3://dossiers/c/{i:05d}": part for i, part in enumerate(parts)}
        paths = list(blobs)
        # Chunk 0 finishes last, chunk 39 first: the reverse of the file order.
        self._fake_store(monkeypatch, blobs, lambda path: (40 - paths.index(path)) * 0.002)

        assert await upload_session_router._join_chunks(paths) == b"".join(parts)

    @pytest.mark.asyncio
    async def test_random_download_times_never_reorder_bytes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rng = random.Random(149)
        for _ in range(20):
            parts = [rng.randbytes(64) for _ in range(40)]
            blobs = {f"s3://dossiers/r/{i:05d}": part for i, part in enumerate(parts)}
            self._fake_store(monkeypatch, blobs, lambda _path: rng.uniform(0, 0.02))

            assert await upload_session_router._join_chunks(list(blobs)) == b"".join(parts)

    @pytest.mark.asyncio
    async def test_at_most_the_window_downloads_run_at_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        running = peak = 0

        async def download(path: str) -> bytes:
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.001)
            running -= 1
            return path.encode()

        monkeypatch.setattr(storage, "download_object", download)
        paths = [f"p{i:03d}" for i in range(50)]

        assert await upload_session_router._join_chunks(paths) == "".join(paths).encode()
        assert peak <= upload_session_router._JOIN_CONCURRENCY


class TestOrphanFiles:
    """A dossier that is not committed must not leave its PDFs in MinIO."""

    @staticmethod
    def _record_uploads(
        monkeypatch: pytest.MonkeyPatch, *, fail_on: str | None = None
    ) -> list[str]:
        stored: list[str] = []
        original = storage.upload_file

        async def upload(file_name: str, file_data: bytes) -> str:
            if fail_on and fail_on in file_name:
                raise RuntimeError("MinIO refused the write")
            path = await original(file_name, file_data)
            if not file_name.startswith("uploads/"):  # dossier files, not chunks
                stored.append(path)
            return path

        monkeypatch.setattr(storage, "upload_file", upload)
        return stored

    @staticmethod
    async def _gone(paths: list[str]) -> bool:
        for path in paths:
            try:
                await storage.download_object(path)
            except FileNotFoundError:
                continue
            return False
        return True

    @pytest.mark.asyncio
    async def test_second_annex_failing_deletes_the_contract_and_first_annex(
        self, client: AsyncClient, headers: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        h = headers()
        files = [make_pdf(marker="hd"), make_pdf(marker="pl1"), make_pdf(marker="pl2")]
        session = await _open(
            client,
            h,
            [
                ("contract", "hd.pdf", files[0]),
                ("annex", "pl1.pdf", files[1]),
                ("annex", "pl2.pdf", files[2]),
            ],
        )
        await _send_all(client, h, session["upload_id"], files)
        stored = self._record_uploads(monkeypatch, fail_on="/02_")

        with pytest.raises(RuntimeError, match="MinIO refused"):
            await client.post(f"/api/v1/uploads/{session['upload_id']}/complete", headers=h)

        assert len(stored) == 2  # contract and first annex were written...
        assert await self._gone(stored)  # ...and removed again
        state = (await client.get(f"/api/v1/uploads/{session['upload_id']}", headers=h)).json()
        assert state["data"]["status"] == "open"  # the user can complete again
        assert (await client.get("/api/v1/dossiers", headers=h)).json()["data"] == []

    @pytest.mark.asyncio
    async def test_commit_failing_deletes_every_file_written(
        self, client: AsyncClient, headers: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        h = headers()
        files = [make_pdf(marker="hd"), make_pdf(marker="pl1")]
        session = await _open(
            client, h, [("contract", "hd.pdf", files[0]), ("annex", "pl1.pdf", files[1])]
        )
        await _send_all(client, h, session["upload_id"], files)
        stored = self._record_uploads(monkeypatch)

        async def broken_commit(self: ContractService) -> None:
            raise RuntimeError("database went away")

        monkeypatch.setattr(ContractService, "commit", broken_commit)
        with pytest.raises(RuntimeError, match="database went away"):
            await client.post(f"/api/v1/uploads/{session['upload_id']}/complete", headers=h)

        assert len(stored) == 2
        assert await self._gone(stored)

    @pytest.mark.asyncio
    async def test_post_dossiers_also_deletes_files_of_a_failed_upload(
        self, client: AsyncClient, headers: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stored = self._record_uploads(monkeypatch, fail_on="/01_")

        with pytest.raises(RuntimeError, match="MinIO refused"):
            await client.post(
                "/api/v1/dossiers",
                files=[
                    ("contract", ("hd.pdf", make_pdf(marker="hd"), "application/pdf")),
                    ("annexes", ("pl1.pdf", make_pdf(marker="pl1"), "application/pdf")),
                ],
                data={"metadata": '{"name": "orphan check"}'},
                headers=headers(),
            )

        assert len(stored) == 1
        assert await self._gone(stored)


class TestSweep:
    @pytest.mark.asyncio
    async def test_a_live_completing_session_is_kept_a_dead_one_is_removed(
        self, client: AsyncClient, headers: Any, db: async_sessionmaker[AsyncSession]
    ) -> None:
        h = headers()
        live = await _open(client, h, [("contract", "a.pdf", b"x" * 10)])
        dead = await _open(client, h, [("contract", "b.pdf", b"x" * 10)])
        past = utcnow() - timedelta(seconds=1)
        async with db() as s:
            await s.execute(update(UploadSessionORM).values(status="completing", expires_at=past))
            await s.execute(
                update(UploadSessionORM)
                .where(UploadSessionORM.id == dead["upload_id"])
                .values(updated_at=utcnow() - timedelta(minutes=11))
            )
            await s.commit()

        await upload_session_store.run_expired_session_sweep()

        async with db() as s:
            left = set((await s.execute(select(UploadSessionORM.id))).scalars())
        assert left == {live["upload_id"]}

    @pytest.mark.asyncio
    async def test_completed_rows_are_kept_seven_days(
        self, client: AsyncClient, headers: Any, db: async_sessionmaker[AsyncSession]
    ) -> None:
        h = headers()
        pdf = make_pdf()
        recent = await _open(client, h, [("contract", "a.pdf", pdf)])
        old = await _open(client, h, [("contract", "b.pdf", pdf)])
        for session in (recent, old):
            await _send_all(client, h, session["upload_id"], [pdf])
            await client.post(f"/api/v1/uploads/{session['upload_id']}/complete", headers=h)
        async with db() as s:
            await s.execute(
                update(UploadSessionORM)
                .where(UploadSessionORM.id == old["upload_id"])
                .values(created_at=utcnow() - timedelta(days=8))
            )
            await s.commit()

        await upload_session_store.run_expired_session_sweep()

        async with db() as s:
            left = set((await s.execute(select(UploadSessionORM.id))).scalars())
        assert left == {recent["upload_id"]}
        again = await client.post(f"/api/v1/uploads/{recent['upload_id']}/complete", headers=h)
        assert again.status_code == 202


class TestConcurrency:
    """Two requests on the same session, or on the same user's cap (review of 146054d1).

    Each test stops one request right after it read the session and runs the
    other one to the end in between, the order vdungx reproduced with barriers.
    """

    @pytest.mark.asyncio
    async def test_a_cancel_that_lost_to_complete_keeps_the_dossier(
        self, client: AsyncClient, headers: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        h = headers()
        pdf = make_pdf()
        session = await _open(client, h, [("contract", "a.pdf", pdf)])
        upload_id = session["upload_id"]
        await _send_all(client, h, upload_id, [pdf])

        real_cancel = upload_session_store.UploadSessionStore.cancel_if_open
        completed: list[Any] = []

        async def complete_first(self: Any, *args: Any, **kwargs: Any) -> Any:
            # DELETE has read "open"; /complete now builds the dossier and commits.
            completed.append(await client.post(f"/api/v1/uploads/{upload_id}/complete", headers=h))
            return await real_cancel(self, *args, **kwargs)

        monkeypatch.setattr(
            upload_session_store.UploadSessionStore, "cancel_if_open", complete_first
        )
        cancel = await client.delete(f"/api/v1/uploads/{upload_id}", headers=h)

        assert completed[0].status_code == 202
        assert cancel.status_code == 409
        assert _code(cancel) == "UPLOAD_COMPLETED"
        state = (await client.get(f"/api/v1/uploads/{upload_id}", headers=h)).json()["data"]
        assert state["status"] == "completed"
        # A client that lost the first answer still gets its dossier.
        again = await client.post(f"/api/v1/uploads/{upload_id}/complete", headers=h)
        assert again.status_code == 202
        assert again.json()["data"] == completed[0].json()["data"]

    @pytest.mark.asyncio
    async def test_concurrent_opens_never_pass_the_cap(
        self, client: AsyncClient, headers: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        h = headers()
        real_count = upload_session_store.UploadSessionStore.count_open

        async def slow_count(self: Any, user_id: str) -> int:
            count = await real_count(self, user_id)
            await asyncio.sleep(0.05)  # every request reads before any creates
            return count

        monkeypatch.setattr(upload_session_store.UploadSessionStore, "count_open", slow_count)
        body = {"metadata": {}, "files": [{"role": "contract", "filename": "c.pdf", "size": 10}]}
        responses = await asyncio.gather(
            *(client.post("/api/v1/uploads", json=body, headers=h) for _ in range(5))
        )

        assert sorted(r.status_code for r in responses) == [201, 201, 201, 429, 429]

    @pytest.mark.asyncio
    async def test_a_session_that_became_active_is_not_evicted(
        self,
        client: AsyncClient,
        headers: Any,
        db: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        h = headers()
        pdf = make_pdf()
        idle = await _open(client, h, [("contract", "a.pdf", pdf)])
        for _ in range(2):
            await _open(client, h, [("contract", "c.pdf", b"x" * 10)])
        async with db() as s:
            await s.execute(
                update(UploadSessionORM)
                .where(UploadSessionORM.id == idle["upload_id"])
                .values(updated_at=utcnow() - timedelta(minutes=6))
            )
            await s.commit()

        real_oldest = upload_session_store.UploadSessionStore.oldest_open

        async def chunk_arrives(self: Any, *args: Any, **kwargs: Any) -> Any:
            candidates = await real_oldest(self, *args, **kwargs)
            # Picked as idle, then a chunk comes in before it is cancelled.
            sent = await _put(client, h, idle["upload_id"], 0, 0, _chunks(pdf)[0])
            assert sent.status_code == 204
            return candidates

        monkeypatch.setattr(upload_session_store.UploadSessionStore, "oldest_open", chunk_arrives)
        response = await client.post(
            "/api/v1/uploads",
            json={"metadata": {}, "files": [{"role": "contract", "filename": "c.pdf", "size": 10}]},
            headers=h,
        )

        assert response.status_code == 429
        state = (await client.get(f"/api/v1/uploads/{idle['upload_id']}", headers=h)).json()
        assert state["data"]["status"] == "open"
        assert state["data"]["files"][0]["received"] == [0]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("ended_by", ["cancel", "complete"])
    async def test_a_chunk_arriving_after_the_session_ended_is_not_kept(
        self,
        ended_by: str,
        client: AsyncClient,
        headers: Any,
        db: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        h = headers()
        pdf = make_pdf()
        parts = _chunks(pdf)
        session = await _open(client, h, [("contract", "a.pdf", pdf)])
        upload_id = session["upload_id"]
        if ended_by == "complete":
            await _send_all(client, h, upload_id, [pdf])

        real_upload = storage.upload_file
        written: list[str] = []

        async def end_session_meanwhile(key: str, data: bytes) -> str:
            path = await real_upload(key, data)
            written.append(path)
            # The PUT has read "open" and stored its object; the session ends now.
            if ended_by == "cancel":
                ended = await client.delete(f"/api/v1/uploads/{upload_id}", headers=h)
                assert ended.status_code == 204
            else:
                monkeypatch.setattr(storage, "upload_file", real_upload)
                ended = await client.post(f"/api/v1/uploads/{upload_id}/complete", headers=h)
                assert ended.status_code == 202
            return path

        monkeypatch.setattr(storage, "upload_file", end_session_meanwhile)
        late = await _put(client, h, upload_id, 0, 0, parts[0])

        assert late.status_code == 409
        assert _code(late) == ("UPLOAD_CANCELLED" if ended_by == "cancel" else "UPLOAD_COMPLETED")
        async with db() as s:
            assert (await s.execute(select(UploadChunkORM))).first() is None
        # The late object is not left behind in MinIO.
        with pytest.raises(FileNotFoundError):
            await storage.download_object(written[0])
