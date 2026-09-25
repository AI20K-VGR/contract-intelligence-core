from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from app.contracts.canonical import BoundaryStatus, EvidenceState, ReviewState
from app.pipeline.canonical import build_canonical_run
from app.pipeline.ai1_snapshot_adapter import adapt_to_canonical_ai2_run


def _input() -> dict:
    return {
        "schema_version": "ai2.canonical.input.v1",
        "input_snapshot_id": "input-p1-001",
        "state_version": 7,
        "logical_documents": [
            {
                "document_id": "doc-body",
                "role": "body",
                "raw_source": {"kind": "ocr.json", "payload": {"text": "Hợp đồng"}},
                "pages": [
                    {
                        "page_id": "page-body-1",
                        "language": "vi/en",
                        "blocks": [
                            {"block_id": "body-b1", "text": "Điều 1. Scope"},
                            {"block_id": "body-b2", "text": "See Annex 1."},
                        ],
                        "tables": [],
                    }
                ],
                "boundaries": [
                    {
                        "boundary_id": "boundary-body-1",
                        "start_ref": "body-b1",
                        "end_ref": "body-b2",
                        "evidence_refs": ["body-b1", "body-b2"],
                        "confidence": 0.96,
                        "status": "PROPOSED",
                    }
                ],
            },
            {
                "document_id": "doc-annex",
                "role": "annex",
                "raw_source": {"kind": "ocr.json", "payload": {"text": "Phụ lục 1"}},
                "pages": [
                    {
                        "page_id": "page-annex-1",
                        "language": "vi",
                        "blocks": [{"block_id": "annex-b1", "text": "Phụ lục 1"}],
                        "tables": [],
                    }
                ],
                "boundaries": [],
            },
        ],
        "relations": [
            {
                "relation_id": "relation-annex-1",
                "type": "ANNEX_OF",
                "from_document_id": "doc-annex",
                "to_document_id": "doc-body",
                "evidence_refs": ["body-b2", "annex-b1"],
                "review_decision": "CONFIRMED",
            }
        ],
    }


def test_one_json_maps_many_documents_and_keeps_raw_source_immutable():
    payload = _input()
    original = deepcopy(payload)

    run = build_canonical_run(payload)

    assert payload == original
    assert [document.role.value for document in run.documents] == ["body", "annex"]
    assert run.input_snapshot.raw_source == original
    assert run.documents[0].raw_source == original["logical_documents"][0]["raw_source"]
    assert run.documents[0].boundaries[0].status is BoundaryStatus.PROPOSED
    assert run.generation.input_snapshot_id == "input-p1-001"
    assert run.generation.segmentation_version == "segmentation.v1"
    assert run.generation.state_version == 7


def test_body_annex_relation_requires_evidence_or_reviewer_decision():
    payload = _input()
    payload["relations"][0]["evidence_refs"] = []
    payload["relations"][0].pop("review_decision")

    run = build_canonical_run(payload)

    relation = run.relations[0]
    assert relation.review_state is ReviewState.NEEDS_REVIEW
    assert relation.evidence_state is EvidenceState.INSUFFICIENT_EVIDENCE
    assert run.review_state is ReviewState.NEEDS_REVIEW


def test_low_confidence_boundary_and_missing_evidence_are_safe_states():
    payload = _input()
    payload["logical_documents"][0]["boundaries"][0]["confidence"] = 0.42
    payload["logical_documents"][0]["boundaries"][0]["status"] = "AMBIGUOUS"
    payload["facts"] = [
        {
            "fact_id": "fact-1",
            "value": "100",
            "evidence_refs": ["not-in-source"],
        }
    ]
    payload["relations"] = [
        {
            "relation_id": "relation-missing",
            "type": "REFERENCES",
            "from_ref": "body-b1",
            "to_ref": "missing-target",
            "evidence_refs": ["not-in-source"],
        }
    ]

    run = build_canonical_run(payload)

    assert run.documents[0].boundaries[0].status is BoundaryStatus.AMBIGUOUS
    assert "LOW_CONFIDENCE_BOUNDARY" in run.quality_flags
    assert run.facts[0].evidence_state is EvidenceState.UNVERIFIABLE
    assert run.relations[0].evidence_state is EvidenceState.INSUFFICIENT_EVIDENCE
    assert run.review_state is ReviewState.NEEDS_REVIEW


def test_bilingual_table_continuation_and_truncated_clause_remain_quality_flags():
    payload = _input()
    payload["logical_documents"][0]["pages"][0]["tables"] = [
        {"table_id": "table-1", "continuation": True, "header_ref": "missing-header"}
    ]
    payload["clauses"] = [
        {"clause_id": "clause-1", "text": "Điều 1. Scope…", "truncated": True, "evidence_refs": ["body-b1"]}
    ]

    run = build_canonical_run(payload)

    assert {"BILINGUAL", "TABLE_CONTINUATION", "TRUNCATED_CLAUSE"}.issubset(run.quality_flags)
    assert run.clauses[0].quality_flags == ["TRUNCATED"]


def test_citation_mismatch_downgrades_fact_even_when_reference_exists():
    payload = _input()
    payload["facts"] = [
        {
            "fact_id": "fact-mismatch",
            "value": "100",
            "evidence_refs": ["body-b1"],
            "citations": [{"evidence_ref": "body-b1", "text": "text absent from block"}],
        }
    ]

    run = build_canonical_run(payload)

    assert run.facts[0].citations[0].status == "MISMATCH"
    assert run.facts[0].evidence_state is EvidenceState.INSUFFICIENT_EVIDENCE
    assert run.review_state is ReviewState.NEEDS_REVIEW


def test_annotation_edit_does_not_stale_evidence_but_boundary_edit_does():
    run = build_canonical_run(_input())

    annotation_impact = run.mark_edit("annotation", "annotation-1")
    boundary_impact = run.mark_edit("boundary", "boundary-body-1")

    assert annotation_impact.stale_artifact_ids == []
    assert boundary_impact.stale_artifact_ids
    assert "generation:input-p1-001" in boundary_impact.stale_artifact_ids
    assert "input:input-p1-001" not in boundary_impact.stale_artifact_ids
    assert run.dependencies.is_stale("generation:input-p1-001")


def test_official_ai1_snapshot_maps_without_changing_compatibility_shape():
    root = Path(__file__).resolve().parents[2]
    payload = json.loads(
        (root / "docs" / "contracts" / "examples" / "ai1.snapshot.v1.body.example.json").read_text(
            encoding="utf-8"
        )
    )
    original = deepcopy(payload)

    run = adapt_to_canonical_ai2_run(
        payload,
        user_context={"requested_by": "reviewer-1", "evidence_refs": ["fake"]},
    )

    assert payload == original
    assert run.input_snapshot.snapshot_id == payload["snapshot_id"]
    assert run.documents[0].raw_source == payload
    assert payload["pages"][0]["page_revision_id"] in run.documents[0].source_refs
    assert run.user_context == {"requested_by": "reviewer-1", "evidence_refs": ["fake"]}
    assert all("fake" not in fact.evidence_refs for fact in run.facts)


@pytest.mark.parametrize("edit_kind", ["fact", "relation"])
def test_fact_or_relation_edit_stales_derived_generation(edit_kind: str):
    run = build_canonical_run(_input())

    impact = run.mark_edit(edit_kind, f"{edit_kind}-1")

    assert "generation:input-p1-001" in impact.stale_artifact_ids
