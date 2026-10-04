from __future__ import annotations

import copy
import hashlib
import json
from decimal import Decimal

import pytest

from app.contracts.models import SemanticExtension, SemanticProfile
from app.pipeline.frame_context import build_semantic_extension
from app.pipeline.idp import run_idp
from app.pipeline.runtime import ProcessingRuntime
from app.tools.persist import record_from_dict, record_to_dict
from fixtures import envelope, mock_record


def semantic_profile(tenant_id="tenant_a"):
    payload = dict(
        schema_version="ai2.semantic-profile.v1",
        capability="ai2.semantic.v1",
        tenant_id=tenant_id,
        version=1,
        contract_type="SALES",
        alias_version=0,
        alias_digest=None,
        aliases=[],
        activation_state="DRAFT_ONLY",
        alias_proposal_minimum_length=None,
        context_bounds=dict(
            max_hops=2,
            max_nodes=10,
            max_context_tokens=4000,
            max_output_tokens=500,
            max_llm_calls=1,
            max_seconds=5,
        ),
    )
    payload["digest"] = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return SemanticProfile.model_validate(payload)


def semantic_record():
    record = mock_record()
    record.egress_approved = False
    record.semantic_profile = semantic_profile()
    record.semantic_snapshots = {"body-file": "snapshot-body"}
    record.nodes = record.nodes[:1]
    node = record.nodes[0]
    node.type, node.has_children, node.source_file_id = "CLAUSE", False, "body-file"
    node.text = "Bên A phải thanh toán 9007199254740993 VND; Bên B không được tiết lộ thông tin"
    node.source_line_ids = ["line-1"]
    page = record.pages[0]
    page.text = node.text
    page.line_texts = {"line-1": node.text}
    page.source_file_id = "body-file"
    page.source_hash = "a" * 64
    return record


def test_semantic_job_default_off_then_full_three_and_exact_decimal(monkeypatch):
    record = semantic_record()
    monkeypatch.delenv("AI2_SEMANTIC_ENABLED", raising=False)
    result = run_idp(record, envelope())
    assert result.contribution.semantic_extension is None
    monkeypatch.setenv("AI2_SEMANTIC_ENABLED", "true")
    monkeypatch.setenv(
        "AI2_SEMANTIC_CONTEXT_CAPS", json.dumps(record.semantic_profile.context_bounds.model_dump())
    )
    result = run_idp(record, envelope())
    extension = result.contribution.semantic_extension
    assert extension.schema_version == "ai2.semantic.v1"
    assert len(extension.frames) == len(extension.rows) == 2
    amount = extension.frames[0].slots["amount"]
    assert amount.value_type == "DECIMAL" and amount.value == str(Decimal("9007199254740993"))
    assert extension.frames[0].evidence[0].citation.validation_status == "VALID"
    assert "timeline_chain_not_supplied" in extension.coverage.reasons
    assert result.review_state.value == "NEEDS_REVIEW"
    reopened = record_from_dict(record_to_dict(record))
    assert reopened.semantic_extension == extension
    assert reopened.semantic_profile == record.semantic_profile


def test_profile_digest_tenant_closed_and_mutation():
    profile = semantic_profile()
    payload = profile.model_dump(mode="json")
    payload["version"] = 2
    with pytest.raises(ValueError, match="digest"):
        SemanticProfile.model_validate(payload)
    payload = profile.model_dump(mode="json")
    payload["surprise"] = True
    with pytest.raises(ValueError):
        SemanticProfile.model_validate(payload)
    record = semantic_record()
    record.semantic_profile = semantic_profile("other-tenant")
    with pytest.raises(ValueError, match="tenant"):
        build_semantic_extension(record, ProcessingRuntime())


def test_invalid_frame_source_retained_for_review():
    record = semantic_record()
    record.pages[0].text = "unrelated immutable source"
    extension = build_semantic_extension(record, ProcessingRuntime())
    assert extension.frames
    assert extension.coverage.invalid_evidence > 0
    assert extension.coverage.state == "NEEDS_REVIEW"
    assert all(s.state != "GROUNDED" for f in extension.frames for s in f.slots.values())
    assert (
        SemanticExtension.model_validate(copy.deepcopy(extension.model_dump(mode="json")))
        == extension
    )


def test_timeline_only_explicit_amendment_acceptance_effective_date():
    from app.contracts.models import RelationEdge, RelationGraph

    record = semantic_record()
    original = record.nodes[0]
    original.text = "Bên A phải thanh toán 100 VND"
    amendment = original.model_copy(
        deep=True,
        update={
            "node_id": "amendment",
            "text": "Các bên đồng ý sửa đổi Bên A phải thanh toán 200 VND có hiệu lực từ 2026-10-03",
        },
    )
    record.nodes = [original, amendment]
    record.pages[0].text = original.text + "\n" + amendment.text
    record.pages[0].line_texts = {"line-1": original.text, "line-2": amendment.text}
    amendment.source_line_ids = ["line-2"]
    record.relation_graph = RelationGraph(
        graph_id="graph",
        source_snapshot_digest=record.pins.source_snapshot_digest,
        edges=[
            RelationEdge(
                edge_id="amends",
                from_node_id="amendment",
                to_node_id=original.node_id,
                relation_type="AMENDS",
                support="EXPLICIT_TEXT",
                source_snapshot_digest=record.pins.source_snapshot_digest,
            )
        ],
    )
    result = build_semantic_extension(record, ProcessingRuntime())
    assert len(result.timeline) == 1
    edge = result.timeline[0]
    assert edge.date_role == "EFFECTIVE" and edge.date_value == "2026-10-03"
    assert edge.proposed_value.value == "200" and edge.review_state == "NEEDS_REVIEW"
    assert len(result.pairs) == 1 and result.pairs[0].candidate_sources == [
        "EXPLICIT_REF",
        "SAME_KEY",
    ]


def test_job_uses_only_active_pinned_alias_and_keeps_method():
    from app.pipeline.tenant_aliases import ApprovedAlias, ApprovedAliasSnapshot

    record = semantic_record()
    record.nodes[0].text = "Bên A phải trả tiền"
    record.pages[0].text = record.nodes[0].text
    record.pages[0].line_texts = {"line-1": record.nodes[0].text}
    payload = record.semantic_profile.model_dump(mode="json", exclude={"digest"})
    alias = ApprovedAlias("trả tiền", "PAY", "action", "proposal-approved")
    snapshot = ApprovedAliasSnapshot(record.tenant_id, 7, (alias,))
    payload.update(
        aliases=[
            dict(
                source=alias.source,
                symbol=alias.symbol,
                kind=alias.kind,
                proposal_id=alias.proposal_id,
            )
        ],
        alias_version=7,
        alias_digest=snapshot.digest,
        activation_state="ACTIVE",
    )
    payload["digest"] = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    record.semantic_profile = SemanticProfile.model_validate(payload)
    extension = build_semantic_extension(record, ProcessingRuntime())
    assert extension.frames[0].key.method == "TENANT_ALIAS"
    assert extension.frames[0].key.alias_version == 7
    assert extension.frames[0].key.alias_proposal_ids == ["proposal-approved"]


@pytest.mark.parametrize("target_count", [0, 1, 2])
def test_same_heading_explicit_amendment_recovers_or_keeps_branch_review(target_count):
    from app.contracts.models import RelationGraph

    record = semantic_record()
    original = record.nodes[0]
    original.raw_label = "\u0110i\u1ec1u 1"
    original.text = "\u0110i\u1ec1u 1. B\u00ean A ph\u1ea3i thanh to\u00e1n 100 VND"
    amendment = original.model_copy(
        deep=True,
        update={
            "node_id": "annex-amendment",
            "text": "\u0110i\u1ec1u 1. C\u00e1c b\u00ean \u0111\u1ed3ng \u00fd s\u1eeda \u0111\u1ed5i \u0110i\u1ec1u 1: B\u00ean A ph\u1ea3i thanh to\u00e1n 200 VND c\u00f3 hi\u1ec7u l\u1ef1c t\u1eeb 2026-10-03",
        },
    )
    targets = [
        original.model_copy(
            deep=True, update={"node_id": f"target-{i}", "text": original.text + f" v{i}"}
        )
        for i in range(target_count)
    ]
    record.nodes = [*targets, amendment]
    for i, node in enumerate(record.nodes):
        node.source_line_ids = [f"line-{i}"]
    record.pages[0].text = "\n".join(node.text for node in record.nodes)
    record.pages[0].line_texts = {node.source_line_ids[0]: node.text for node in record.nodes}
    record.relation_graph = RelationGraph(
        graph_id="graph", source_snapshot_digest=record.pins.source_snapshot_digest
    )
    extension = build_semantic_extension(record, ProcessingRuntime())
    assert extension.timeline
    if target_count == 1:
        assert any(
            edge.proposed_value and edge.proposed_value.value == "200"
            for edge in extension.timeline
        )
        assert "EXPLICIT_REF" in extension.pairs[0].candidate_sources
    else:
        assert all(
            edge.target_id is None and edge.proposed_value is None for edge in extension.timeline
        )
        assert all("missing_target" in edge.reasons for edge in extension.timeline)
        if target_count == 2:
            assert (
                len([pair for pair in extension.pairs if "EXPLICIT_REF" in pair.candidate_sources])
                == 2
            )


def test_multiple_invalid_explicit_targets_keep_distinct_review_records():
    from app.contracts.models import RelationGraph

    record = semantic_record()
    node = record.nodes[0]
    target = node.model_copy(
        deep=True,
        update={
            "node_id": "target-one",
            "raw_label": "\u0110i\u1ec1u 1",
            "text": "\u0110i\u1ec1u 1. B\u00ean A ph\u1ea3i thanh to\u00e1n 100 VND",
        },
    )
    second = target.model_copy(deep=True, update={"node_id": "target-two"})
    source = node.model_copy(
        deep=True,
        update={
            "node_id": "source",
            "raw_label": "\u0110i\u1ec1u 1",
            "text": "\u0110i\u1ec1u 1. C\u00e1c b\u00ean \u0111\u1ed3ng \u00fd s\u1eeda \u0111\u1ed5i \u0110i\u1ec1u 1: B\u00ean A ph\u1ea3i thanh to\u00e1n 101 VND c\u00f3 hi\u1ec7u l\u1ef1c t\u1eeb 2026-10-03",
            "source_line_ids": ["source-line"],
        },
    )
    record.nodes = [target, second, source]
    record.pages[0].text = source.text
    record.pages[0].line_texts = {"source-line": source.text}
    record.relation_graph = RelationGraph(
        graph_id="graph", source_snapshot_digest=record.pins.source_snapshot_digest
    )
    result = build_semantic_extension(record, ProcessingRuntime())
    assert len(result.timeline) == 2
    assert len({edge.edge_id for edge in result.timeline}) == 2
    assert all(
        edge.proposed_value is None and "missing_target" in edge.reasons for edge in result.timeline
    )
    assert "explicit_amendment_target_invalid" in result.coverage.reasons
