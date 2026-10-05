"""Persistence contract tests for the complete AI2 result envelope."""

from __future__ import annotations

import copy
import json

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from contract_intelligence.contract.infrastructure.persistence.orm import (
    DocumentORM,
    DossierORM,
    JobORM,
)
from contract_intelligence.extraction.infrastructure.persistence.orm import PipelineRunORM
from contract_intelligence.review.infrastructure.persistence.orm import ReviewItemORM
from contract_intelligence.shared.ai.persistence import (
    load_ai2_read_model,
    persist_ai2_processing_result,
)
from contract_intelligence.shared.persistence.base import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models

TENANT_ID = "tenant-ai2"
DOSSIER_ID = "dossier-ai2"
RUN_ID = "run-ai2"
IDEMPOTENCY_KEY = "idem-ai2"
HASH = "a" * 64


@pytest.mark.asyncio
async def test_semantic_scope_rejected_before_writes():
    engine, factory = await _session_factory()
    try:
        async with factory() as session:
            await _seed_run(session)
            result = complete_result()
            result["result"]["semantic_extension"] = {
                "schema_version": "ai2.semantic.v1",
                "tenant_id": "different-tenant",
                "dossier_id": DOSSIER_ID,
                "profile_digest": HASH,
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
                    "reasons": [],
                    "context_nodes": 0,
                    "context_calls": 0,
                },
            }
            with pytest.raises(ValueError, match="semantic.*scope"):
                await persist_ai2_processing_result(
                    session,
                    tenant_id=TENANT_ID,
                    dossier_id=DOSSIER_ID,
                    result=result,
                    run_id=RUN_ID,
                )
            assert await session.scalar(select(func.count()).select_from(ReviewItemORM)) == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_negotiated_run_legacy_result_is_partial_after_rollback():
    engine, factory = await _session_factory()
    try:
        async with factory() as session:
            await _seed_run(session)
            run = await session.get(PipelineRunORM, RUN_ID)
            run.config_snapshot = '{"semantic_profile":{"digest":"pinned"}}'
            result = complete_result()
            stored = await persist_ai2_processing_result(
                session, tenant_id=TENANT_ID, dossier_id=DOSSIER_ID, result=result, run_id=RUN_ID
            )
            await session.commit()
            assert (
                stored["reason_code"] == "SEMANTIC_NOT_MEASURED"
                and stored["evidence_ready"] is False
            )
            loaded = await load_ai2_read_model(session, tenant_id=TENANT_ID, run_id=RUN_ID)
            assert loaded.payload == result and loaded.completeness_state == "NEEDS_REVIEW"
    finally:
        await engine.dispose()


def _citation(citation_id: str, document_id: str) -> dict[str, object]:
    return {
        "citation_id": citation_id,
        "node_id": f"node-{citation_id}",
        "page_revision_id": f"page-rev-{citation_id}",
        "bbox": [1, 2, 30, 40],
        "bbox_fragments": [[1, 2, 30, 40]],
        "text_span": f"evidence {citation_id}",
        "source_file_id": document_id,
        "page": 3,
        "page_range": [3],
        "line_ids": [f"line-{citation_id}"],
        "char_start": 10,
        "char_end": 30,
        "breadcrumb": ["article 1"],
        "structure_path": "article[1]",
        "geometry_available": True,
        "source_hash": HASH,
        "quote_sha256": HASH,
        "coordinate_system": "pdf",
        "geometry_source": "ocr",
        "precision": "exact",
        "validation_status": "validated",
        "table_id": None,
        "cell_id": None,
    }


def complete_result() -> dict[str, object]:
    chunks = [
        {
            "chunk_id": f"chunk-{index}",
            "text": f"chunk text {index}",
            "citation_ids": ["cit-body"],
            "metadata": {"ordinal": index},
        }
        for index in range(58)
    ]
    events = [
        {
            "event_id": f"event-{index}",
            "event_type": "extraction.observed",
            "payload": {"ordinal": index, "source": "ai2"},
        }
        for index in range(23)
    ]
    body = {
        "facts": [],
        "findings": [],
        "context_findings": [
            {
                "finding_id": "context-1",
                "finding_type": "party",
                "relation_type": "MEMBER_OF",
                "subject_key": "seller",
                "source_node_ids": ["node-cit-body"],
                "review_state": "PASS",
                "reason": "context retained",
                "citation_ids": ["cit-body"],
                "metadata": {"role": "seller", "nested": {"source": "manifest"}},
            }
        ],
        "events": events,
        "citations": [
            _citation("cit-body", "document-body"),
            _citation("cit-annex", "document-annex"),
        ],
        "annex_links": [
            {
                "link_id": "annex-link-1",
                "annex_document_id": "document-annex",
                "contract_document_id": "document-body",
                "score": 0.98,
                "annex_sequence": 1,
                "effective_date": "2026-09-25",
                "status": "linked",
                "citation_ids": ["cit-annex"],
            }
        ],
        "index_contribution": {
            "state": "propose",
            "chunks": chunks,
            "evidence_issues": [
                {
                    "issue_id": "evidence-1",
                    "severity": "low",
                    "reason": "table context retained",
                    "citation_ids": ["cit-body"],
                    "metadata": {"table": "pricing"},
                }
            ],
            "coverage": {
                "input": {"pages": 12, "lines": 240, "tables": 4},
                "output": {"chunks": 58, "citations": 2},
                "covered": 232,
                "denominator": 240,
            },
            "extraction_version": 7,
            "proposed_index_version": "idx-2026-09-25",
            "contract_context": {
                "document_id": "document-body",
                "parts": [{"part_id": "part-1", "citation_ids": ["cit-body"]}],
            },
        },
    }
    return {
        "schema_version": "ai2.be.processing.result.v1",
        "request_id": "request-ai2",
        "idempotency_key": IDEMPOTENCY_KEY,
        "attempt": 1,
        "job_id": "job-ai2",
        "status": "SUCCEEDED",
        "review_state": "PASS",
        "input_snapshots": [
            {
                "snapshot_id": "snapshot-body",
                "snapshot_version": "ai1.snapshot.v1",
                "source_digest": HASH,
                "snapshot_digest": HASH,
            }
        ],
        "result": body,
        "errors": [],
    }


async def _session_factory() -> tuple[object, async_sessionmaker[AsyncSession]]:
    import_all_models()
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _seed_run(session: AsyncSession) -> None:
    session.add_all(
        [
            DossierORM(id=DOSSIER_ID, tenant_id=TENANT_ID, name="AI2 dossier"),
            JobORM(id="job-ai2", tenant_id=TENANT_ID, dossier_id=DOSSIER_ID),
            PipelineRunORM(
                id=RUN_ID,
                tenant_id=TENANT_ID,
                job_id="job-ai2",
                dossier_id=DOSSIER_ID,
                status="running",
                pipeline_version="v1.0.0",
            ),
            DocumentORM(
                id="document-body",
                tenant_id=TENANT_ID,
                dossier_id=DOSSIER_ID,
                role="CONTRACT",
                filename="body.pdf",
                sha256=HASH,
            ),
            DocumentORM(
                id="document-annex",
                tenant_id=TENANT_ID,
                dossier_id=DOSSIER_ID,
                role="ANNEX",
                filename="annex.pdf",
                sha256="b" * 64,
            ),
        ]
    )
    await session.commit()


@pytest.mark.asyncio
async def test_complete_result_round_trips_after_reload_and_replay_is_idempotent() -> None:
    engine, factory = await _session_factory()
    try:
        async with factory() as session:
            await _seed_run(session)
            result = complete_result()
            persisted = await persist_ai2_processing_result(
                session,
                tenant_id=TENANT_ID,
                dossier_id=DOSSIER_ID,
                result=result,
                run_id=RUN_ID,
            )
            await session.commit()
            assert persisted["facts"] == 0
            assert persisted["findings"] == 0
            assert persisted["chunks"] == 58
            assert persisted["events"] == 23
            assert persisted["evidence_issues"] == 1
            assert persisted["annex_links"] == 1
            assert persisted["evidence_ready"] is False

        async with factory() as session:
            read_model = await load_ai2_read_model(session, tenant_id=TENANT_ID, run_id=RUN_ID)
            assert read_model.job_status == "SUCCEEDED"
            assert read_model.evidence_ready is False
            assert read_model.completeness_state != "SUCCEEDED"
            assert (
                read_model.payload["result"]["context_findings"]
                == result["result"]["context_findings"]
            )
            assert len(read_model.payload["result"]["events"]) == 23
            assert len(read_model.payload["result"]["index_contribution"]["chunks"]) == 58
            assert read_model.payload["result"]["annex_links"] == result["result"]["annex_links"]
            assert read_model.coverage["input"]["tables"] == 4

            replay = await persist_ai2_processing_result(
                session,
                tenant_id=TENANT_ID,
                dossier_id=DOSSIER_ID,
                result=copy.deepcopy(result),
                run_id=RUN_ID,
            )
            await session.commit()
            assert replay["idempotent_replay"] is True
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(PipelineRunORM)
                    .where(PipelineRunORM.id == RUN_ID)
                )
                == 1
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_invalid_citation_is_retained_with_stable_review_reason() -> None:
    engine, factory = await _session_factory()
    try:
        async with factory() as session:
            await _seed_run(session)
            result = complete_result()
            result["result"]["facts"] = [
                {
                    "fact_id": "fact-invalid",
                    "raw_value": "100",
                    "normalized_value": "100",
                    "subject": "price",
                    "role": "amount",
                    "unit": "VND",
                    "currency": "VND",
                    "vat_basis": None,
                    "condition": None,
                    "scope": "body",
                    "validity": None,
                    "item_key": "price",
                    "tax_basis": None,
                    "period_start": None,
                    "source_role": "body",
                    "provenance": "ai2",
                    "review_state": "PASS",
                    "citation_ids": ["citation-does-not-exist"],
                }
            ]
            persisted = await persist_ai2_processing_result(
                session,
                tenant_id=TENANT_ID,
                dossier_id=DOSSIER_ID,
                result=result,
                run_id=RUN_ID,
            )
            await session.commit()
            assert persisted["dropped_records"] == 1
            assert persisted["reason_code"] == "INVALID_CITATION_REFERENCE"
            assert persisted["review_state"] == "NEEDS_REVIEW"
            assert persisted["evidence_ready"] is False
            assert await session.scalar(select(func.count()).select_from(ReviewItemORM)) == 1

            read_model = await load_ai2_read_model(session, tenant_id=TENANT_ID, run_id=RUN_ID)
            assert read_model.payload["result"]["facts"][0]["fact_id"] == "fact-invalid"
            assert read_model.reason_code == "INVALID_CITATION_REFERENCE"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_findings_project_real_two_sided_citations_and_skip_single_document_context() -> None:
    from contract_intelligence.conflict.infrastructure.persistence.orm import (
        FindingORM,
        FindingSideORM,
    )

    engine, factory = await _session_factory()
    try:
        async with factory() as session:
            await _seed_run(session)
            result = complete_result()
            body = result["result"]
            body["findings"] = [
                {
                    "finding_id": "cand_clause_1",
                    "left_id": "node-cit-body",
                    "right_id": "node-cit-annex",
                    "finding_type": "COMPARABLE_DIFFERENCE",
                    "model_disposition": "UNCLEAR",
                    "review_state": "NEEDS_REVIEW",
                    "evidence_left_citation_ids": ["cit-body"],
                    "evidence_right_citation_ids": ["cit-annex"],
                    "reason": "08 tuần ↔ 10 tuần",
                    "disposition": "COMPARABLE_DIFFERENCE",
                    "scope": "CONTRACT_ANNEX",
                    "item_key": "Điều 3.1 · Tiến độ",
                }
            ]
            body["context_findings"] = [
                {
                    # Single-document signal: must not become a contract↔annex conflict.
                    "finding_id": "context-gap",
                    "finding_type": "CONTEXT_GAP",
                    "relation_type": None,
                    "subject_key": "annex:01",
                    "source_node_ids": ["node-cit-body"],
                    "review_state": "NEEDS_REVIEW",
                    "reason": "Phát hiện Phụ lục 01 nhưng chưa thấy tham chiếu",
                    "citation_ids": ["cit-body"],
                    "metadata": {},
                },
                {
                    # Already emitted as a canonical finding: must not be duplicated.
                    "finding_id": "context-dup",
                    "finding_type": "CONTEXT_CONFLICT",
                    "relation_type": None,
                    "subject_key": "Điều 3.1 · Tiến độ",
                    "source_node_ids": ["node-cit-body", "node-cit-annex"],
                    "review_state": "NEEDS_REVIEW",
                    "reason": "duplicate",
                    "citation_ids": ["cit-body", "cit-annex"],
                    "metadata": {"candidate_id": "cand_clause_1"},
                },
                {
                    # Genuine cross-document context signal with real citations on both sides.
                    "finding_id": "context-cross",
                    "finding_type": "AMENDMENT_SIGNAL",
                    "relation_type": "AMENDS",
                    "subject_key": "annex:02",
                    "source_node_ids": ["node-cit-body", "node-cit-annex"],
                    "review_state": "NEEDS_REVIEW",
                    "reason": "Phụ lục có ngôn ngữ sửa đổi",
                    "citation_ids": ["cit-body", "cit-annex"],
                    "metadata": {},
                },
            ]
            persisted = await persist_ai2_processing_result(
                session,
                tenant_id=TENANT_ID,
                dossier_id=DOSSIER_ID,
                result=result,
                run_id=RUN_ID,
            )
            await session.commit()
            # One canonical clause finding + one cross-document context signal.
            assert persisted["findings"] == 2

            findings = (await session.execute(select(FindingORM))).scalars().all()
            by_topic = {f.key_or_topic: f for f in findings}
            assert set(by_topic) == {"Điều 3.1 · Tiến độ", "annex:02"}
            assert by_topic["Điều 3.1 · Tiến độ"].disposition == "comparable_difference"
            assert by_topic["annex:02"].disposition == "candidate_amendment"
            assert all(f.run_id == RUN_ID for f in findings)

            sides = (await session.execute(select(FindingSideORM))).scalars().all()
            for finding in findings:
                documents = {s.document_id for s in sides if s.finding_id == finding.id}
                assert documents == {"document-body", "document-annex"}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_worker_persisted_off_pin_survives_later_enable(monkeypatch):
    import json

    from contract_intelligence.worker import _freeze_semantic_profile

    engine, factory = await _session_factory()
    try:
        monkeypatch.setenv("AI2_SEMANTIC_ENABLED", "false")
        async with factory() as session:
            await _seed_run(session)
            run = await session.get(PipelineRunORM, RUN_ID)
            assert await _freeze_semantic_profile(session, run, TENANT_ID) is None
            await session.commit()
        monkeypatch.setenv("AI2_SEMANTIC_ENABLED", "true")
        monkeypatch.delenv("AI2_SEMANTIC_PROFILE_CONFIG", raising=False)
        async with factory() as session:
            reopened = await session.get(PipelineRunORM, RUN_ID)
            assert "semantic_profile" in json.loads(reopened.config_snapshot)
            assert await _freeze_semantic_profile(session, reopened, TENANT_ID) is None
            assert json.loads(reopened.config_snapshot)["semantic_profile"] is None
    finally:
        await engine.dispose()


def _semantic_evidence(raw: str) -> dict[str, object]:
    return {
        "document_id": "document-body",
        "snapshot_id": "snapshot-body",
        "source_ref": "node-cit-body",
        "raw": raw,
        "citation": {
            "node_id": "node-cit-body",
            "page_revision_id": "page-rev-cit-body",
            "text_span": raw,
            "source_file_id": "document-body",
            "validation_status": "VALID",
        },
    }


def _semantic_slot(value: str, raw: str) -> dict[str, object]:
    return {
        "value_type": "TEXT",
        "value": value,
        "state": "GROUNDED",
        "evidence": [_semantic_evidence(raw)],
        "reason": "",
    }


@pytest.mark.asyncio
async def test_amendment_to_an_unextracted_clause_is_persisted_without_keyerror():
    """A ``missing_target`` AMENDS edge is valid; it must not crash persistence."""
    clause = "Thanh toán trong 30 ngày."
    effective = "Phụ lục này có hiệu lực từ 2026-10-01."
    accepted = "Các bên đồng ý sửa đổi Điều 9 như sau."
    profile = {"digest": HASH, "alias_version": 0, "alias_digest": None}
    extension = {
        "schema_version": "ai2.semantic.v1",
        "tenant_id": TENANT_ID,
        "dossier_id": DOSSIER_ID,
        "profile_digest": HASH,
        "alias_version": 0,
        "alias_digest": None,
        "frames": [
            {
                "frame_id": "frame-source",
                "family": "OBLIGATION",
                "profile": "SALES",
                "document_id": "document-body",
                "snapshot_id": "snapshot-body",
                "dossier_id": DOSSIER_ID,
                "evidence": [_semantic_evidence(clause)],
                "slots": {},
                "key": {
                    "key": ["PAY"],
                    "certainty": "DEFINITE",
                    "reason": "",
                    "method": "CLOSED_SYMBOL",
                    "alias_digest": None,
                    "alias_version": None,
                    "alias_proposal_ids": [],
                },
            }
        ],
        "rows": ["frame-source"],
        "pairs": [],
        "timeline": [
            {
                "edge_id": "edge-missing-target",
                "source_id": "frame-source",
                "target_id": "frame-not-extracted",
                "relation": "AMENDS",
                "date_role": "EFFECTIVE",
                "date_value": "2026-10-01",
                "evidence": [_semantic_evidence(effective)],
                "acceptance": _semantic_slot("ACCEPTED", accepted),
                "value_slot": "deadline",
                "proposed_value": _semantic_slot("45 ngày", accepted),
                "reasons": ["missing_target"],
            }
        ],
        "alias_drafts": [],
        "coverage": {
            "state": "NEEDS_REVIEW",
            "attempted_nodes": 1,
            "frames": 1,
            "grounded_slots": 0,
            "unresolved_slots": 0,
            "invalid_evidence": 0,
            "reasons": [],
            "context_nodes": 0,
            "context_calls": 0,
        },
    }
    engine, factory = await _session_factory()
    try:
        async with factory() as session:
            await _seed_run(session)
            run = await session.get(PipelineRunORM, RUN_ID)
            assert run is not None
            run.config_snapshot = json.dumps({"semantic_profile": profile})
            result = complete_result()
            result["result"]["semantic_extension"] = extension
            await persist_ai2_processing_result(
                session, tenant_id=TENANT_ID, dossier_id=DOSSIER_ID, result=result, run_id=RUN_ID
            )
            await session.commit()
            loaded = await load_ai2_read_model(session, tenant_id=TENANT_ID, run_id=RUN_ID)
            timeline = loaded.payload["result"]["semantic_extension"]["timeline"]
            assert [edge["edge_id"] for edge in timeline] == ["edge-missing-target"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_worker_does_not_pin_aliases_after_the_expert_assignment_expired(monkeypatch):
    from datetime import UTC, datetime, timedelta

    from contract_intelligence.shared.ai.tenant_lexicon_contracts import digest_json
    from contract_intelligence.shared.ai.tenant_lexicon_store import (
        ExpertAssignmentORM,
        LexiconVersionORM,
    )
    from contract_intelligence.worker import _freeze_semantic_profile

    alias = {"source": "trả tiền", "symbol": "PAY", "kind": "action", "proposal_id": "p-1"}
    stored = {
        "active_aliases": [alias],
        "activation_state": "ACTIVE",
        "policy_digest": HASH,
        "alias_digest": digest_json({"tenant_id": TENANT_ID, "version": 3, "aliases": [alias]}),
    }
    monkeypatch.setenv("AI2_SEMANTIC_ENABLED", "true")
    monkeypatch.setenv(
        "AI2_SEMANTIC_PROFILE_CONFIG",
        json.dumps(
            {
                "version": 1,
                "contract_type": "SALES",
                "context_bounds": {
                    "max_hops": 2,
                    "max_nodes": 256,
                    "max_context_tokens": 32768,
                    "max_output_tokens": 8192,
                    "max_llm_calls": 20,
                    "max_seconds": 300,
                },
                "alias_proposal_minimum_length": 4,
            }
        ),
    )
    engine, factory = await _session_factory()
    try:
        async with factory() as session:
            await _seed_run(session)
            session.add_all(
                [
                    LexiconVersionORM(
                        tenant_id=TENANT_ID, version=3, digest=HASH, profile=stored
                    ),
                    ExpertAssignmentORM(
                        tenant_id=TENANT_ID,
                        version=1,
                        expert_id="expert",
                        designated_by="admin",
                        expertise_ref="attestation-1",
                        expires_at=datetime.now(UTC) - timedelta(days=1),
                    ),
                ]
            )
            await session.commit()
            run = await session.get(PipelineRunORM, RUN_ID)
            profile = await _freeze_semantic_profile(session, run, TENANT_ID)

        assert profile is not None
        assert profile["alias_version"] == 3
        assert profile["aliases"] == []
        assert profile["activation_state"] == "DRAFT_ONLY"
    finally:
        await engine.dispose()
