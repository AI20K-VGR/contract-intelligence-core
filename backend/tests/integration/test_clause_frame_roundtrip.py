"""HTTP thật + PostgreSQL reopen; fixture cơ học, không claim độ đúng hồ sơ thật."""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import os
import socket
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from contract_intelligence.contract.infrastructure.persistence.orm import (
    DocumentORM,
    DossierORM,
    JobORM,
)
from contract_intelligence.extraction.infrastructure.persistence.orm import (
    OcrLineORM,
    PipelineRunORM,
)
from contract_intelligence.shared.ai.persistence import (
    Ai2PersistenceConflict,
    load_ai2_read_model,
    persist_ai2_processing_result,
)
from contract_intelligence.shared.ai.schemas import SemanticProfile
from contract_intelligence.shared.persistence import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models

ROOT = Path(__file__).resolve().parents[3]
SECRET = "frame-roundtrip-test-only"
TENANT = "tenant-frame-test"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def signed(payload, scope="ai2.jobs.submit"):
    clean = {k: v for k, v in payload.items() if k != "service_envelope"}
    now = int(time.time())
    envelope = {
        "schema_version": "ai2.service-envelope.v1",
        "issuer": "backend-service",
        "audience": "vsf-ai2",
        "tenant_id": TENANT,
        "actor_id": "backend",
        "dossier_id": payload["dossier_id"],
        "scopes": [scope],
        "key_id": "default",
        "issued_at": now,
        "expires_at": now + 300,
        "nonce": uuid4().hex,
        "payload_sha256": digest(clean),
    }
    envelope["signature"] = hmac.new(
        SECRET.encode(),
        json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(),
        hashlib.sha256,
    ).hexdigest()
    return envelope


def request_fixture(annex_clause=4):
    uid = uuid4().hex[:12]
    dossier = f"dossier-frame-{uid}"
    snapshots = []
    texts = [
        [
            "Điều 1. Bên A phải thanh toán 9007199254740993 VND",
            "Điều 2. Bên B không được tiết lộ thông tin",
            "Điều 3. Bên A được phép chấm dứt hợp đồng",
            "Giá trị hợp đồng: 100 VND",
        ],
        [
            "Điều 4. Các bên đồng ý sửa đổi Điều 1: Bên A phải thanh toán 101 VND "
            "có hiệu lực từ 2026-10-03"
        ],
    ]
    texts[1][0] = texts[1][0].replace("4.", f"{annex_clause}.", 1)
    for role, rows in zip(("body", "annex"), texts, strict=True):
        snapshot = json.loads(
            (ROOT / "docs/contracts/examples" / f"ai1.snapshot.v1.{role}.example.json").read_text(
                encoding="utf-8"
            )
        )
        snapshot.update(
            dossier_id=dossier, document_id=f"doc-{role}-{uid}", snapshot_id=f"snap-{role}-{uid}"
        )
        page = snapshot["pages"][0]
        page["lines"] = [
            {
                "line_id": f"line-{role}-{i}",
                "raw_text": line,
                "bbox_source": "absent",
                "geometry_status": "absent",
                "words": [],
            }
            for i, line in enumerate(rows)
        ]
        snapshots.append(snapshot)
    profile = {
        "schema_version": "ai2.semantic-profile.v1",
        "capability": "ai2.semantic.v1",
        "tenant_id": TENANT,
        "version": 1,
        "contract_type": "SALES",
        "alias_version": 0,
        "alias_digest": None,
        "aliases": [],
        "activation_state": "DRAFT_ONLY",
        "alias_proposal_minimum_length": None,
        "context_bounds": {
            "max_hops": 2,
            "max_nodes": 10,
            "max_context_tokens": 4000,
            "max_output_tokens": 500,
            "max_llm_calls": 0,
            "max_seconds": 5,
        },
    }
    alias = {
        "source": "tr\u1ea3 ti\u1ec1n",
        "symbol": "PAY",
        "kind": "action",
        "proposal_id": "synthetic-approved-alias",
    }
    texts_alias = texts[0][0].replace("thanh to\u00e1n", alias["source"])
    snapshots[0]["pages"][0]["lines"][0]["raw_text"] = texts_alias
    profile.update(
        aliases=[alias],
        alias_version=7,
        activation_state="ACTIVE",
        alias_digest=digest({"tenant_id": TENANT, "version": 7, "aliases": [alias]}),
    )
    profile["digest"] = digest(profile)
    SemanticProfile.model_validate(profile)
    request = {
        "schema_version": "be.ai2.processing.request.v1",
        "request_id": f"req-{uid}",
        "idempotency_key": f"idem-{uid}",
        "attempt": 1,
        "task_id": f"run-{uid}",
        "dossier_id": dossier,
        "snapshots": snapshots,
        "snapshot_identities": [
            {
                "snapshot_id": s["snapshot_id"],
                "snapshot_version": "ai1.snapshot.v1",
                "source_digest": s["source_digest"],
                "snapshot_digest": digest(s),
            }
            for s in snapshots
        ],
        "dossier_members": [
            {
                "member_id": f"member-{i}-{uid}",
                "document_id": s["document_id"],
                "snapshot_id": s["snapshot_id"],
                "role": "body" if i == 0 else "annex",
                "source_digest": s["source_digest"],
            }
            for i, s in enumerate(snapshots)
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
        "semantic_profile": profile,
    }
    request["service_envelope"] = signed(request)
    return request


@pytest.fixture
def ai_http():
    raw = os.environ.get("AI2_FRAME_TEST_DATABASE_URL")
    if not raw:
        pytest.fail("AI2_FRAME_TEST_DATABASE_URL phải có PostgreSQL dùng riêng; không skip")
    if make_url(raw).get_backend_name() != "postgresql":
        pytest.fail("P4 requires real PostgreSQL")
    ai_root = ROOT / "ai-service"
    python = ai_root / ".venv-ai2-frame/Scripts/python.exe"
    with socket.socket() as binding:
        binding.bind(("127.0.0.1", 0))
        port = binding.getsockname()[1]
    env = dict(
        os.environ,
        AI2_DATABASE_URL=make_url(raw)
        .set(drivername="postgresql+psycopg")
        .render_as_string(hide_password=False),
        AI2_REQUIRE_DATABASE="true",
        AI2_SERVICE_HMAC_SECRET=SECRET,
        AI2_PROCESSING_EGRESS_ALLOWED="false",
        AI2_SEMANTIC_ENABLED="true",
        AI2_LLM_API_KEY="",
        OPENAI_API_KEY="",
        AI2_QUERY_EGRESS_ALLOWED="false",
        AI2_SEMANTIC_CONTEXT_CAPS=json.dumps(
            request_fixture()["semantic_profile"]["context_bounds"]
        ),
    )

    def start():
        return subprocess.Popen(
            [
                str(python),
                "-B",
                "-m",
                "uvicorn",
                "app.api.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=ai_root,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

    process = start()
    base = f"http://127.0.0.1:{port}"

    def ready():
        for _ in range(120):
            if process.poll() is not None:
                pytest.fail("AI2 test HTTP process exited")
            try:
                if httpx.get(base + "/health", timeout=0.5).status_code == 200:
                    return
            except httpx.TransportError:
                pass
            time.sleep(0.1)
        pytest.fail("AI2 test HTTP readiness timeout")

    ready()

    def restart():
        nonlocal process
        process.terminate()
        process.wait(timeout=10)
        process = start()
        ready()

    try:

        class IsolatedFixture:
            def __repr__(self):
                return "<isolated HTTP/PG fixture>"

            def __iter__(self):
                yield base
                yield restart
                yield raw

        yield IsolatedFixture()
    finally:
        process.terminate()
        process.wait(timeout=10)


def poll(base, request, job_id):
    query = {"operation": "get_job", "job_id": job_id, "dossier_id": request["dossier_id"]}
    headers = {"X-AI2-Service-Envelope": json.dumps(signed(query))}
    for _ in range(100):
        response = httpx.get(base + f"/jobs/{job_id}", headers=headers, timeout=5)
        assert response.status_code == 200
        result = response.json()
        if result["status"] in {"SUCCEEDED", "FAILED"}:
            return result
        time.sleep(0.05)
    pytest.fail("AI2 job poll timeout")


@pytest.mark.asyncio
@pytest.mark.parametrize("annex_clause", [1, 4])
async def test_actual_http_pg_reopen_semantic_fields_retry_and_scope(ai_http, annex_clause):
    base, restart, raw = ai_http
    request = request_fixture(annex_clause)
    response = httpx.post(base + "/jobs/idp", json=request, timeout=10)
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    result = poll(base, request, job_id)
    assert result["status"] == "SUCCEEDED", result["errors"]
    extension = result["result"]["semantic_extension"]
    assert extension["frames"] and extension["pairs"] and extension["rows"]
    assert (
        extension["alias_version"] == 7
        and extension["alias_digest"] == request["semantic_profile"]["alias_digest"]
    )
    assert any(pair["method"] == "TENANT_ALIAS" for pair in extension["pairs"])
    assert any(
        frame["key"]["alias_proposal_ids"] == ["synthetic-approved-alias"]
        for frame in extension["frames"]
    )

    assert any(
        slot["value"] == "9007199254740993" and slot["value_type"] == "DECIMAL"
        for frame in extension["frames"]
        for slot in frame["slots"].values()
    )
    assert {"OBLIGATION", "RIGHT", "PROHIBITION", "PARAMETER"}.issubset(
        {frame["family"] for frame in extension["frames"]}
    )
    amendments = [edge for edge in extension["timeline"] if edge["proposed_value"] is not None]
    assert amendments, extension["timeline"]
    assert any(
        edge["relation"] == "AMENDS"
        and edge["date_role"] == "EFFECTIVE"
        and edge["date_value"] == "2026-10-03"
        and edge["proposed_value"]["value"] == "101"
        and edge["review_state"] == "NEEDS_REVIEW"
        for edge in amendments
    )
    fixture_output = os.environ.get("AI2_FRAME_FIXTURE_OUTPUT")
    if fixture_output:
        Path(fixture_output).write_text(
            json.dumps(extension, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    restart()
    assert poll(base, request, job_id) == result
    assert httpx.post(base + "/jobs/idp", json=request, timeout=10).json()["job_id"] == job_id
    changed = copy.deepcopy(request)
    changed["task_id"] += "-changed"
    changed["service_envelope"] = signed(changed)
    assert httpx.post(base + "/jobs/idp", json=changed, timeout=10).status_code == 409
    import_all_models()
    url = make_url(raw).set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)
    engine = create_async_engine(url, hide_parameters=True)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    run_id = request["task_id"]
    async with factory() as session:
        session.add(
            DossierORM(id=request["dossier_id"], tenant_id=TENANT, name="synthetic mechanics")
        )
        session.add(JobORM(id=f"job-{run_id}", tenant_id=TENANT, dossier_id=request["dossier_id"]))
        await session.flush()
        session.add(
            PipelineRunORM(
                id=run_id,
                tenant_id=TENANT,
                dossier_id=request["dossier_id"],
                job_id=f"job-{run_id}",
                status="running",
                pipeline_version="v1",
                config_snapshot=json.dumps({"semantic_profile": request["semantic_profile"]}),
            )
        )
        for member in request["dossier_members"]:
            session.add(
                DocumentORM(
                    id=member["document_id"],
                    tenant_id=TENANT,
                    dossier_id=request["dossier_id"],
                    role="CONTRACT" if member["role"] == "body" else "ANNEX",
                    filename="synthetic.pdf",
                    sha256=member["source_digest"],
                )
            )
        for snapshot in request["snapshots"]:
            offset = 0
            for page in snapshot["pages"]:
                for line_no, line in enumerate(page["lines"]):
                    raw_text = line["raw_text"]
                    session.add(
                        OcrLineORM(
                            id=f"ocr-{snapshot['document_id']}-{line_no}",
                            tenant_id=TENANT,
                            document_id=snapshot["document_id"],
                            page_no=1,
                            line_no=line_no,
                            text=raw_text,
                            bbox="[]",
                            confidence=None,
                            doc_char_start=offset,
                            doc_char_end=offset + len(raw_text),
                        )
                    )
                    offset += len(raw_text) + 1
        await session.commit()
        stored = await persist_ai2_processing_result(
            session,
            tenant_id=TENANT,
            dossier_id=request["dossier_id"],
            result=result,
            run_id=run_id,
        )
        await session.commit()
        assert stored["evidence_ready"] is False and stored["review_items"] > 0
    await engine.dispose()
    engine = create_async_engine(url, hide_parameters=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        loaded = await load_ai2_read_model(session, tenant_id=TENANT, run_id=run_id)
        assert loaded.payload["result"]["semantic_extension"] == extension
        if fixture_output:
            Path(fixture_output).with_name("p4-semantic-reloaded-2021.json").write_text(
                json.dumps(
                    loaded.payload["result"]["semantic_extension"], ensure_ascii=False, indent=2
                ),
                encoding="utf-8",
            )
        amendment_findings = (
            (
                await session.execute(
                    text(
                        "SELECT disposition FROM finding "
                        "WHERE tenant_id=:tenant AND key_or_topic=:topic"
                    ),
                    {"tenant": TENANT, "topic": amendments[0]["edge_id"]},
                )
            )
            .scalars()
            .all()
        )
        assert amendment_findings == ["candidate_amendment"]
        methods = (
            (
                await session.execute(
                    text("SELECT method FROM finding WHERE tenant_id=:tenant"), {"tenant": TENANT}
                )
            )
            .scalars()
            .all()
        )
        assert "TENANT_ALIAS" in methods

        citation_digests = (
            (
                await session.execute(
                    text(
                        "SELECT c.quote_sha256 FROM citation c "
                        "JOIN finding_side s ON s.citation_id=c.id "
                        "WHERE s.tenant_id=:tenant AND s.value_snapshot IS NOT NULL"
                    ),
                    {"tenant": TENANT},
                )
            )
            .scalars()
            .all()
        )
        assert citation_digests and all(len(value) == 64 for value in citation_digests)

        sides = (
            (
                await session.execute(
                    text("SELECT value_snapshot FROM finding_side WHERE tenant_id=:tenant"),
                    {"tenant": TENANT},
                )
            )
            .scalars()
            .all()
        )
        assert any(
            json.loads(side)["semantic"]["frame"]["slots"]["amount"]["value"] == "9007199254740993"
            for side in sides
            if side
        )
        assert (
            await persist_ai2_processing_result(
                session,
                tenant_id=TENANT,
                dossier_id=request["dossier_id"],
                result=result,
                run_id=run_id,
            )
        )["idempotent_replay"]
        with pytest.raises(LookupError):
            await load_ai2_read_model(session, tenant_id="other-tenant", run_id=run_id)
        bad = copy.deepcopy(result)
        bad["result"]["semantic_extension"]["profile_digest"] = "f" * 64
        with pytest.raises(Ai2PersistenceConflict):
            await persist_ai2_processing_result(
                session,
                tenant_id=TENANT,
                dossier_id=request["dossier_id"],
                result=bad,
                run_id=run_id,
            )
    await engine.dispose()
