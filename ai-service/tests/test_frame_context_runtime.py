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


def test_slot_context_prompt_names_json_for_provider_json_mode(monkeypatch):
    from app.contracts.clause_frames import ClauseFrame, Evidence, Slot
    from app.pipeline import frame_context
    from app.pipeline.frame_context import _enrich

    record = semantic_record()
    node = record.nodes[0]
    bounds = record.semantic_profile.context_bounds
    evidence = Evidence("doc-1", "snapshot-1", node.node_id, node.text)
    frame = ClauseFrame(
        "frame-1",
        "OBLIGATION",
        "SALES",
        "doc-1",
        "snapshot-1",
        (evidence,),
        (("action", Slot("PAY", "GROUNDED", (evidence,))), ("deadline", Slot(None, "UNKNOWN", ()))),
        "dossier",
    )
    prompts = []

    def complete_json(_runtime, _client, system, user, **_kwargs):
        prompts.append(f"{system}\n{user}")
        return {"slots": []}

    monkeypatch.setattr(ProcessingRuntime, "complete_json", complete_json)
    # One-node fixture has no parent; any context is enough to reach the provider call.
    monkeypatch.setattr(frame_context, "context_nodes", lambda *_a: ((node,), ()))
    monkeypatch.setattr(
        frame_context, "_groundable", lambda *_a: True
    )  # isolate from the pre-call gate
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=5)
    _enrich(
        record,
        (frame,),
        runtime,
        SimpleNamespace(configured=lambda: True),
        bounds,
        runtime.clock() + 60,
        0,
    )

    assert prompts, "fixture must reach the slot-context LLM call"
    assert all("json" in p.casefold() for p in prompts)


def test_proposal_citing_an_empty_context_node_is_rejected_not_raised(monkeypatch):
    # gpt-5.6-luna named the empty root node as a slot source; Evidence() raised and the
    # whole IDP job crashed. An ungrounded proposal is dropped like any other.
    from app.contracts.clause_frames import ClauseFrame, Evidence, Slot
    from app.contracts.models import StructuralNode
    from app.pipeline import frame_context
    from app.pipeline.frame_context import _enrich

    record = semantic_record()
    node = record.nodes[0]
    empty = StructuralNode(
        node_id="ai2-root:body-file",
        type="SECTION",
        raw_label="",
        text="",
        source_file_id=node.source_file_id,
    )
    evidence = Evidence("doc-1", "snapshot-1", node.node_id, node.text)
    frame = ClauseFrame(
        "frame-1",
        "OBLIGATION",
        "SALES",
        "doc-1",
        "snapshot-1",
        (evidence,),
        (("action", Slot("PAY", "GROUNDED", (evidence,))), ("deadline", Slot(None, "UNKNOWN", ()))),
        "dossier",
    )
    monkeypatch.setattr(
        ProcessingRuntime,
        "complete_json",
        lambda *_a, **_k: {
            "frames": [
                {
                    "id": "f1",
                    "slots": [{"slot": "deadline", "node_id": empty.node_id, "value": "5"}],
                }
            ]
        },
    )
    monkeypatch.setattr(frame_context, "context_nodes", lambda *_a: ((node, empty), ()))
    monkeypatch.setattr(
        frame_context, "_groundable", lambda *_a: True
    )  # isolate from the pre-call gate
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=5)
    _, _, _, reasons, _ = _enrich(
        record,
        (frame,),
        runtime,
        SimpleNamespace(configured=lambda: True),
        record.semantic_profile.context_bounds,
        runtime.clock() + 60,
        0,
    )
    assert "PROPOSAL_SOURCE_NOT_GROUNDED" in reasons


def _batch_setup(monkeypatch, n_frames, respond):
    from app.contracts.clause_frames import ClauseFrame, Evidence, Slot
    from app.pipeline import frame_context

    record = semantic_record()
    node = record.nodes[0]
    frames = []
    for i in range(n_frames):
        evidence = Evidence("doc-1", "snapshot-1", f"{node.node_id}#span{i}", node.text)
        frames.append(
            ClauseFrame(
                f"frame-{i}",
                "OBLIGATION",
                "SALES",
                "doc-1",
                "snapshot-1",
                (evidence,),
                (
                    ("action", Slot("PAY", "GROUNDED", (evidence,))),
                    ("deadline", Slot(None, "UNKNOWN", ())),
                ),
                "dossier",
            )
        )
    calls = []

    def complete_json(_runtime, _client, system, user, **_kwargs):
        calls.append(json.loads(user))
        _runtime.llm_calls_used += 1
        return respond(json.loads(user))

    monkeypatch.setattr(ProcessingRuntime, "complete_json", complete_json)
    monkeypatch.setattr(frame_context, "context_nodes", lambda *_a: ((node,), ()))
    monkeypatch.setattr(
        frame_context, "_groundable", lambda *_a: True
    )  # isolate from the pre-call gate
    bounds = record.semantic_profile.context_bounds.model_copy(
        update={"max_llm_calls": 20, "max_nodes": 256, "max_context_tokens": 100_000}
    )
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=20)
    out = frame_context._enrich(
        record,
        tuple(frames),
        runtime,
        SimpleNamespace(configured=lambda: True),
        bounds,
        runtime.clock() + 60,
        0,
    )
    return calls, out


def test_slot_context_batches_frames_into_few_calls(monkeypatch):
    # One call per frame spent the whole job budget on ~12 frames; a batch carries several.
    calls, (frames, _, used, reasons, _) = _batch_setup(
        monkeypatch,
        10,
        lambda payload: {"frames": [{"id": f["id"], "slots": []} for f in payload["frames"]]},
    )
    assert len(calls) == 2 and used == 2
    assert [len(c["frames"]) for c in calls] == [8, 2]
    assert len(frames) == 10 and "PROPOSAL_FRAME_MISSING" not in reasons


def test_frame_missing_from_batch_answer_is_kept_unchanged(monkeypatch):
    calls, (frames, _, _, reasons, _) = _batch_setup(
        monkeypatch,
        3,
        lambda payload: {"frames": [{"id": payload["frames"][0]["id"], "slots": []}]},
    )
    assert len(frames) == 3 and reasons.count("PROPOSAL_FRAME_MISSING") == 2


def _two_clause_record(context_text):
    record = semantic_record()
    frame_node = record.nodes[0]
    frame_node.text = "Bên A thanh toán đợt 2 theo thời hạn quy định tại khoản 2 Điều 5."
    ctx = frame_node.model_copy(
        update={"node_id": "ctx-1", "text": context_text, "source_line_ids": ["line-2"]}
    )
    record.nodes.append(ctx)
    page = record.pages[0]
    page.text = f"{frame_node.text}\n{context_text}"
    page.line_texts = {"line-1": frame_node.text, "line-2": context_text}
    return record, frame_node, ctx


def _run_enrich(monkeypatch, record, frame_node, ctx, respond):
    from app.contracts.clause_frames import Evidence
    from app.pipeline import frame_context
    from app.pipeline.frame_extraction import extract_frames

    frame = extract_frames(
        Evidence("body-file", "snapshot-body", frame_node.node_id, frame_node.text),
        profile="SALES",
        dossier_id=record.dossier_id,
    )[0]
    calls = []

    def complete_json(_runtime, _client, system, user, **_kwargs):
        calls.append(json.loads(user))
        _runtime.llm_calls_used += 1
        return respond(json.loads(user))

    monkeypatch.setattr(ProcessingRuntime, "complete_json", complete_json)
    monkeypatch.setattr(frame_context, "context_nodes", lambda *_a: ((ctx,), ()))
    bounds = record.semantic_profile.context_bounds.model_copy(
        update={"max_llm_calls": 5, "max_context_tokens": 100_000}
    )
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=5)
    frames, *_rest = frame_context._enrich(
        record,
        (frame,),
        runtime,
        SimpleNamespace(configured=lambda: True),
        bounds,
        runtime.clock() + 60,
        0,
    )
    return calls, frames[0], _rest[2]


def test_context_slot_is_filled_when_a_referenced_clause_grounds_it(monkeypatch):
    record, frame_node, ctx = _two_clause_record(
        "5.2. Bên A thanh toán mỗi đợt trong vòng 07 ngày kể từ ngày nhận được hóa đơn hợp lệ."
    )
    calls, frame, reasons = _run_enrich(
        monkeypatch,
        record,
        frame_node,
        ctx,
        lambda p: {
            "frames": [
                {
                    "id": p["frames"][0]["id"],
                    "slots": [{"slot": "deadline", "node_id": "ctx-1", "value": "07"}],
                }
            ]
        },
    )
    assert len(calls) == 1
    assert (frame.get("deadline").state, frame.get("deadline").value) == ("GROUNDED", "07"), reasons


def test_no_llm_call_when_no_context_clause_can_ground_a_missing_slot(monkeypatch):
    # The validator only accepts a value the context clause already grounds with the same
    # actor/action/modality; without such a clause every call was paid for nothing.
    record, frame_node, ctx = _two_clause_record("Bên B giao hàng tại kho của Bên A.")
    calls, frame, reasons = _run_enrich(
        monkeypatch, record, frame_node, ctx, lambda p: {"frames": []}
    )
    assert calls == [] and "context_no_groundable_source" in reasons
