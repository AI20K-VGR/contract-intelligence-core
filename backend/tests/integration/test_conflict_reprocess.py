"""Run creation contract required for safe semantic reprocessing."""

import asyncio
import hashlib
import json

import pytest
from sqlalchemy import func, select, update
from tests.integration.test_clause_frame_e2e import ai_http, semantic_case  # noqa: F401, F811
from tests.integration.test_clause_frame_review_flow import (
    semantic_reviewer,
    semantic_route_client,
)

from contract_intelligence.contract.infrastructure.persistence.orm import DocumentORM, JobORM
from contract_intelligence.extraction.application.services.extraction_service import (
    ReprocessRequestConflict,
)
from contract_intelligence.extraction.infrastructure.persistence.orm import PipelineRunORM
from contract_intelligence.extraction.infrastructure.persistence.repository_impl import (
    PipelineRunRepositoryImpl,
)
from contract_intelligence.extraction.interfaces.api import dependencies as extraction_dependencies
from contract_intelligence.main import app
from contract_intelligence.shared.storage import get_file_storage

__all__ = ["ai_http"]


def test_existing_reprocess_route_accepts_an_idempotency_key() -> None:
    schema = app.openapi()
    operation = schema["paths"]["/api/v1/dossiers/{dossier_id}/reprocess"]["post"]
    parameters = operation.get("parameters", [])

    assert any(
        parameter.get("in") == "header"
        and str(parameter.get("name", "")).casefold() == "idempotency-key"
        for parameter in parameters
    ), "existing reprocess route must bind the request to a stable idempotency key"
    request_body = operation.get("requestBody", {})
    assert request_body.get("required") is True
    body_ref = request_body["content"]["application/json"]["schema"]["$ref"]
    body_name = body_ref.rsplit("/", 1)[-1]
    body_schema = schema["components"]["schemas"][body_name]
    assert set(body_schema["required"]) == {"base_run_id", "source_snapshot_digest"}


def _source_digest(snapshots: list[dict]) -> tuple[str, dict[str, str]]:
    per_document = {
        str(snapshot["document_id"]): hashlib.sha256(
            json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        for snapshot in snapshots
    }
    digest = hashlib.sha256(
        json.dumps(per_document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return digest, per_document


@pytest.mark.asyncio
async def test_concurrent_same_key_returns_one_run_and_changed_digest_conflicts(
    semantic_case,  # noqa: F811 - imported pytest fixture is re-exported by test module
) -> None:
    factory, request, _ = semantic_case
    dossier_id, base_run_id = request["dossier_id"], request["task_id"]
    source_digest, per_document = _source_digest(request["snapshots"])
    async with factory() as session:
        job = await session.scalar(select(JobORM).where(JobORM.dossier_id == dossier_id))
        base_run = await session.get(PipelineRunORM, base_run_id)
        assert job is not None and base_run is not None
        job.status = "pending_review"
        base_run.status = "succeeded"
        base_run.config_snapshot = json.dumps(
            {
                "ai1_snapshot_digests": per_document,
                "ai1_snapshots": {
                    str(snapshot["document_id"]): snapshot for snapshot in request["snapshots"]
                },
                "ai1_extracted_documents": sorted(per_document),
            },
            sort_keys=True,
        )
        await session.commit()

    async def request_reprocess() -> tuple[str, bool]:
        async with factory() as session:
            repo = PipelineRunRepositoryImpl(session, job.tenant_id)
            run, created = await repo.create_reprocess(
                dossier_id=dossier_id,
                actor_id="semantic-operator",
                idempotency_key="same-request-key-001",
                base_run_id=base_run_id,
                source_snapshot_digest=source_digest,
                trace_id="semantic-operator",
            )
            await session.commit()
            return run.id, created

    results = await asyncio.gather(request_reprocess(), request_reprocess())
    assert results[0][0] == results[1][0]
    assert sorted(created for _, created in results) == [False, True]

    async with factory() as session:
        repo = PipelineRunRepositoryImpl(session, job.tenant_id)
        with pytest.raises(ReprocessRequestConflict):
            await repo.create_reprocess(
                dossier_id=dossier_id,
                actor_id="semantic-operator",
                idempotency_key="same-request-key-001",
                base_run_id=base_run_id,
                source_snapshot_digest="f" * 64,
                trace_id="semantic-operator",
            )
        await session.rollback()


@pytest.mark.asyncio
async def test_http_reprocess_retry_returns_the_same_persisted_run(
    semantic_case,  # noqa: F811 - imported pytest fixture is re-exported here
    monkeypatch,
) -> None:
    factory, request, _ = semantic_case
    dossier_id, base_run_id = request["dossier_id"], request["task_id"]
    source_digest, per_document = _source_digest(request["snapshots"])
    async with factory() as session:
        job = await session.scalar(select(JobORM).where(JobORM.dossier_id == dossier_id))
        base_run = await session.get(PipelineRunORM, base_run_id)
        assert job is not None and base_run is not None
        base_run.status = "succeeded"
        base_run.config_snapshot = json.dumps(
            {
                "ai1_snapshot_digests": per_document,
                "ai1_snapshots": {
                    str(snapshot["document_id"]): snapshot for snapshot in request["snapshots"]
                },
                "ai1_extracted_documents": sorted(per_document),
            },
            sort_keys=True,
        )
        await session.execute(
            update(DocumentORM)
            .where(DocumentORM.dossier_id == dossier_id)
            .values(role=func.lower(DocumentORM.role))
        )
        await session.commit()

    published: list[str] = []

    async def publish(dossier: str) -> None:
        published.append(dossier)

    monkeypatch.setattr(extraction_dependencies, "publish_dossier_run", publish)
    previous_storage = app.dependency_overrides.get(get_file_storage)
    app.dependency_overrides[get_file_storage] = lambda: None
    try:
        async with semantic_route_client(factory, semantic_reviewer(role="OPERATOR")) as client:
            responses = [
                await client.post(
                    f"/api/v1/dossiers/{dossier_id}/reprocess",
                    headers={"Idempotency-Key": "http-reprocess-request"},
                    json={
                        "base_run_id": base_run_id,
                        "source_snapshot_digest": source_digest,
                    },
                )
                for _ in range(2)
            ]
            mismatched = await client.post(
                f"/api/v1/dossiers/{dossier_id}/reprocess",
                headers={"Idempotency-Key": "http-reprocess-request"},
                json={
                    "base_run_id": base_run_id,
                    "source_snapshot_digest": "f" * 64,
                },
            )
    finally:
        if previous_storage is None:
            app.dependency_overrides.pop(get_file_storage, None)
        else:
            app.dependency_overrides[get_file_storage] = previous_storage

    assert [response.status_code for response in responses] == [202, 202]
    assert mismatched.status_code == 409
    accepted_ids = [response.json()["data"]["job_id"] for response in responses]
    assert accepted_ids[0] == accepted_ids[1]
    assert published == [dossier_id, dossier_id]  # at-least-once delivery; worker fences by run
    async with factory() as session:
        matching = list(
            (
                await session.scalars(
                    select(PipelineRunORM).where(
                        PipelineRunORM.tenant_id == job.tenant_id,
                        PipelineRunORM.dossier_id == dossier_id,
                        PipelineRunORM.reprocess_idempotency_key
                        == hashlib.sha256(b"http-reprocess-request").hexdigest(),
                    )
                )
            ).all()
        )
    assert [run.id for run in matching] == [accepted_ids[0]]


@pytest.mark.asyncio
async def test_current_results_do_not_fall_back_to_a_prior_run(
    semantic_case,  # noqa: F811 - imported pytest fixture is re-exported by test module
) -> None:
    factory, request, _ = semantic_case
    dossier_id, previous_run_id = request["dossier_id"], request["task_id"]
    async with factory() as session:
        job = await session.scalar(select(JobORM).where(JobORM.dossier_id == dossier_id))
        previous = await session.get(PipelineRunORM, previous_run_id)
        assert job is not None and previous is not None
        prior_payload = previous.ai2_result_json
        prior_digest = previous.ai2_result_digest
        replacement_id = f"{previous_run_id}-pending-reprocess"
        session.add(
            PipelineRunORM(
                id=replacement_id,
                tenant_id=job.tenant_id,
                dossier_id=dossier_id,
                job_id=job.id,
                status="queued",
                pipeline_version="test-reprocess-v1",
            )
        )
        job.current_run_id = replacement_id
        await session.commit()

    async with semantic_route_client(factory, semantic_reviewer()) as client:
        response = await client.get(f"/api/v1/dossiers/{dossier_id}/semantic-results")

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["run_id"] == replacement_id
    assert data["state"] == "NOT_READY"
    assert data["semantic_extension"] is None
    async with factory() as session:
        previous = await session.get(PipelineRunORM, previous_run_id)
    assert previous is not None
    assert previous.ai2_result_json == prior_payload
    assert previous.ai2_result_digest == prior_digest
