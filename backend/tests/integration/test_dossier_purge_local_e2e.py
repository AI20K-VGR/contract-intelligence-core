"""Local-only real HTTP + migrated PostgreSQL controls for issue #131.

Set AI2_PURGE_TEST_DATABASE_URL to a dedicated PostgreSQL database whose Backend
migrations are at head. No SQLite and no production data are used by this suite.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import socket
import subprocess
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tests.unit.conftest_contract import FakeFileStorage

from contract_intelligence.config.settings import get_settings
from contract_intelligence.contract.infrastructure.persistence.orm import DocumentORM, DossierORM
from contract_intelligence.extraction.infrastructure.persistence.orm import OcrLineORM
from contract_intelligence.infrastructure.ai_adapters import _service_envelope
from contract_intelligence.shared.ai.client import HttpAiServiceClient
from contract_intelligence.shared.persistence import bind_engine, reset_engine
from contract_intelligence.shared.persistence.session import get_async_session
from contract_intelligence.shared.storage import (
    get_file_storage,
    reset_file_storage,
    set_file_storage,
)

pytestmark = [pytest.mark.ai2_local_e2e, pytest.mark.asyncio]
ROOT = Path(__file__).resolve().parents[3]
SECRET = "issue131-local-e2e-only"
TENANT = "tenant_vgr_01"


@pytest_asyncio.fixture
async def purge_stack(tmp_path, monkeypatch):
    raw = os.getenv("AI2_PURGE_TEST_DATABASE_URL")
    if not raw:
        pytest.skip("Requires dedicated local AI2_PURGE_TEST_DATABASE_URL")
    parsed = make_url(raw)
    assert parsed.get_backend_name() == "postgresql"
    engine = create_async_engine(parsed.set(drivername="postgresql+asyncpg"))
    with socket.socket() as binding:
        binding.bind(("127.0.0.1", 0))
        port = binding.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    env = dict(
        os.environ,
        AI2_DATABASE_URL=parsed.set(drivername="postgresql+psycopg").render_as_string(
            hide_password=False
        ),
        AI2_REQUIRE_DATABASE="true",
        AI2_SERVICE_HMAC_SECRET=SECRET,
        AI2_PROCESSING_EGRESS_ALLOWED="false",
        AI2_QUERY_EGRESS_ALLOWED="false",
        AI2_LLM_API_KEY="",
        OPENAI_API_KEY="",
        AI2_DATA_DIR=str(tmp_path / "ai2"),
    )
    command = [
        str(ROOT / "ai-service/.venv/Scripts/python.exe"),
        "-m",
        "uvicorn",
        "app.api.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]

    def start():
        return subprocess.Popen(
            command,
            cwd=ROOT / "ai-service",
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

    async def ready():
        async with httpx.AsyncClient(trust_env=False, timeout=1) as client:
            for _ in range(200):
                assert process.poll() is None, "AI2 local HTTP process exited"
                try:
                    if (await client.get(base + "/healthz")).status_code == 200:
                        return
                except httpx.TransportError:
                    pass
                await asyncio.sleep(0.1)
        pytest.fail("AI2 local readiness timeout")

    async def restart():
        nonlocal process
        process.terminate()
        process.wait(timeout=15)
        process = start()
        await ready()

    process = start()
    try:
        await ready()
        settings = get_settings()
        for key, value in {
            "ai2_base_url": base,
            "ai2_service_hmac_secret": SECRET,
            "env": "test",
            "database_url": parsed.set(drivername="postgresql+asyncpg").render_as_string(
                hide_password=False
            ),
            "job_queue_enabled": False,
        }.items():
            monkeypatch.setattr(settings, key, value)
        monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1")
        monkeypatch.setenv("no_proxy", "localhost,127.0.0.1")
        from contract_intelligence.shared.ai import client as ai_clients

        ai_client = HttpAiServiceClient(settings)
        monkeypatch.setattr(ai_clients, "get_ai_service_client", lambda: ai_client)
        bind_engine(engine)
        set_file_storage(FakeFileStorage())
        yield base, engine, settings, restart
        await ai_client.aclose()
    finally:
        process.terminate()
        process.wait(timeout=15)
        reset_engine()
        reset_file_storage()
        await engine.dispose()


def processing_request(dossier):
    body = json.loads(
        (ROOT / "docs/contracts/examples/ai1.snapshot.v1.body.example.json").read_text("utf-8")
    )
    body["dossier_id"] = dossier
    digest = hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    request_id = uuid4().hex
    payload = {
        "schema_version": "be.ai2.processing.request.v1",
        "request_id": request_id,
        "idempotency_key": f"{dossier}:{request_id}",
        "attempt": 1,
        "task_id": "process-dossier",
        "dossier_id": dossier,
        "snapshots": [body],
        "snapshot_identities": [
            {
                "snapshot_id": body["snapshot_id"],
                "snapshot_version": "ai1.snapshot.v1",
                "source_digest": body["source_digest"],
                "snapshot_digest": digest,
            }
        ],
        "dossier_members": [
            {
                "member_id": "body",
                "document_id": body["document_id"],
                "snapshot_id": body["snapshot_id"],
                "role": "body",
                "source_digest": body["source_digest"],
            }
        ],
        "role_relation_map": [],
        "policy_flags": {
            "egress_allowed": False,
            "use_vector": False,
            "budget_limits": {
                "max_processing_seconds": 30,
                "max_llm_calls": 0,
                "max_embedding_tokens": 0,
            },
        },
    }
    payload["service_envelope"] = _service_envelope(
        payload, tenant_id=TENANT, dossier_id=dossier, actor_id="backend"
    )
    return payload


async def process(client, base, dossier):
    response = await client.post(base + "/jobs/idp", json=processing_request(dossier))
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    payload = {"operation": "get_job", "job_id": job_id, "dossier_id": dossier}
    envelope = _service_envelope(payload, tenant_id=TENANT, dossier_id=dossier, actor_id="backend")
    for _ in range(200):
        response = await client.get(
            base + f"/jobs/{job_id}", headers={"X-AI2-Service-Envelope": json.dumps(envelope)}
        )
        assert response.status_code == 200
        if response.json()["status"] in {"SUCCEEDED", "FAILED"}:
            assert response.json()["status"] == "SUCCEEDED", response.json().get("errors")
            return job_id
        await asyncio.sleep(0.05)
    pytest.fail("AI2 processing timeout")


@pytest.mark.parametrize("retry_first", [False, True])
async def test_backend_delete_calls_real_ai2_and_commits_evidence(
    purge_stack,
    make_keycloak_token,
    monkeypatch,
    retry_first,
):
    from contract_intelligence.contract.infrastructure.persistence.dossier_deletion_service import (
        sweep_pending_purges,
    )
    from contract_intelligence.main import app

    base, engine, settings, restart = purge_stack
    dossier, other = "dos_" + uuid4().hex, "dos_" + uuid4().hex
    blob_keys = []
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add_all(
            [
                DossierORM(
                    id=identifier,
                    tenant_id=TENANT,
                    name="Synthetic purge E2E",
                    metadata_json={"created_by": "usr_purge"},
                )
                for identifier in (dossier, other)
            ]
        )
        await session.flush()
        for index in range(2):
            doc_id = "doc_" + uuid4().hex
            key = f"contracts/{doc_id}.pdf"
            blob_keys.append(key)
            await get_file_storage().put(key, BytesIO(b"%PDF synthetic"))
            session.add(
                DocumentORM(
                    id=doc_id,
                    tenant_id=TENANT,
                    dossier_id=dossier,
                    role="contract",
                    order_index=index,
                    filename="synthetic.pdf",
                    sha256=doc_id,
                    blob_uri=key,
                    file_size_bytes=14,
                )
            )
            await session.flush()
            session.add(
                OcrLineORM(
                    id="oln_" + uuid4().hex,
                    tenant_id=TENANT,
                    document_id=doc_id,
                    page_no=1,
                    line_no=1,
                    text="synthetic private OCR",
                    bbox="[0,0,1,1]",
                )
            )
        await session.commit()
    async with httpx.AsyncClient(trust_env=False, timeout=15) as ai:
        deleted_job = await process(ai, base, dossier)
        await process(ai, base, other)

    async def session_override():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_async_session] = session_override
    token = make_keycloak_token(role="ADMINISTRATOR", user_id="usr_purge")
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-Id": TENANT}
    try:
        if retry_first:
            monkeypatch.setattr(settings, "ai2_base_url", "http://127.0.0.1:1")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://backend",
        ) as backend:
            response = await backend.delete(f"/api/v1/dossiers/{dossier}", headers=headers)
            assert response.status_code == 202, response.text
            async with engine.connect() as cx:
                status = (
                    await cx.execute(
                        text("SELECT purge_status FROM dossier WHERE id=:id"), {"id": dossier}
                    )
                ).scalar_one()
                assert status == ("failed" if retry_first else "completed")
                if retry_first:
                    assert (
                        await cx.execute(
                            text("SELECT count(*) FROM ai2.jobs WHERE dossier_id=:id"),
                            {"id": dossier},
                        )
                    ).scalar_one() == 1
            if retry_first:
                monkeypatch.setattr(settings, "ai2_base_url", base)
                await sweep_pending_purges()
            response = await backend.get(f"/api/v1/dossiers/{dossier}", headers=headers)
            assert response.status_code == 404
            assert (
                await backend.delete(f"/api/v1/dossiers/{dossier}", headers=headers)
            ).status_code == 202
        async with engine.connect() as cx:
            ledger = (
                (
                    await cx.execute(
                        text(
                            "SELECT purge_status,evidence FROM deletion_ledger WHERE dossier_id=:id"
                        ),
                        {"id": dossier},
                    )
                )
                .mappings()
                .one()
            )
            assert ledger["purge_status"] == "completed"
            assert ledger["evidence"]["ai2"]["deleted"]["jobs"] == 1
            assert ledger["evidence"]["blob_count"] == 2
            assert (
                await cx.execute(
                    text(
                        "SELECT count(*) FROM document WHERE dossier_id=:id AND filename='[purged]'"
                    ),
                    {"id": dossier},
                )
            ).scalar_one() == 2
            assert (
                await cx.execute(
                    text(
                        "SELECT count(*) FROM ocr_line WHERE document_id IN "
                        "(SELECT id FROM document WHERE dossier_id=:id)"
                    ),
                    {"id": dossier},
                )
            ).scalar_one() == 0
            for table in (
                "jobs",
                "dossier_query_snapshots",
                "contract_edges",
                "contract_pair_relations",
            ):
                assert (
                    await cx.execute(
                        text(
                            f"SELECT count(*) FROM ai2.{table} "
                            "WHERE tenant_id=:t AND dossier_id=:id"
                        ),
                        {"t": TENANT, "id": dossier},
                    )
                ).scalar_one() == 0
            assert (
                await cx.execute(
                    text(
                        "SELECT count(*) FROM ai2.dossier_query_snapshots "
                        "WHERE tenant_id=:t AND dossier_id=:id"
                    ),
                    {"t": TENANT, "id": other},
                )
            ).scalar_one() == 1
        await restart()
        for key in blob_keys:
            assert not await get_file_storage().exists(key)
        async with httpx.AsyncClient(trust_env=False) as ai:
            assert (await ai.get(base + f"/jobs/{deleted_job}")).status_code == 404
            query = {"tenant_id": TENANT, "dossier_id": dossier, "query": "synthetic clause?"}
            query["service_envelope"] = _service_envelope(
                query,
                tenant_id=TENANT,
                dossier_id=dossier,
                actor_id="backend",
                scopes=["ai2.query"],
            )
            assert (await ai.post(base + "/query", json=query)).status_code == 410
            payload = {"tenant_id": TENANT, "dossier_id": dossier}
            payload["service_envelope"] = _service_envelope(
                payload,
                tenant_id=TENANT,
                dossier_id=dossier,
                actor_id="backend",
                scopes=["ai2.dossier.delete"],
            )
            response = await ai.request(
                "DELETE", base + f"/api/v1/dossiers/{dossier}", json=payload
            )
            assert response.status_code == 200
            assert not any(response.json()["deleted"].values())
            assert response.json()["evidence"]["deleted"]["jobs"] == 1
    finally:
        app.dependency_overrides.pop(get_async_session, None)


@pytest.mark.parametrize("retry_first", [False, True])
async def test_historical_completed_ledger_sweeps_real_ai2(purge_stack, monkeypatch, retry_first):
    from contract_intelligence.contract.infrastructure.persistence.deletion_ledger import (
        DeletionLedgerORM,
    )
    from contract_intelligence.contract.infrastructure.persistence.dossier_deletion_service import (
        DossierDeletionService,
        sweep_pending_purges,
    )
    from contract_intelligence.shared.base import utcnow

    base, engine, settings, _ = purge_stack
    dossier = "dos_" + uuid4().hex
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = utcnow()
    async with factory() as session:
        session.add(
            DossierORM(
                id=dossier,
                tenant_id=TENANT,
                name="[deleted]",
                deleted_at=now,
                purge_completed_at=now,
                purge_status="completed",
            )
        )
        session.add(
            DeletionLedgerORM(
                id="led_" + uuid4().hex,
                tenant_id=TENANT,
                dossier_id=dossier,
                requested_by="usr_purge",
                tombstoned_at=now,
                purged_at=now,
                purge_status="completed",
                evidence={"blob_count": 7, "blobs_deleted": 7},
            )
        )
        await session.commit()
    async with httpx.AsyncClient(trust_env=False, timeout=15) as ai:
        await process(ai, base, dossier)
    cleanup = AsyncMock(side_effect=AssertionError("Historical Backend content is already purged"))
    monkeypatch.setattr(DossierDeletionService, "_purge_db_content", cleanup)
    monkeypatch.setattr(DossierDeletionService, "_collect_blob_uris", cleanup)
    if retry_first:
        monkeypatch.setattr(settings, "ai2_base_url", "http://127.0.0.1:1")
        await sweep_pending_purges()
        async with factory() as session:
            row = await session.get(DossierORM, dossier)
            assert row.purge_status == "failed"
            assert row.purge_completed_at is not None
        monkeypatch.setattr(settings, "ai2_base_url", base)
    await sweep_pending_purges()
    await sweep_pending_purges()
    async with engine.connect() as cx:
        ledger = (
            (
                await cx.execute(
                    text("SELECT purge_status,evidence FROM deletion_ledger WHERE dossier_id=:id"),
                    {"id": dossier},
                )
            )
            .mappings()
            .one()
        )
        assert ledger["purge_status"] == "completed"
        assert ledger["evidence"]["blob_count"] == 7
        assert ledger["evidence"]["blobs_deleted"] == 7
        assert ledger["evidence"]["ai2"]["deleted"]["jobs"] == 1
        assert (
            await cx.execute(
                text("SELECT count(*) FROM ai2.jobs WHERE dossier_id=:id"), {"id": dossier}
            )
        ).scalar_one() == 0
    cleanup.assert_not_awaited()
