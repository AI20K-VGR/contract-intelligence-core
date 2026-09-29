"""Integration tests cho async pipeline flow + AI service integration.

Test setup giống test_auth_endpoints.py — SQLite in-memory + mock Keycloak JWKS.
Mỗi test verify:
    - POST /dossiers (multipart) trả 202 + dossier_id + job_id; endpoint cũ
      POST /dossiers/upload đã bị gỡ
    - POST /dossiers/{id}/runs schedule pipeline run async qua BackgroundDispatcher
    - Stub AI client trả completed ngay → orchestrator persist results
    - GET /runs/{id} trả status="succeeded"
    - GET /runs/{id}/events stream SSE events
    - POST /documents/{id}/re-ocr submits async + poll returns result
    - GET /ai/healthz + /readyz proxy qua AI client

Sau refactor Keycloak SSO:
    - Test KHÔNG seed users vào DB nữa (Keycloak quản lý user identity).
    - Mỗi test tạo mock Keycloak JWT qua fixture `make_keycloak_token`
      (private key trong memory, JWKS cache patched).
    - User provisioning qua webhook được test riêng (Phase 2).

Chạy:
    cd backend
    uv run pytest tests/integration/test_ai_pipeline.py -v
"""

from __future__ import annotations

import asyncio
import io
import json
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from tests.pdf_bytes import make_pdf
from tests.unit.conftest_contract import FakeFileStorage

from contract_intelligence.config.settings import get_settings
from contract_intelligence.main import app
from contract_intelligence.shared.ai import (
    reset_pipeline_orchestrator,
)
from contract_intelligence.shared.persistence import (
    Base,
    bind_engine,
    reset_engine,
)
from contract_intelligence.shared.persistence.session import get_async_session
from contract_intelligence.shared.storage import reset_file_storage, set_file_storage

# ──────────────────────────────────────────────────────────────────────────────
# Settings override (autouse) — Keycloak SSO mode (no /auth/login anymore)
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def _override_settings() -> AsyncGenerator[None, None]:
    get_settings.cache_clear()
    settings = get_settings()
    settings.database_url = "sqlite+aiosqlite:///:memory:"
    settings.auth_mode = "keycloak"
    settings.keycloak_server_url = "https://test-keycloak.local"
    settings.keycloak_realm = "test-realm"
    settings.keycloak_client_id = "ci-backend"
    settings.keycloak_audience = "ci-backend"
    settings.keycloak_role_map = {
        "ci_operator": "OPERATOR",
        "ci_reviewer": "REVIEWER",
        "ci_administrator": "ADMINISTRATOR",
    }
    settings.env = "test"
    settings.ai_service_mode = "stub"  # Dùng stub để test deterministic
    settings.ai_dispatcher_max_polls = 5
    settings.ai_dispatcher_poll_interval_seconds = 0.1
    settings.job_queue_enabled = False
    yield
    get_settings.cache_clear()


# ──────────────────────────────────────────────────────────────────────────────
# DB fixtures — use tempfile SQLite so all sessions share the same DB
# ──────────────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="function")
async def db_engine(tmp_path: Any) -> AsyncGenerator[Any, None]:
    """Fresh SQLite file-based engine + schema per test.

    Using a file (not :memory:) ensures all async sessions share the same DB
    without SQLite shared-cache mode issues.
    """
    db_path = tmp_path / "test_ai_pipeline.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    bind_engine(engine)
    yield engine
    reset_engine()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_engine: Any) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
        factory = async_sessionmaker(bind=db_engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_async_session] = override_get_async_session
    # POST /dossiers ghi blob qua MinIO (stub trong conftest) + FileStorage — dùng
    # bản in-memory để không ghi đường dẫn s3:// ra filesystem.
    set_file_storage(FakeFileStorage())
    # Reset orchestrator singleton để nó pick up engine mới của test này
    reset_pipeline_orchestrator()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    reset_file_storage()


# ──────────────────────────────────────────────────────────────────────────────
# Helpers — mock Keycloak token (no /auth/login endpoint anymore)
# ──────────────────────────────────────────────────────────────────────────────


def _auth_headers(
    make_keycloak_token: Any,
    *,
    role: str = "OPERATOR",
    user_id: str = "usr_test_operator",
    email: str = "operator@vgr.vn",
    display_name: str = "Operator",
    tenant_id: str = "tenant_vgr_01",
) -> dict[str, str]:
    """Tạo headers với Bearer Keycloak token cho test."""
    token = make_keycloak_token(
        user_id=user_id,
        tenant_id=tenant_id,
        email=email,
        display_name=display_name,
        role=role,
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": tenant_id,
    }


def _pdf_bytes(content: str = "PDF stub content") -> bytes:
    """Tạo PDF stub bytes — không cần format PDF thật vì StubAI trả về canned."""
    return make_pdf(marker=content)


async def _create_dossier(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    name: str,
    annexes: int = 0,
) -> dict[str, Any]:
    """POST /dossiers (multipart) — endpoint tạo hồ sơ duy nhất."""
    files: list[tuple[str, Any]] = [
        (
            "contract",
            ("contract.pdf", io.BytesIO(_pdf_bytes(f"{name} contract")), "application/pdf"),
        ),
        ("metadata", (None, json.dumps({"name": name}))),
    ]
    for index in range(1, annexes + 1):
        files.append(
            (
                "annexes",
                (
                    f"phuluc-{index:02d}.pdf",
                    io.BytesIO(_pdf_bytes(f"{name} annex {index}")),
                    "application/pdf",
                ),
            )
        )
    resp = await client.post("/api/v1/dossiers", headers=headers, files=files)
    assert resp.status_code == 202, f"got {resp.status_code}: {resp.text}"
    data: dict[str, Any] = resp.json()["data"]
    return data


async def _documents(
    client: AsyncClient, headers: dict[str, str], dossier_id: str
) -> list[dict[str, Any]]:
    resp = await client.get(f"/api/v1/dossiers/{dossier_id}/documents", headers=headers)
    assert resp.status_code == 200, resp.text
    rows: list[dict[str, Any]] = resp.json()["data"]
    return rows


def _roles(documents: list[dict[str, Any]]) -> list[str]:
    return sorted(str(doc["role"]).lower() for doc in documents)


async def _contract_document_id(client: AsyncClient, headers: dict[str, str], *, name: str) -> str:
    dossier = await _create_dossier(client, headers, name=name)
    documents = await _documents(client, headers, dossier["dossier_id"])
    return next(str(doc["id"]) for doc in documents if str(doc["role"]).lower() == "contract")


async def _trigger_run(client: AsyncClient, headers: dict[str, str], *, name: str) -> str:
    dossier = await _create_dossier(client, headers, name=name)
    resp = await client.post(
        f"/api/v1/dossiers/{dossier['dossier_id']}/runs", headers=headers, json={}
    )
    assert resp.status_code == 202, f"got {resp.status_code}: {resp.text}"
    return str(resp.json()["data"]["run_id"])


# ──────────────────────────────────────────────────────────────────────────────
# Tests — Dossier upload flow
# ──────────────────────────────────────────────────────────────────────────────


class TestDossierUpload:
    @pytest.mark.asyncio
    async def test_upload_dossier_with_contract_only(
        self, client: AsyncClient, make_keycloak_token: Any
    ) -> None:
        """POST /dossiers với 1 contract file → 202 + dossier_id + job_id."""
        headers = _auth_headers(make_keycloak_token, role="OPERATOR")

        data = await _create_dossier(client, headers, name="Hop dong so 12/2026")

        assert data["dossier_id"].startswith("dos_")
        assert data["job_id"] is not None
        documents = await _documents(client, headers, data["dossier_id"])
        assert _roles(documents) == ["contract"]

    @pytest.mark.asyncio
    async def test_upload_dossier_with_contract_and_annexes(
        self, client: AsyncClient, make_keycloak_token: Any
    ) -> None:
        """POST /dossiers với contract + 2 annex files."""
        headers = _auth_headers(make_keycloak_token, role="OPERATOR")

        data = await _create_dossier(client, headers, name="Dossier with annexes", annexes=2)

        documents = await _documents(client, headers, data["dossier_id"])
        assert _roles(documents) == ["annex", "annex", "contract"]

    @pytest.mark.asyncio
    async def test_upload_without_contract_file_returns_400(
        self, client: AsyncClient, make_keycloak_token: Any
    ) -> None:
        """Thiếu contract → 422 (Pydantic validation) hoặc 400."""
        headers = _auth_headers(make_keycloak_token, role="OPERATOR")
        resp = await client.post(
            "/api/v1/dossiers",
            headers=headers,
            files={"metadata": (None, json.dumps({"name": "No file"}))},
        )
        assert resp.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_upload_allowed_for_administrator(
        self, client: AsyncClient, make_keycloak_token: Any
    ) -> None:
        """ADMINISTRATOR kế thừa quyền upload của OPERATOR."""
        headers = _auth_headers(make_keycloak_token, role="ADMINISTRATOR")
        data = await _create_dossier(client, headers, name="Admin upload")
        assert data["dossier_id"].startswith("dos_")

    @pytest.mark.asyncio
    async def test_upload_reviewer_role_forbidden(
        self, client: AsyncClient, make_keycloak_token: Any
    ) -> None:
        """REVIEWER không có quyền upload (chỉ OPERATOR, ADMINISTRATOR)."""
        headers = _auth_headers(make_keycloak_token, role="REVIEWER")
        resp = await client.post(
            "/api/v1/dossiers",
            headers=headers,
            files={
                "contract": ("x.pdf", io.BytesIO(_pdf_bytes()), "application/pdf"),
                "metadata": (None, json.dumps({"name": "Reviewer upload"})),
            },
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_legacy_upload_endpoint_is_gone(
        self, client: AsyncClient, make_keycloak_token: Any
    ) -> None:
        """POST /dossiers/upload (pipeline in-process cũ) đã bị gỡ."""
        headers = _auth_headers(make_keycloak_token, role="OPERATOR")
        resp = await client.post(
            "/api/v1/dossiers/upload",
            headers=headers,
            data={"name": "Legacy"},
            files={"contract_file": ("x.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
        )
        assert resp.status_code in (404, 405)


# ──────────────────────────────────────────────────────────────────────────────
# Tests — AI service health proxy
# ──────────────────────────────────────────────────────────────────────────────


class TestAiServiceHealth:
    @pytest.mark.asyncio
    async def test_backend_healthz(self, client: AsyncClient) -> None:
        """GET /api/v1/healthz — liveness."""
        resp = await client.get("/api/v1/healthz")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_backend_readyz(self, client: AsyncClient) -> None:
        """GET /api/v1/readyz — readiness (DB + AI)."""
        resp = await client.get("/api/v1/readyz")
        # 200 OK hoặc 503 Service Unavailable
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            body = resp.json()
            assert "checks" in body["data"]

    @pytest.mark.asyncio
    async def test_ai_get_job_status_stub(
        self, client: AsyncClient, make_keycloak_token: Any
    ) -> None:  # noqa: E501
        """GET /api/v1/ai/jobs/{id} — proxy qua StubAI."""
        # Trước submit 1 job qua reocr để có job_id
        headers = _auth_headers(make_keycloak_token, role="OPERATOR")
        doc_id = await _contract_document_id(client, headers, name="Setup for reocr")

        # Submit reocr
        reocr = await client.post(
            f"/api/v1/documents/{doc_id}/re-ocr",
            headers=headers,
            json={
                "profile": "high_res_binarize",
                "page_numbers": [1],
                "reason": "test reocr",
            },
        )
        assert reocr.status_code == 202
        job_id = reocr.json()["data"]["job_id"]
        assert job_id is not None

        # Proxy qua AI service proxy
        resp = await client.get(
            f"/api/v1/ai/jobs/{job_id}",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["job_id"] == job_id


# ──────────────────────────────────────────────────────────────────────────────
# Tests — Re-OCR async submission
# ──────────────────────────────────────────────────────────────────────────────


class TestReOcrAsync:
    @pytest.mark.asyncio
    async def test_reocr_submit_returns_job_id(
        self, client: AsyncClient, make_keycloak_token: Any
    ) -> None:  # noqa: E501
        """POST /documents/{id}/re-ocr trả job_id async."""
        headers = _auth_headers(make_keycloak_token, role="OPERATOR")
        doc_id = await _contract_document_id(client, headers, name="Dossier for reocr")

        # Submit re-OCR
        resp = await client.post(
            f"/api/v1/documents/{doc_id}/re-ocr",
            headers=headers,
            json={
                "profile": "high_res_binarize",
                "page_numbers": [1, 2],
                "reason": "OCR bị mờ ở điều khoản thanh toán",
            },
        )
        assert resp.status_code == 202
        data = resp.json()["data"]
        assert data["document_id"] == doc_id
        assert data["profile"] == "high_res_binarize"
        assert data["status"] in ("pending", "processing", "completed")
        assert data["job_id"] is not None
        assert "ai_job_" in data["job_id"]

    @pytest.mark.asyncio
    async def test_reocr_get_request_status(
        self, client: AsyncClient, make_keycloak_token: Any
    ) -> None:  # noqa: E501
        """GET /re-ocr-requests/{id} — poll status."""
        headers = _auth_headers(make_keycloak_token, role="OPERATOR")
        doc_id = await _contract_document_id(client, headers, name="Reocr status")

        reocr = await client.post(
            f"/api/v1/documents/{doc_id}/re-ocr",
            headers=headers,
            json={
                "profile": "table_optimized",
                "page_numbers": [1],
                "reason": "test",
            },
        )
        assert reocr.status_code == 202
        request_id = reocr.json()["data"]["id"]

        # Đợi 1s để background polling complete (stub trả ngay)
        await asyncio.sleep(0.5)

        resp = await client.get(
            f"/api/v1/re-ocr-requests/{request_id}",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["id"] == request_id


# ──────────────────────────────────────────────────────────────────────────────
# Tests — Pipeline run lifecycle
# ──────────────────────────────────────────────────────────────────────────────


class TestPipelineRun:
    @pytest.mark.asyncio
    async def test_trigger_run_queues_run_and_hands_it_to_worker(
        self, client: AsyncClient, make_keycloak_token: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:  # noqa: E501
        """POST /runs chỉ xếp hàng run + publish dossier.uploaded; pipeline chạy ở Kafka worker."""
        from contract_intelligence.extraction.interfaces.api import dependencies

        published: list[tuple[str, dict[str, Any]]] = []

        async def fake_publish(topic: str, message: dict[str, Any], **_: Any) -> None:
            published.append((topic, message))

        monkeypatch.setattr(dependencies.messaging, "publish_event", fake_publish)
        headers = _auth_headers(make_keycloak_token, role="OPERATOR")
        run_id = await _trigger_run(client, headers, name="Pipeline test")

        resp = await client.get(f"/api/v1/runs/{run_id}", headers=headers)
        assert resp.status_code == 200
        run = resp.json()["data"]
        # Nothing runs in the API process: the run waits for the Kafka worker.
        assert run["status"] == "queued"
        # The upload publishes its own event first; the trigger adds the hand-off.
        assert published[-1] == (
            "dossier_events",
            {"event": "dossier.uploaded", "dossier_id": run["dossier_id"]},
        )

    @pytest.mark.asyncio
    async def test_pipeline_run_steps_endpoint(
        self, client: AsyncClient, make_keycloak_token: Any
    ) -> None:  # noqa: E501
        """GET /runs/{id}/steps trả về 11 steps S0..S10."""
        headers = _auth_headers(make_keycloak_token, role="OPERATOR")
        run_id = await _trigger_run(client, headers, name="Steps test")

        # Đợi pipeline chạy
        await asyncio.sleep(2.0)

        resp = await client.get(
            f"/api/v1/runs/{run_id}/steps",
            headers=headers,
        )
        assert resp.status_code == 200
        steps = resp.json()["data"]
        # 11 steps S0..S10
        assert len(steps) == 11
        step_codes = {s["step"] for s in steps}
        assert step_codes == {f"S{i}" for i in range(11)}


# ──────────────────────────────────────────────────────────────────────────────
# Tests — SSE events
# ──────────────────────────────────────────────────────────────────────────────


class TestSseEvents:
    @pytest.mark.asyncio
    async def test_sse_stream_runs_events(
        self, client: AsyncClient, make_keycloak_token: Any
    ) -> None:  # noqa: E501
        """GET /runs/{id}/events stream SSE events."""
        headers = _auth_headers(make_keycloak_token, role="OPERATOR")
        run_id = await _trigger_run(client, headers, name="SSE test")
        # No Kafka worker runs in tests, so the run would stay queued and the
        # stream never end (ASGITransport buffers the whole body). Cancel it:
        # the stream then closes with run.completed.
        resp = await client.post(f"/api/v1/runs/{run_id}/cancel", headers=headers)
        assert resp.status_code == 200, resp.text

        # Mở SSE stream — đọc tối đa 5 giây
        events_received = []
        try:
            async with client.stream(
                "GET",
                f"/api/v1/runs/{run_id}/events",
                headers=headers,
                timeout=5.0,
            ) as resp:
                assert resp.status_code == 200
                assert resp.headers["content-type"].startswith("text/event-stream")

                async for line in resp.aiter_lines():
                    if line.startswith("event:"):
                        events_received.append(line)
                    if "run.completed" in line or len(events_received) > 20:
                        break
        except Exception:
            # Timeout OK — pipeline có thể đã chạy xong trước khi stream đọc
            pass

        # Ít nhất phải có event "run.started"
        # (run.completed có thể đến sau khi stream đóng)
        assert any("run.started" in e for e in events_received), (
            f"expected run.started event, got: {events_received}"
        )

    @pytest.mark.asyncio
    async def test_sse_stream_replays_cancel_and_closes(
        self, client: AsyncClient, make_keycloak_token: Any
    ) -> None:
        """Cancel lands in run_event; the stream replays it with an id and closes."""
        headers = _auth_headers(make_keycloak_token, role="OPERATOR")
        run_id = await _trigger_run(client, headers, name="SSE replay test")
        resp = await client.post(f"/api/v1/runs/{run_id}/cancel", headers=headers)
        assert resp.status_code == 200, resp.text

        resp = await client.get(f"/api/v1/runs/{run_id}/events", headers=headers, timeout=5.0)
        assert resp.status_code == 200
        body = resp.text
        assert "event: run.started" in body
        assert '"status": "cancelled"' in body
        assert body.rstrip().splitlines()[-2] == "event: run.completed"
        ids = [int(line[4:]) for line in body.splitlines() if line.startswith("id: ")]
        assert ids and ids == sorted(ids)

        # Resuming after the last id replays nothing but still reports completion.
        resp = await client.get(
            f"/api/v1/runs/{run_id}/events",
            headers={**headers, "Last-Event-ID": str(ids[-1])},
            timeout=5.0,
        )
        assert resp.status_code == 200
        assert "id: " not in resp.text
        assert "event: run.completed" in resp.text

    @pytest.mark.asyncio
    async def test_sse_stream_refuses_unknown_run_and_other_users(
        self, client: AsyncClient, make_keycloak_token: Any
    ) -> None:
        owner = _auth_headers(make_keycloak_token, role="OPERATOR")
        run_id = await _trigger_run(client, owner, name="SSE access test")

        resp = await client.get("/api/v1/runs/run_does_not_exist/events", headers=owner)
        assert resp.status_code == 404

        stranger = _auth_headers(
            make_keycloak_token,
            role="OPERATOR",
            user_id="usr_test_stranger",
            email="stranger@vgr.vn",
            display_name="Stranger",
        )
        resp = await client.get(f"/api/v1/runs/{run_id}/events", headers=stranger)
        assert resp.status_code == 403

        other_tenant = _auth_headers(
            make_keycloak_token,
            role="OPERATOR",
            user_id="usr_test_other_tenant",
            email="other@vgr.vn",
            tenant_id="tenant_vgr_02",
        )
        resp = await client.get(f"/api/v1/runs/{run_id}/events", headers=other_tenant)
        assert resp.status_code == 404
