from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.contracts.contract_graph import PairLabel, PairRelation, pair_relation_id_for
from app.contracts.models import ReviewState
from app.llm.client import NineRouterClient
from app.pipeline.contract_graph import pair_builder as builder
from app.pipeline.contract_graph.pair_candidates import PairCandidate, PairCandidateSet, PairSource
from app.pipeline.runtime import ProcessingRuntime
from fixtures.contract_graph_records import Spec, dossier

TEXT_A = "Bên Mua thanh toán trong 30 ngày kể từ ngày nhận hóa đơn."
TEXT_B = "Bên Mua thanh toán trong 15 ngày kể từ ngày nhận hóa đơn."


@pytest.fixture(autouse=True)
def _offline_pairs_env(monkeypatch):
    for key in (builder.PAIRS_BASE_URL_ENV, builder.PAIRS_API_KEY_ENV, builder.PAIRS_MODEL_ENV, builder.PAIRS_ENV):
        monkeypatch.delenv(key, raising=False)


class Client:
    def __init__(self, direction=None):
        self.traces = []
        self.messages = []
        self.direction = direction

    def configured(self):
        return True

    def complete_json(self, system, user, **kwargs):
        self.messages.append(json.loads(user))
        self.traces.append({"served_model": "claude-test", "prompt_tokens": 10,
                            "completion_tokens": 5, "latency_ms": 2})
        label = "GENERAL_SPECIFIC" if self.direction else "CONFLICT"
        return {"results": [{"id": "p1", "label": label, "span_a": TEXT_A,
                             "span_b": TEXT_B, "general": self.direction}]}


def record():
    out = dossier([("f", "body", [Spec("d3", "Điều 3", "Thanh toán"),
                                    Spec("a", "1.", TEXT_A, "d3"),
                                    Spec("b", "2.", TEXT_B, "d3")])], [])
    out.content_sharing_consent = True
    return out


def runtime():
    return ProcessingRuntime(egress_allowed=True, max_llm_calls=10, max_processing_seconds=1000)


def build(rec=None, **kwargs):
    return builder.build_pair_relations(rec or record(), [], llm=kwargs.pop("llm", Client()),
                                       runtime=kwargs.pop("runtime", runtime()), model="claude-test", **kwargs)


def test_pair_relation_rejects_pass():
    relation = build().relations[0]
    with pytest.raises(ValueError):
        PairRelation(**{**relation.model_dump(), "review_state": ReviewState.PASS})
    with pytest.raises(ValueError):
        PairRelation(**{**relation.model_dump(), "legal_winner": "a"})


def test_relation_id_stable_across_spans():
    one = pair_relation_id_for("digest", PairLabel.CONFLICT, "a", "b")
    assert one == pair_relation_id_for("digest", PairLabel.CONFLICT, "a", "b")
    assert one.startswith("cpair:") and len(one) == 30
    assert one != pair_relation_id_for("different", PairLabel.CONFLICT, "a", "b")


@pytest.mark.parametrize("changes,expected", [
    ({"consent": False, "egress": False}, "NO_CONSENT"),
    ({"egress": False, "llm": None}, "EGRESS_DENIED"),
    ({"llm": None, "model": ""}, "LLM_UNAVAILABLE"),
    ({"llm": SimpleNamespace(configured=lambda: False)}, "LLM_UNAVAILABLE"),
    ({"model": ""}, "MODEL_UNSET"),
    ({"budget": 0, "remaining": 1}, "BUDGET_EXHAUSTED"),
    ({"remaining": 120}, "DEADLINE"), ({}, None),
])
def test_gate_order(changes, expected, monkeypatch):
    for key in (builder.PAIRS_BASE_URL_ENV, builder.PAIRS_API_KEY_ENV):
        monkeypatch.delenv(key, raising=False)
    rec, rt = record(), runtime()
    rec.content_sharing_consent = changes.get("consent", True)
    rt.egress_allowed = changes.get("egress", True)
    rt.max_llm_calls = changes.get("budget", 10)
    if "remaining" in changes:
        rt.remaining = lambda: changes["remaining"]
    assert builder.gate(rec, changes.get("llm", Client()), rt, changes.get("model", "claude-test")) == expected


def test_rule_only_makes_no_llm_call_and_counts_candidates():
    rec, client = record(), Client()
    rec.content_sharing_consent = False
    result = build(rec, llm=client)
    assert result.mode == "rule_only" and result.rule_only_reason == "NO_CONSENT"
    assert result.relations == [] and result.batches_completed == 0
    assert result.stats["candidates_kept"] > 0
    assert client.messages == []


def test_llm_mode_builds_relations_with_valid_citations():
    result = build()
    assert result.mode == "llm" and result.rule_only_reason is None
    relation = result.relations[0]
    assert relation.citation_a.validation_status == relation.citation_b.validation_status == "VALID"
    assert relation.node_a_id == "a" and relation.node_b_id == "b" and relation.directed is False
    assert relation.review_state == ReviewState.NEEDS_REVIEW
    assert result.node_parts == {"a": "body:f", "b": "body:f"}


def test_direction_b_swaps_nodes_and_spans():
    relation = build(llm=Client("B")).relations[0]
    assert relation.directed and relation.node_a_id == "b" and relation.span_a == TEXT_B
    assert relation.citation_a.node_id == "b"


def test_invalid_citation_dropped():
    rec = record()
    rec.pages[0].source_hash = None
    result = build(rec)
    assert result.relations == []
    assert result.stats["rejected"]["citation_invalid"] == 1


def test_luong1_edges_excluded_from_candidates():
    result = builder.build_pair_relations(record(), [SimpleNamespace(source_node_id="a", target_node_id="b")],
                                         llm=Client(), runtime=runtime(), model="claude-test")
    assert result.stats["candidates_kept"] == 0 and not result.relations


def test_classifier_client_env_override_and_inherit(monkeypatch):
    base = NineRouterClient(base_url="http://base.test/v1", api_key="base-test", model="gpt-test")
    monkeypatch.setenv(builder.PAIRS_BASE_URL_ENV, "http://pairs.test/v1")
    monkeypatch.setenv(builder.PAIRS_API_KEY_ENV, "pairs-test")
    own = builder.classifier_client(base, "claude-test")
    assert own.base_url == "http://pairs.test/v1" and own.api_key == "pairs-test"
    assert own.model == "claude-test"
    assert builder.classifier_client(None, "claude-test").base_url == own.base_url
    monkeypatch.delenv(builder.PAIRS_BASE_URL_ENV)
    monkeypatch.delenv(builder.PAIRS_API_KEY_ENV)
    inherited = builder.classifier_client(base, "claude-test")
    assert inherited.base_url == base.base_url and inherited.api_key == base.api_key
    assert inherited.model == "claude-test"
    assert builder.classifier_client(None, "claude-test") is None
    fake = Client()
    assert builder.classifier_client(fake, "claude-test") is fake


@pytest.mark.parametrize("value,expected", [("1", True), ("true", True), ("YES", True), ("on", True),
                                          ("0", False), ("", False), ("anything", False)])
def test_pairs_enabled_truthy_values(monkeypatch, value, expected):
    monkeypatch.setenv(builder.PAIRS_ENV, value)
    assert builder.pairs_enabled() is expected


def test_builder_does_not_mutate_record():
    rec = record()
    before = copy.deepcopy(rec)
    build(rec)
    assert rec == before


def test_stats_keys_fixed():
    llm_result = build()
    rec = record()
    rec.content_sharing_consent = False
    fallback = build(rec)
    assert set(llm_result.stats) == set(fallback.stats)
    assert set(llm_result.stats["rejected"]) == set(fallback.stats["rejected"])
    assert {"pairs_sent", "pairs_unclassified", "llm_calls", "prompt_tokens", "completion_tokens",
            "injection_signals", "relations_total", "relations_by_label", "rejected",
            "stopped_reason", "served_model"} <= set(llm_result.stats)


def test_runtime_never_passes_eval_overrides():
    signature = inspect.signature(builder.build_pair_relations)
    assert "skip_gate" not in signature.parameters
    import ast
    for path in Path("app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "build_pair_relations":
                assert not {"candidates", "max_calls"} & {k.arg for k in node.keywords}


def test_token_and_served_model_stats_from_traces():
    result = build()
    assert result.stats["prompt_tokens"] == 10 and result.stats["completion_tokens"] == 5
    assert result.stats["served_model"] == "claude-test"
    assert result.classifier_model == result.relations[0].classifier_model == "claude-test"
    assert result.stats["llm_calls"] == 1


def test_sources_variant_b_passthrough(monkeypatch):
    real = builder.generate_pair_candidates
    seen = []
    def wrapped(*args, **kwargs):
        seen.append(kwargs["sources"])
        return real(*args, **kwargs)
    monkeypatch.setattr(builder, "generate_pair_candidates", wrapped)
    allowed = frozenset({PairSource.SAME_ARTICLE, PairSource.EXPLICIT_REF})
    build(sources=allowed)
    assert seen == [allowed]


def test_batches_completed_reported():
    assert build().batches_completed == 1


def test_eval_candidates_cannot_bypass_gate():
    rec = record()
    rec.content_sharing_consent = False
    client = Client()
    candidates = PairCandidateSet((PairCandidate("a", "b", frozenset(), 0, None),), {})
    result = build(rec, llm=client, candidates=candidates, max_calls=100)
    assert result.mode == "rule_only" and not client.messages


def test_eval_candidates_have_fixed_stat_defaults():
    result = build(candidates=PairCandidateSet((PairCandidate("a", "b", frozenset(), 0, None),)))
    assert set(result.stats) == set(build().stats)
    assert result.stats["candidates_kept"] == result.stats["candidates_total"] == 1


def test_runtime_gpt_response_cannot_create_relation():
    class WrongProvider(Client):
        def complete_json(self, *args, **kwargs):
            result = super().complete_json(*args, **kwargs)
            self.traces[-1]["served_model"] = "gpt-4o-mini"
            return result
    result = build(llm=WrongProvider())
    assert not result.relations and result.batches_completed == 0
    assert result.stats["stopped_reason"] == "LLM_FALLBACK"


def test_duplicate_relations_are_deduplicated():
    class AllPairs(Client):
        def complete_json(self, system, user, **kwargs):
            result = super().complete_json(system, user, **kwargs)
            result["results"] = [{**result["results"][0], "id": p["id"]} for p in json.loads(user)["pairs"]]
            return result
    candidate = PairCandidate("a", "b", frozenset({PairSource.SAME_ARTICLE}), 1, None)
    result = build(llm=AllPairs(), candidates=PairCandidateSet((candidate, candidate)))
    assert len(result.relations) == result.stats["relations_total"] == 1


def test_relation_id_excludes_span_choice():
    class ShortSpans(Client):
        def complete_json(self, *args, **kwargs):
            result = super().complete_json(*args, **kwargs)
            result["results"][0].update(span_a="thanh toán trong 30 ngày", span_b="thanh toán trong 15 ngày")
            return result
    full = build().relations[0]
    short = build(llm=ShortSpans()).relations[0]
    assert full.span_a != short.span_a and full.relation_id == short.relation_id
