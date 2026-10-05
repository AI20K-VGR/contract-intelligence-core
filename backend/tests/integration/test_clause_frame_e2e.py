"""Actual AI HTTP/PG persistence and backend HITL run fence; synthetic data only."""

import copy
import os
import socket
import subprocess
import time
from contextlib import contextmanager
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from tests.integration.test_clause_frame_review_flow import (
    semantic_case,
    semantic_reviewer,
    semantic_route_client,
)
from tests.integration.test_clause_frame_roundtrip import (
    ROOT,
    SECRET,
    TENANT,
    ai_http,
    poll,
    signed,
)

from contract_intelligence.contract.infrastructure.persistence.orm import JobORM
from contract_intelligence.extraction.infrastructure.persistence.orm import PipelineRunORM
from contract_intelligence.review.infrastructure.persistence.orm import (
    ReviewActionORM,
    ReviewItemORM,
)

__all__ = ["ai_http", "semantic_case"]


@contextmanager
def producer_off(raw: str):
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
        AI2_SEMANTIC_ENABLED="false",
        AI2_PROCESSING_EGRESS_ALLOWED="false",
        AI2_QUERY_EGRESS_ALLOWED="false",
        AI2_LLM_API_KEY="",
        OPENAI_API_KEY="",
    )
    process = subprocess.Popen(
        [
            str(ROOT / "ai-service/.venv-ai2-frame/Scripts/python.exe"),
            "-m",
            "uvicorn",
            "app.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT / "ai-service",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(120):
            assert process.poll() is None, "producer-off HTTP process exited"
            try:
                if httpx.get(base + "/health", timeout=0.5).status_code == 200:
                    break
            except httpx.TransportError:
                pass
            time.sleep(0.1)
        else:
            pytest.fail("producer-off HTTP readiness timed out")
        yield base
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.mark.asyncio
async def test_old_run_action_rejected_without_mutating_review(semantic_case: Any) -> None:
    factory, request, _ = semantic_case
    run, dossier = request["task_id"], request["dossier_id"]
    async with factory() as session:
        item = await session.scalar(select(ReviewItemORM).where(ReviewItemORM.run_id == run))
        assert item is not None
        item_id, version, status = item.id, item.version, item.status
        job = await session.scalar(select(JobORM).where(JobORM.dossier_id == dossier))
        assert job is not None
        pending = run + "-replacement"
        session.add(
            PipelineRunORM(
                id=pending,
                tenant_id=TENANT,
                dossier_id=dossier,
                job_id=job.id,
                status="running",
                pipeline_version="test-v1",
            )
        )
        job.current_run_id = pending
        await session.commit()
    async with semantic_route_client(factory, semantic_reviewer()) as client:
        response = await client.post(
            f"/api/v1/review-items/{item_id}/actions",
            json={"action": "confirm", "base_version": version},
        )
        assert response.status_code == 409, response.text
    async with factory() as session:
        item = await session.get(ReviewItemORM, item_id)
        assert (item.version, item.status) == (version, status)
        count = await session.scalar(
            select(func.count())
            .select_from(ReviewActionORM)
            .where(
                ReviewActionORM.review_item_id == item_id,
            )
        )
        assert count == 0


@pytest.mark.asyncio
async def test_actual_producer_off_rollback_retains_prior_result(
    semantic_case: Any, ai_http: Any
) -> None:
    from contract_intelligence.shared.ai.persistence import (
        load_ai2_read_model,
        persist_ai2_processing_result,
    )

    factory, request, original = semantic_case
    _, _, raw = ai_http
    replacement = copy.deepcopy(request)
    for key in ("task_id", "request_id", "idempotency_key"):
        replacement[key] += "-rollback"
    replacement["service_envelope"] = signed(replacement)
    with producer_off(raw) as base:
        response = httpx.post(base + "/jobs/idp", json=replacement, timeout=10)
        assert response.status_code == 202, response.text
        rolled_back = poll(base, replacement, response.json()["job_id"])
    assert rolled_back["status"] == "SUCCEEDED"
    assert rolled_back["result"].get("semantic_extension") is None
    async with factory() as session:
        job = await session.scalar(select(JobORM).where(JobORM.dossier_id == request["dossier_id"]))
        session.add(
            PipelineRunORM(
                id=replacement["task_id"],
                tenant_id=TENANT,
                dossier_id=request["dossier_id"],
                job_id=job.id,
                status="running",
                pipeline_version="test-v1",
            )
        )
        await session.flush()
        await persist_ai2_processing_result(
            session,
            tenant_id=TENANT,
            dossier_id=request["dossier_id"],
            result=rolled_back,
            run_id=replacement["task_id"],
        )
        job.current_run_id = replacement["task_id"]
        await session.commit()
    async with semantic_route_client(factory, semantic_reviewer()) as client:
        response = await client.get(f"/api/v1/dossiers/{request['dossier_id']}/semantic-results")
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["run_id"] == replacement["task_id"]
        assert data["state"] == "NOT_MEASURED"
        assert data["semantic_extension"] is None
    async with factory() as session:
        old = await load_ai2_read_model(session, tenant_id=TENANT, run_id=request["task_id"])
        assert (
            old.payload["result"]["semantic_extension"] == original["result"]["semantic_extension"]
        )
