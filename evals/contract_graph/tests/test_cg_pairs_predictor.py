from __future__ import annotations

import json

import pytest
from app.pipeline.citations import CitationResolver

from evals.contract_graph.pairs import predictor, run
from evals.contract_graph.pairs.pool import build_pool

TEXT_A = "Bên Mua thanh toán trong 30 ngày kể từ ngày nhận hóa đơn."
TEXT_B = "Bên Mua thanh toán trong 15 ngày kể từ ngày nhận hóa đơn."


@pytest.fixture(autouse=True)
def _offline_pairs_env(monkeypatch):
    from app.pipeline.contract_graph import pair_builder
    for key in (pair_builder.PAIRS_BASE_URL_ENV, pair_builder.PAIRS_API_KEY_ENV, pair_builder.PAIRS_MODEL_ENV,
                pair_builder.PAIRS_ENV):
        monkeypatch.delenv(key, raising=False)


def doc():
    return {"doc_id": "synthetic", "profile": "SALES", "text_sha256": "abc", "nodes": [
        {"node_id": "d3", "type": "SECTION", "raw_label": "Điều 3", "order": 1,
         "parent_id": None, "text": "Thanh toán", "page_range": [1], "source_file_id": "synthetic"},
        {"node_id": "a", "type": "CLAUSE", "raw_label": "1.", "order": 2,
         "parent_id": "d3", "text": TEXT_A, "page_range": [1], "source_file_id": "synthetic"},
        {"node_id": "b", "type": "CLAUSE", "raw_label": "2.", "order": 3,
         "parent_id": "d3", "text": TEXT_B, "page_range": [1], "source_file_id": "synthetic"},
    ]}


class Client:
    def __init__(self, served="claude-test"):
        self.served = served
        self.traces = []
        self.calls = 0

    def configured(self):
        return True

    def complete_json(self, system, user, **kwargs):
        self.calls += 1
        self.traces.append({"served_model": self.served, "prompt_tokens": 10,
                            "completion_tokens": 3, "latency_ms": 2})
        item = json.loads(user)["pairs"][0]
        return {"results": [{"id": item["id"], "label": "CONFLICT", "span_a": TEXT_A, "span_b": TEXT_B}]}


@pytest.mark.parametrize("served", ["gh/gpt-4o-mini", "unknown-model", None])
def test_family_check_on_served_models(served):
    client = Client(served)
    with pytest.raises(SystemExit) as error:
        predictor.predict_doc(doc(), llm=client, model="claude-requested", variant="C")
    assert error.value.code == 2 and client.calls == 1


def test_claude_served_passes_family_check():
    assert predictor.predict_doc(doc(), llm=Client(), model="claude-requested", variant="C")["predictions"]


def test_labeler_unknown_or_anthropic_refused_before_call():
    for labeler_model in ("unknown", "claude-labeler", None):
        client = Client()
        with pytest.raises(SystemExit) as error:
            predictor.predict_doc(doc(), llm=client, model="claude-requested", variant="C",
                                  labeler_served_model=labeler_model)
        assert error.value.code == 2 and client.calls == 0


def test_family_check_before_second_batch(monkeypatch):
    from app.pipeline.contract_graph.pair_candidates import PairCandidate, PairCandidateSet
    pairs = PairCandidateSet(tuple(PairCandidate("a", "b", frozenset(), 0, None) for _ in range(10)))
    monkeypatch.setattr(predictor, "candidate_set", lambda *args, **kwargs: pairs)
    client = Client("gpt-4o-mini")
    with pytest.raises(SystemExit):
        predictor.predict_doc(doc(), llm=client, model="claude-requested", variant="C")
    assert client.calls == 1


def test_heldout_refused_without_flag(monkeypatch):
    monkeypatch.setattr(predictor.manifest, "read_split", lambda *a, **k: pytest.fail("must not read heldout"))
    assert run.main(["predict", "--split", "heldout", "--variant", "C", "--model", "claude-test"]) == 2


def test_variants_candidate_sets():
    current = doc()
    pool, _ = build_pool(current)
    sets = {variant: predictor.candidate_set(current, variant=variant, pool=pool)
            for variant in ("B", "C", "E")}
    pairs = {v: {(p.node_a, p.node_b) for p in value.candidates} for v, value in sets.items()}
    assert pairs["B"] <= pairs["C"]
    assert {(p["a"], p["b"]) for p in pool} <= pairs["E"]


def test_report_fields_and_no_text():
    prediction = predictor.predict_doc(doc(), llm=Client(), model="claude-requested", variant="C")
    gold = [{"pair_id": prediction["predictions"][0]["pair_id"], "doc_id": "synthetic",
             "gold_label": "CONFLICT", "source": "gpt", "approved": False}]
    report = predictor.build_report([prediction], gold, split="dev", variant="C", prompt_rounds=1)
    assert {"by_label", "by_cluster", "false_duplicate", "direction_accuracy", "rejected",
            "injection_signals", "tokens_per_doc", "calls_per_doc", "latency_ms",
            "served_model", "prompt_version", "prompt_rounds", "ground_truth"} <= report.keys()
    assert report["ground_truth"] == "gpt-labels (approved=false), dev"
    assert report["by_label"]["CONFLICT"]["passed"] == 1
    serialized = json.dumps(report, ensure_ascii=False)
    assert TEXT_A not in serialized and TEXT_B not in serialized
    assert "span_a" not in serialized


def test_prompt_rounds_recorded():
    assert predictor.build_report([], [], split="dev", variant="C", prompt_rounds=2)["prompt_rounds"] == 2
    with pytest.raises(ValueError):
        predictor.build_report([], [], split="dev", variant="C", prompt_rounds=4)


def test_record_built_from_doc_verifies_citations(monkeypatch):
    from app.pipeline.contract_graph.pair_builder import build_pair_relations
    rec = predictor.record_from_doc(doc())
    result = build_pair_relations(rec, [], llm=Client(), model="claude-test", runtime=predictor.eval_runtime(5))
    assert result.relations
    resolver = CitationResolver(rec.pages, rec.tables, rec.evidence_nodes())
    for relation in result.relations:
        assert resolver.verify(relation.citation_a).valid
        assert resolver.verify(relation.citation_b).valid


def test_report_render_no_text():
    report = predictor.build_report([], [], split="dev", variant="C", prompt_rounds=0)
    assert "BLOCKED" in predictor.render_report({**report, "status": "BLOCKED", "blocked_reasons": ["Q3"]})


def test_split_converts_gpt_labels_and_includes_clusters(monkeypatch, tmp_path):
    current = doc()
    pool, _ = build_pool(current)
    labels = [{"pair_id": p["pair_id"], "label": "CONFLICT", "label_invalid": False,
               "general": None, "referrer": None, "span_a": "private span not for reports"} for p in pool]
    monkeypatch.setattr(predictor.manifest, "read_split", lambda *a, **k: [{"doc": current, "pool": pool, "labels": labels}])
    monkeypatch.setattr(predictor.manifest, "read_json", lambda *a, **k: {
        "labeler": {"served_model": "gpt-4o-mini"},
        "clusters": [{"cluster_id": "synthetic-cluster", "doc_ids": ["synthetic"]}]})
    report = predictor.predict_split(tmp_path, split="dev", variant="C", llm=Client(), model="claude-test")
    assert report["n_gold"] == report["by_label"]["CONFLICT"]["passed"] == 1
    assert "synthetic-cluster" in report["by_cluster"]
    assert "private span" not in json.dumps(report)


def test_cli_missing_frozen_data_stops_without_network(monkeypatch, tmp_path):
    monkeypatch.setattr(predictor.manifest, "verify", lambda *a: ["missing"])
    assert run.main(["predict", "--data-dir", str(tmp_path), "--model", "claude-test"]) == 2


def test_cluster_intervals_use_observed_cluster_denominators():
    blocks = {"cl-a": {"CONFLICT": {"precision_conservative": {"passed": 8, "denominator": 10},
                                     "recall_observed": {"passed": 8, "denominator": 12},
                                     "direction_accuracy": None}},
              "cl-b": {"CONFLICT": {"precision_conservative": {"passed": 0, "denominator": 2},
                                     "recall_observed": {"passed": 0, "denominator": 3},
                                     "direction_accuracy": None}}}
    intervals = predictor.cluster_intervals(blocks)
    interval = intervals["CONFLICT"]["precision_conservative"]
    assert interval["N"] == 12 and interval["K"] == 2
    assert interval["route"] == "cluster-floor"
    assert 0 <= interval["lower"] <= interval["upper"] <= 1
    assert intervals["CONFLICT"]["recall_observed"]["N"] == 15


def test_heldout_missing_locked_review_stops_before_call(monkeypatch, tmp_path):
    current = doc()
    pool, _ = build_pool(current)
    monkeypatch.setattr(predictor.manifest, "read_split", lambda *a, **k: [{"doc": current, "pool": pool, "labels": []}])
    monkeypatch.setattr(predictor.manifest, "read_json", lambda *a, **k: {"labeler": {"served_model": "gpt-4o-mini"}})
    client = Client()
    with pytest.raises(SystemExit) as error:
        predictor.predict_split(tmp_path, split="heldout", variant="C", llm=client,
                                 model="claude-test", allow_heldout=True)
    assert error.value.code == 2 and client.calls == 0
