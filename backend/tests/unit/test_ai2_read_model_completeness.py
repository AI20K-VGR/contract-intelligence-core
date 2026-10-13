"""Completeness is independent from the AI2 job lifecycle status."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM, JobORM
from contract_intelligence.extraction.infrastructure.persistence.orm import PipelineRunORM
from contract_intelligence.shared.ai.persistence import (
    evaluate_ai2_completeness,
    load_ai2_read_model,
    persist_ai2_processing_result,
)
from contract_intelligence.shared.persistence.base import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models


async def _factory() -> tuple[object, async_sessionmaker[AsyncSession]]:
    import_all_models()
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _succeeded_result() -> dict[str, object]:
    return {
        "schema_version": "ai2.be.processing.result.v1",
        "request_id": "request-empty",
        "idempotency_key": "idem-empty",
        "attempt": 1,
        "job_id": "job-empty",
        "status": "SUCCEEDED",
        "review_state": "PASS",
        "input_snapshots": [
            {
                "snapshot_id": "snap",
                "snapshot_version": "ai1.snapshot.v1",
                "source_digest": "a" * 64,
                "snapshot_digest": "a" * 64,
            }
        ],
        "result": {
            "facts": [],
            "findings": [],
            "context_findings": [],
            "events": [],
            "citations": [],
            "index_contribution": {
                "state": "propose",
                "chunks": [],
                "evidence_issues": [],
                "coverage": {"input": {"pages": 2, "lines": 20, "tables": 0}},
                "extraction_version": 1,
                "proposed_index_version": "idx-empty",
                "contract_context": None,
            },
        },
        "errors": [],
    }


def test_semantic_review_and_missing_extension_never_become_evidence_ready():
    from contract_intelligence.shared.ai.schemas import SemanticExtension

    payload = _succeeded_result()
    extension = SemanticExtension.model_validate(
        {
            "schema_version": "ai2.semantic.v1",
            "tenant_id": "tenant-a",
            "dossier_id": "dossier-a",
            "profile_digest": "a" * 64,
            "alias_version": 0,
            "alias_digest": None,
            "frames": [],
            "rows": [],
            "pairs": [],
            "timeline": [],
            "alias_drafts": [],
            "coverage": {
                "state": "NOT_MEASURED",
                "attempted_nodes": 0,
                "frames": 0,
                "grounded_slots": 0,
                "unresolved_slots": 0,
                "invalid_evidence": 0,
                "reasons": ["timeline_chain_not_supplied"],
                "context_nodes": 0,
                "context_calls": 0,
            },
        }
    )
    payload["result"]["semantic_extension"] = extension.model_dump(mode="json")
    completeness = evaluate_ai2_completeness(payload)
    assert completeness["evidence_ready"] is False
    assert completeness["semantic_state"] == "NOT_MEASURED"
    assert completeness["output_counts"]["semantic_frames"] == 0
    del payload["result"]["semantic_extension"]
    assert evaluate_ai2_completeness(payload)["semantic_state"] == "NOT_MEASURED"
    payload["result"]["index_contribution"]["coverage"]["semantic_requested"] = True
    assert evaluate_ai2_completeness(payload)["reason_code"] == "SEMANTIC_NOT_MEASURED"


@pytest.mark.asyncio
async def test_succeeded_zero_output_is_not_evidence_ready() -> None:
    engine, factory = await _factory()
    try:
        async with factory() as session:
            session.add_all(
                [
                    DossierORM(id="dossier-empty", tenant_id="tenant-empty", name="empty"),
                    JobORM(id="job-empty", tenant_id="tenant-empty", dossier_id="dossier-empty"),
                    PipelineRunORM(
                        id="run-empty",
                        tenant_id="tenant-empty",
                        job_id="job-empty",
                        dossier_id="dossier-empty",
                        status="running",
                        pipeline_version="v1.0.0",
                    ),
                ]
            )
            await session.commit()
            result = _succeeded_result()
            completeness = evaluate_ai2_completeness(result)
            assert completeness["evidence_ready"] is False
            assert completeness["reason_code"] == "NO_ELIGIBLE_DATA"

            persisted = await persist_ai2_processing_result(
                session,
                tenant_id="tenant-empty",
                dossier_id="dossier-empty",
                result=result,
                run_id="run-empty",
            )
            await session.commit()
            assert persisted["job_status"] == "SUCCEEDED"
            assert persisted["evidence_ready"] is False
            read_model = await load_ai2_read_model(
                session, tenant_id="tenant-empty", run_id="run-empty"
            )
            assert read_model.job_status == "SUCCEEDED"
            assert read_model.completeness_state == "NO_ELIGIBLE_DATA"
            assert read_model.evidence_ready is False
    finally:
        await engine.dispose()
