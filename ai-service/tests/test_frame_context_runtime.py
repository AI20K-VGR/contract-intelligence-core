from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from test_frame_job import semantic_profile, semantic_record

from app.llm.client import NineRouterClient
from app.pipeline.frame_context import context_nodes, effective_context_bounds
from app.pipeline.runtime import ProcessingRuntime


def test_missing_caps_and_higher_request_caps_rejected(monkeypatch):
    bounds = semantic_profile().context_bounds
    monkeypatch.delenv("AI2_SEMANTIC_CONTEXT_CAPS", raising=False)
    with pytest.raises(ValueError, match="caps"):
        effective_context_bounds(bounds)
    caps = bounds.model_dump()
    caps["max_nodes"] = 1
    monkeypatch.setenv("AI2_SEMANTIC_CONTEXT_CAPS", json.dumps(caps))
    with pytest.raises(ValueError, match="cap"):
        effective_context_bounds(bounds)


def test_parent_cycle_ambiguity_and_wrong_scope_stop_context():
    record = semantic_record()
    node = record.nodes[0]
    node.parent_id = node.node_id
    selected, reasons = context_nodes(record, node.node_id, record.semantic_profile.context_bounds)
    assert selected == () and "context_cycle" in reasons
    node.parent_id = "missing"
    assert (
        "context_target_missing"
        in context_nodes(record, node.node_id, record.semantic_profile.context_bounds)[1]
    )


def test_runtime_forwards_output_cap_and_counts_calls(monkeypatch):
    calls = []
    client = NineRouterClient(api_key="local-test", model="test-model")

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"slots":[]}'))], usage=None
        )

    monkeypatch.setattr(client._client.chat.completions, "create", create)
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=1)
    assert runtime.complete_json(client, "system", "user", max_output_tokens=127) == {"slots": []}
    assert calls[0]["max_tokens"] == 127 and runtime.llm_calls_used == 1
    assert runtime.complete_json(client, "system", "user", max_output_tokens=127) is None
    assert len(calls) == 1
    denied = ProcessingRuntime(egress_allowed=False, max_llm_calls=1)
    assert denied.complete_json(client, "system", "user", max_output_tokens=127) is None
    assert len(calls) == 1


@pytest.mark.parametrize("value", [0, -1, True, float("inf"), "10"])
def test_output_cap_validated_before_provider(value):
    with pytest.raises(ValueError, match="max_output_tokens"):
        ProcessingRuntime().complete_json(None, "s", "u", max_output_tokens=value)


def test_format_fallback_keeps_cap_and_debits_same_runtime(monkeypatch):
    import httpx
    import openai

    calls = []
    client = NineRouterClient(api_key="test-only", model="test-model")

    def create(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise openai.BadRequestError(
                "response_format unsupported",
                response=httpx.Response(400, request=httpx.Request("POST", "http://provider.test")),
                body={"error": {"param": "response_format"}},
            )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"slots":[]}'))], usage=None
        )

    monkeypatch.setattr(client._client.chat.completions, "create", create)
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=2)
    assert runtime.complete_json(client, "s", "u", max_output_tokens=64) == {"slots": []}
    assert [request["max_tokens"] for request in calls] == [64, 64]
    assert runtime.llm_calls_used == 2


def test_draft_proposals_use_same_runtime_and_frozen_policy():
    import hashlib

    from app.contracts.models import SemanticProfile
    from app.pipeline.frame_context import build_semantic_extension

    record = semantic_record()
    record.nodes[0].text = "Bên A phải trả tiền"
    record.pages[0].text = record.nodes[0].text
    record.pages[0].line_texts = {"line-1": record.nodes[0].text}
    payload = record.semantic_profile.model_dump(mode="json", exclude={"digest"})
    payload["alias_proposal_minimum_length"] = 4
    payload["digest"] = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    record.semantic_profile = SemanticProfile.model_validate(payload)

    class Provider:
        def configured(self):
            return True

        def complete_json(self, system, user, **kwargs):
            return {"proposals": [{"source": "trả tiền", "symbol": "PAY", "kind": "action"}]}

    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=1)
    extension = build_semantic_extension(
        record, runtime, Provider(), record.semantic_profile.context_bounds
    )
    assert runtime.llm_calls_used == 1
    assert (
        extension.alias_drafts[0].source == "trả tiền"
        and extension.alias_drafts[0].status == "DRAFT"
    )
    assert extension.frames[0].slots["action"].state == "UNKNOWN"


def test_semantic_caps_stop_giant_unit_with_visible_source_gap():
    from app.pipeline.frame_context import build_semantic_extension

    record = semantic_record()
    record.nodes[0].text = "Bên A phải thanh toán " * 1000
    extension = build_semantic_extension(
        record, ProcessingRuntime(), bounds=record.semantic_profile.context_bounds
    )
    assert extension.frames == []
    assert any(reason.startswith("semantic_token_cap:") for reason in extension.coverage.reasons)


def test_context_retry_never_sleeps_past_operation_deadline():
    import httpx
    import openai

    now, sleeps = [0.0], []

    class Provider:
        def configured(self):
            return True

        def complete_json(self, *args, **kwargs):
            raise openai.RateLimitError(
                "retry later",
                response=httpx.Response(
                    429,
                    headers={"retry-after": "1"},
                    request=httpx.Request("POST", "http://provider.test"),
                ),
                body={},
            )

    runtime = ProcessingRuntime(
        egress_allowed=True,
        max_llm_calls=3,
        clock=lambda: now[0],
        sleep=lambda delay: (sleeps.append(delay), now.__setitem__(0, now[0] + delay)),
    )
    assert runtime.complete_json(Provider(), "s", "u", operation_deadline=0.25) is None
    assert runtime.llm_calls_used == 1 and sleeps == [] and now[0] == 0
    assert runtime.remaining() == 300
    assert any(code == "CONTEXT_TIME_CAP" for code, _ in runtime.issues)


@pytest.mark.parametrize(
    "fault,reason",
    [
        ("digest", "context_snapshot_mismatch"),
        ("support", "context_unverified_relation"),
        ("hop", "context_hop_cap"),
    ],
)
def test_reference_context_rejects_stale_heuristic_and_exhausted_chain(fault, reason):
    from app.contracts.models import RelationEdge, RelationGraph

    record = semantic_record()
    original = record.nodes[0]
    second = original.model_copy(deep=True, update={"node_id": "context-second"})
    third = original.model_copy(deep=True, update={"node_id": "context-third"})
    record.nodes = [original, second, third]
    from app.contracts.clause_frames import Evidence
    from app.pipeline.frame_context import _evidence

    citation = _evidence(
        record, Evidence(original.source_file_id, "snapshot-body", original.node_id, original.text)
    ).citation.model_dump()
    bounds = record.semantic_profile.context_bounds.model_copy(update={"max_hops": 1})
    record.relation_graph = RelationGraph(
        graph_id="graph",
        source_snapshot_digest=record.pins.source_snapshot_digest,
        edges=[
            RelationEdge(
                edge_id="ref-1",
                from_node_id=original.node_id,
                to_node_id=second.node_id,
                relation_type="REFERENCES",
                citations=[citation],
                support="HEURISTIC" if fault == "support" else "EXPLICIT_TEXT",
                source_snapshot_digest="stale"
                if fault == "digest"
                else record.pins.source_snapshot_digest,
            ),
            RelationEdge(
                edge_id="ref-2",
                from_node_id=second.node_id,
                to_node_id=third.node_id,
                relation_type="REFERENCES",
                citations=[citation],
                support="EXPLICIT_TEXT",
                source_snapshot_digest=record.pins.source_snapshot_digest,
            ),
        ],
    )
    selected, gaps = context_nodes(record, original.node_id, bounds)
    assert reason in gaps
    if fault != "hop":
        assert selected == ()
