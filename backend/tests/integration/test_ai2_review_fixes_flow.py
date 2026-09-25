"""Deterministic offline integration coverage for the AI2 review-fixes flow."""

from __future__ import annotations

import copy
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from contract_intelligence.contract.infrastructure.persistence.orm import (
    DocumentORM,
    DossierORM,
    JobORM,
)
from contract_intelligence.extraction.infrastructure.persistence.orm import PipelineRunORM
from contract_intelligence.main import app
from contract_intelligence.shared.ai.client import (
    StubAiServiceClient,
    canonical_ai_service_mode,
)
from contract_intelligence.shared.ai.persistence import (
    load_ai2_read_model,
    persist_ai2_processing_result,
)
from contract_intelligence.shared.ai.schemas import ExtractJobRequest
from contract_intelligence.shared.auth import AuthenticatedUser, get_current_user
from contract_intelligence.shared.auth.tenant import get_tenant_id
from contract_intelligence.shared.persistence import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models
from contract_intelligence.shared.persistence.session import get_async_session

TENANT_ID = "tenant-vsf-ai2"
OTHER_TENANT_ID = "tenant-vsf-other"
DOSSIER_ID = "dossier-vsf-ai2"
RUN_ID = "run-vsf-ai2"
REVIEW_RUN_ID = "run-vsf-ai2-review"
BODY_DOCUMENT_ID = "document-vsf-body"
ANNEX_DOCUMENT_ID = "document-vsf-annex"
SNAPSHOT_DIGEST = "sha256:vsf-ai2-fixture-001"

OPERATOR = AuthenticatedUser(
    user_id="user-vsf-operator",
    tenant_id=TENANT_ID,
    email="operator@vsf.test",
    display_name="VSF Operator",
    role="OPERATOR",
)
REVIEWER = AuthenticatedUser(
    user_id="user-vsf-reviewer",
    tenant_id=TENANT_ID,
    email="reviewer@vsf.test",
    display_name="VSF Reviewer",
    role="REVIEWER",
)


def _citation(citation_id: str, document_id: str, source_hash: str) -> dict[str, Any]:
    return {
        "citation_id": citation_id,
        "node_id": f"node-{citation_id}",
        "page_revision_id": f"page-revision-{citation_id}",
        "bbox": [1, 2, 30, 40],
        "bbox_fragments": [[1, 2, 30, 40]],
        "text_span": f"evidence {citation_id}",
        "source_file_id": document_id,
        "page": 1,
        "page_range": [1],
        "line_ids": [f"line-{citation_id}"],
        "char_start": 0,
        "char_end": 20,
        "breadcrumb": ["article 1"],
        "structure_path": "article[1]",
        "geometry_available": True,
        "source_hash": source_hash,
        "quote_sha256": "e" * 64,
        "coordinate_system": "pdf",
        "geometry_source": "ocr",
        "precision": "exact",
        "validation_status": "validated",
    }


def _processing_result() -> dict[str, Any]:
    body_citation = _citation("citation-body", BODY_DOCUMENT_ID, "b" * 64)
    annex_citation = _citation("citation-annex", ANNEX_DOCUMENT_ID, "a" * 64)
    return {
        "schema_version": "ai2.be.processing.result.v1",
        "request_id": "request-vsf-ai2-001",
        "idempotency_key": "idempotency-vsf-ai2-001",
        "attempt": 1,
        "job_id": "ai2-job-vsf-ai2-001",
        "status": "SUCCEEDED",
        "review_state": "PASS",
        "input_snapshots": [
            {
                "snapshot_id": "snapshot-body-001",
                "snapshot_version": "ai1.snapshot.v1",
                "source_digest": SNAPSHOT_DIGEST,
                "snapshot_digest": SNAPSHOT_DIGEST,
            },
            {
                "snapshot_id": "snapshot-annex-001",
                "snapshot_version": "ai1.snapshot.v1",
                "source_digest": "sha256:vsf-ai2-annex-001",
                "snapshot_digest": "sha256:vsf-ai2-annex-001",
            },
        ],
        "result": {
            "facts": [
                {
                    "fact_id": "fact-contract-value",
                    "item_key": "contract_value",
                    "raw_value": "1000000",
                    "normalized_value": {"value": 1000000, "currency": "VND"},
                    "role": "amount",
                    "review_state": "PASS",
                    "citation_ids": ["citation-body"],
                }
            ],
            "findings": [
                {
                    "finding_id": "finding-term-mismatch",
                    "item_key": "payment_term",
                    "finding_type": "structured",
                    "scope": "contract_annex",
                    "disposition": "needs_review",
                    "reason": "Body and annex terms differ.",
                    "review_state": "NEEDS_REVIEW",
                    "evidence_left_citation_ids": ["citation-body"],
                    "evidence_right_citation_ids": ["citation-annex"],
                }
            ],
            "context_findings": [
                {
                    "finding_id": "context-party",
                    "finding_type": "party",
                    "subject_key": "seller",
                    "reason": "Context retained even with a review finding.",
                    "review_state": "PASS",
                    "citation_ids": ["citation-body"],
                }
            ],
            "events": [{"event_id": "event-001", "event_type": "grounding.observed"}],
            "citations": [body_citation, annex_citation],
            "annex_links": [
                {
                    "link_id": "annex-link-001",
                    "annex_document_id": ANNEX_DOCUMENT_ID,
                    "contract_document_id": BODY_DOCUMENT_ID,
                    "score": 0.98,
                    "annex_sequence": 1,
                    "status": "linked",
                    "citation_ids": ["citation-annex"],
                }
            ],
            "index_contribution": {
                "state": "propose",
                "chunks": [
                    {
                        "chunk_id": "chunk-body-001",
                        "text": "body",
                        "citation_ids": ["citation-body"],
                    },
                    {
                        "chunk_id": "chunk-annex-001",
                        "text": "annex",
                        "citation_ids": ["citation-annex"],
                    },
                ],
                "evidence_issues": [
                    {
                        "issue_id": "evidence-gap-001",
                        "severity": "low",
                        "reason": "One page requires reviewer confirmation.",
                        "citation_ids": ["citation-annex"],
                    }
                ],
                "coverage": {
                    "input": {"pages": 2, "lines": 20, "tables": 1},
                    "output": {"chunks": 2, "citations": 2},
                    "covered": 19,
                    "denominator": 20,
                },
                "contract_context": {
                    "document_id": BODY_DOCUMENT_ID,
                    "parts": [{"part_id": "part-001", "citation_ids": ["citation-body"]}],
                },
            },
        },
        "errors": [],
    }


async def _seed_dossier(factory: async_sessionmaker[AsyncSession]) -> None:
    async with factory() as session:
        session.add_all(
            [
                DossierORM(
                    id=DOSSIER_ID,
                    tenant_id=TENANT_ID,
                    name="Deterministic AI2 review fixture",
                    checksum=SNAPSHOT_DIGEST,
                    metadata_json={
                        "ai2_snapshot_digest": SNAPSHOT_DIGEST,
                        "created_by": OPERATOR.user_id,
                        "shared_with": [
                            {
                                "id": REVIEWER.user_id,
                                "roles": ["REVIEWER"],
                            }
                        ],
                    },
                ),
                JobORM(id="job-vsf-ai2", tenant_id=TENANT_ID, dossier_id=DOSSIER_ID),
                PipelineRunORM(
                    id=RUN_ID,
                    tenant_id=TENANT_ID,
                    job_id="job-vsf-ai2",
                    dossier_id=DOSSIER_ID,
                    status="running",
                    pipeline_version="test-v1",
                ),
                DocumentORM(
                    id=BODY_DOCUMENT_ID,
                    tenant_id=TENANT_ID,
                    dossier_id=DOSSIER_ID,
                    role="CONTRACT",
                    filename="body.pdf",
                    sha256="b" * 64,
                ),
                DocumentORM(
                    id=ANNEX_DOCUMENT_ID,
                    tenant_id=TENANT_ID,
                    dossier_id=DOSSIER_ID,
                    role="ANNEX",
                    filename="annex.pdf",
                    sha256="a" * 64,
                ),
            ]
        )
        await session.commit()


@pytest_asyncio.fixture
async def db_session_factory(
    tmp_path: Any,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    import_all_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'ai2-review-flow.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await _seed_dossier(factory)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with db_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_current_user] = lambda: OPERATOR
    app.dependency_overrides[get_tenant_id] = lambda: TENANT_ID
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_snapshot_result_read_model_query_and_review_flow(
    db_session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
) -> None:
    result = _processing_result()
    async with db_session_factory() as session:
        persisted = await persist_ai2_processing_result(
            session,
            tenant_id=TENANT_ID,
            dossier_id=DOSSIER_ID,
            result=result,
            run_id=RUN_ID,
        )
        await session.commit()

    async with db_session_factory() as session:
        read_model = await load_ai2_read_model(session, tenant_id=TENANT_ID, run_id=RUN_ID)

    assert read_model.payload["input_snapshots"][1]["snapshot_version"] == "ai1.snapshot.v1"
    assert read_model.payload["result"]["annex_links"][0]["annex_document_id"] == ANNEX_DOCUMENT_ID
    assert len(read_model.payload["result"]["context_findings"]) == 1
    assert len(read_model.payload["result"]["index_contribution"]["chunks"]) == 2
    assert read_model.evidence_issue_count == 1
    assert persisted["review_state"] == "PASS"
    assert persisted["evidence_ready"] is False

    with patch(
        "contract_intelligence.api.v1.dossiers.query_ai2",
        new=AsyncMock(
            return_value={
                "state": "BLOCKED",
                "answer": "A transport answer is not an approved answer.",
                "citations": [
                    {
                        "source_file_id": BODY_DOCUMENT_ID,
                        "line_id": "line-citation-body",
                    }
                ],
                "retrieval_layer": {"selected": "LEXICAL"},
                "reasoning_trace": [{"code": "EVIDENCE_GAP"}],
            }
        ),
    ) as query_mock:
        response = await client.post(
            f"/api/v1/dossiers/{DOSSIER_ID}/query",
            json={"query": "What is the payment term?"},
        )

    assert response.status_code == 200
    assert response.json()["state"] == "BLOCKED"
    assert response.json()["reasoning_trace"] == [{"code": "EVIDENCE_GAP"}]
    query_mock.assert_awaited_once()
    query_payload = query_mock.await_args.args[0]
    assert query_payload["tenant_id"] == TENANT_ID
    assert query_payload["snapshot_digest"] == SNAPSHOT_DIGEST


@pytest.mark.asyncio
async def test_review_queue_rejects_stale_version_after_invalid_evidence(
    db_session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
) -> None:
    invalid_result = copy.deepcopy(_processing_result())
    invalid_result["request_id"] = "request-vsf-ai2-review"
    invalid_result["idempotency_key"] = "idempotency-vsf-ai2-review"
    invalid_result["result"]["facts"][0]["citation_ids"] = ["citation-does-not-exist"]

    async with db_session_factory() as session:
        session.add(
            JobORM(id="job-vsf-ai2-review", tenant_id=TENANT_ID, dossier_id=DOSSIER_ID)
        )
        session.add(
            PipelineRunORM(
                id=REVIEW_RUN_ID,
                tenant_id=TENANT_ID,
                job_id="job-vsf-ai2-review",
                dossier_id=DOSSIER_ID,
                status="running",
                pipeline_version="test-v1",
            )
        )
        await session.commit()
        await persist_ai2_processing_result(
            session,
            tenant_id=TENANT_ID,
            dossier_id=DOSSIER_ID,
            result=invalid_result,
            run_id=REVIEW_RUN_ID,
        )
        await session.commit()

    app.dependency_overrides[get_current_user] = lambda: REVIEWER
    queue = await client.get(f"/api/v1/dossiers/{DOSSIER_ID}/review-items")
    assert queue.status_code == 200
    item = next(
        row for row in queue.json()["data"] if row["reason"] == "INVALID_CITATION_REFERENCE"
    )
    assert item["reason"] == "INVALID_CITATION_REFERENCE"
    assert item["version"] == 1

    accepted = await client.post(
        f"/api/v1/review-items/{item['id']}/actions",
        json={"action": "needs_more_evidence", "base_version": 1},
        headers={"Idempotency-Key": "review-action-vsf-001"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["data"]["new_version"] == 2

    stale = await client.post(
        f"/api/v1/review-items/{item['id']}/actions",
        json={"action": "confirm", "base_version": 1},
        headers={"Idempotency-Key": "review-action-vsf-002"},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"
    assert stale.json()["current_state"]["version"] == 2


@pytest.mark.asyncio
async def test_anonymous_and_cross_tenant_query_are_denied(
    client: AsyncClient,
) -> None:
    app.dependency_overrides.pop(get_current_user)
    anonymous = await client.post(
        f"/api/v1/dossiers/{DOSSIER_ID}/query",
        json={"query": "anonymous"},
    )
    assert anonymous.status_code == 401

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        user_id="user-other-tenant",
        tenant_id=OTHER_TENANT_ID,
        email="other@vsf.test",
        display_name="Other Tenant",
        role="OPERATOR",
    )
    cross_tenant = await client.post(
        f"/api/v1/dossiers/{DOSSIER_ID}/query",
        json={"query": "cross tenant"},
    )
    assert cross_tenant.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_result_recovery_is_idempotent_and_legacy_stub_is_explicit(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    result = _processing_result()
    async with db_session_factory() as session:
        first = await persist_ai2_processing_result(
            session,
            tenant_id=TENANT_ID,
            dossier_id=DOSSIER_ID,
            result=result,
            run_id=RUN_ID,
        )
        await session.commit()

    async with db_session_factory() as session:
        replay = await persist_ai2_processing_result(
            session,
            tenant_id=TENANT_ID,
            dossier_id=DOSSIER_ID,
            result=copy.deepcopy(result),
            run_id=RUN_ID,
        )
        await session.commit()
        run_count = await session.scalar(
            select(func.count()).select_from(PipelineRunORM).where(PipelineRunORM.id == RUN_ID)
        )

    assert first["idempotent_replay"] is False
    assert replay["idempotent_replay"] is True
    assert run_count == 1
    assert canonical_ai_service_mode("compatibility") == "stub"
    assert canonical_ai_service_mode("http") == "http"

    stub = StubAiServiceClient()
    submission = await stub.submit_extract(
        ExtractJobRequest(
            task_id=1,
            attempt_id=1,
            tenant_id=TENANT_ID,
            document_id=BODY_DOCUMENT_ID,
            snapshot_digest=SNAPSHOT_DIGEST,
            document_text_nfc="deterministic stub text",
        )
    )
    report = await stub.get_job_status(submission.job_id)
    assert report.result["schema_version"] == "ai2.extraction.v2"
