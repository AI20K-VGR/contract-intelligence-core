from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from app.pipeline.citations import CitationResolver

from evals.contract_graph.pairs import manifest, predictor, run
from evals.contract_graph.pairs.pool import build_pool, pair_id_for

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


def test_gemini_served_passes_family_check():
    assert predictor.predict_doc(doc(), llm=Client("gemini-3.8-flash"), model="gemini/gemini-3.8-flash", variant="C")["predictions"]


def test_different_openai_served_model_passes_family_check():
    assert predictor.predict_doc(doc(), llm=Client("gpt-6-sol"), model="cx/gpt-6-sol", variant="C")["predictions"]


def test_reasoning_openai_model_family_uses_shared_gate():
    assert predictor.predict_doc(doc(), llm=Client("o5-mini"), model="o5-mini", variant="C")["predictions"]


def test_labeler_unknown_or_anthropic_refused_before_call():
    for labeler_model in ("unknown", "claude-labeler", None):
        client = Client()
        with pytest.raises(SystemExit) as error:
            predictor.predict_doc(doc(), llm=client, model="claude-requested", variant="C",
                                  labeler_served_model=labeler_model)
        assert error.value.code == 2 and client.calls == 0


def test_family_check_before_second_batch(monkeypatch):
    from app.pipeline.contract_graph.pair_candidates import (
        PairCandidate,
        PairCandidateSet,
    )
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
            "rejection_reason_versions", "served_model", "prompt_version", "prompt_rounds",
            "ground_truth", "evaluation_gate", "gold_provenance", "unreviewed_diagnostic"} <= report.keys()
    assert report["ground_truth"] == "unreviewed GPT suggestions (calibration only), dev"
    assert report["evaluation_gate"] == "BLOCKED_UNREVIEWED_DEV_GOLD"
    assert report["by_label"]["CONFLICT"]["passed"] == 0
    assert report["unreviewed_diagnostic"]["by_label"]["CONFLICT"]["passed"] == 1
    assert report["rejection_reason_versions"] == ["pair-rejections-v1"]
    assert report["report_sha256"] == predictor.report_digest(report)
    serialized = json.dumps(report, ensure_ascii=False)
    assert TEXT_A not in serialized and TEXT_B not in serialized
    assert "span_a" not in serialized


def test_dev_report_blocks_unreviewed_gold_from_being_called_recall():
    """Unreviewed GPT suggestions may diagnose calibration, never close a recall gate."""

    prediction = predictor.predict_doc(doc(), llm=Client(), model="claude-requested", variant="C")
    gold = [{"pair_id": prediction["predictions"][0]["pair_id"], "doc_id": "synthetic",
             "gold_label": "CONFLICT", "source": "gpt", "approved": False}]
    report = predictor.build_report([prediction], gold, split="dev", variant="C", prompt_rounds=0)

    assert report["ground_truth"] == "unreviewed GPT suggestions (calibration only), dev"
    assert report["evaluation_gate"] == "BLOCKED_UNREVIEWED_DEV_GOLD"
    assert report["gold_provenance"] == {"approved": 0, "unapproved": 1,
                                         "invalid_approval": 0, "scoring": "approved_only"}


def test_dev_report_scores_reviewed_gold():
    prediction = predictor.predict_doc(doc(), llm=Client(), model="claude-requested", variant="C")
    gold = [{"pair_id": prediction["predictions"][0]["pair_id"], "doc_id": "synthetic",
             "gold_label": "CONFLICT", "source": "user-review", "approved": True}]
    report = predictor.build_report([prediction], gold, split="dev", variant="C", prompt_rounds=0)

    assert report["evaluation_gate"] == "PASS"
    assert report["gold_provenance"] == {"approved": 1, "unapproved": 0,
                                         "invalid_approval": 0, "scoring": "approved_only"}
    assert report["n_gold"] == report["by_label"]["CONFLICT"]["passed"] == 1
    assert "unreviewed_diagnostic" not in report


def test_dev_classifier_gate_blocks_reviewed_zero_conflict_duplicate_recall():
    gold = [
        {"pair_id": "c", "doc_id": "synthetic", "gold_label": "CONFLICT",
         "source": "user-review", "approved": True},
        {"pair_id": "d", "doc_id": "synthetic", "gold_label": "DUPLICATE",
         "source": "user-review", "approved": True},
    ]
    report = predictor.build_report([], gold, split="dev", variant="C", prompt_rounds=0)
    assert report["evaluation_gate"] == "PASS"
    assert report["status"] == "BLOCKED"
    assert report["p3_classifier_gate"]["status"] == "BLOCKED"
    assert {"zero_conflict_recall", "zero_duplicate_recall"} <= set(
        report["p3_classifier_gate"]["reason_codes"]
    )


def test_reviewed_rejects_do_not_block_dev_gate():
    prediction = predictor.predict_doc(doc(), llm=Client(), model="claude-requested", variant="C")
    pair_id = prediction["predictions"][0]["pair_id"]
    gold = [
        {"pair_id": pair_id, "doc_id": "synthetic", "gold_label": "CONFLICT",
         "source": "user-review", "approved": True},
        {"pair_id": "rejected", "doc_id": "synthetic", "gold_label": None,
         "source": "user-review", "approved": False},
        {"pair_id": "duplicate", "doc_id": "synthetic", "gold_label": "DUPLICATE",
         "source": "user-review", "approved": True},
    ]
    predictions = prediction["predictions"] + [{"pair_id": "duplicate", "doc_id": "synthetic",
                                                  "label": "DUPLICATE", "direction": None}]
    report = predictor.build_report([{"doc_id": "synthetic", "cluster_id": "synthetic",
                                      "predictions": predictions, "stats": {"rejected": {},
                                      "served_model": "claude-test", "prompt_tokens": 1,
                                      "completion_tokens": 1, "llm_calls": 1,
                                      "rejection_reason_version": "pair-rejections-v1",
                                      "injection_signals": 0}, "latency_ms": 1,
                                      "mode": "llm", "rule_only_reason": None,
                                      "batches_completed": 1}], gold, split="dev", variant="C",
                                  prompt_rounds=0)
    assert report["evaluation_gate"] == "PASS"
    assert report["gold_provenance"]["approved"] == 2
    assert report["gold_provenance"]["unapproved"] == 0


def test_reviewed_reject_false_duplicate_blocks_p3_gate():
    prediction = predictor.predict_doc(doc(), llm=Client(), model="claude-requested", variant="C")
    pair_id = prediction["predictions"][0]["pair_id"]
    gold = [
        {"pair_id": pair_id, "doc_id": "synthetic", "gold_label": "CONFLICT",
         "source": "user-review", "approved": True},
        {"pair_id": "rejected", "doc_id": "synthetic", "gold_label": None,
         "source": "user-review", "approved": False},
        {"pair_id": "duplicate", "doc_id": "synthetic", "gold_label": "DUPLICATE",
         "source": "user-review", "approved": True},
    ]
    predictions = prediction["predictions"] + [
        {"pair_id": "duplicate", "doc_id": "synthetic", "label": "DUPLICATE", "direction": None},
        {"pair_id": "rejected", "doc_id": "synthetic", "label": "DUPLICATE", "direction": None},
    ]
    report = predictor.build_report([{"doc_id": "synthetic", "cluster_id": "synthetic",
                                      "predictions": predictions, "stats": {"rejected": {},
                                      "served_model": "claude-test", "prompt_tokens": 1,
                                      "completion_tokens": 1, "llm_calls": 1,
                                      "rejection_reason_version": "pair-rejections-v1",
                                      "injection_signals": 0}, "latency_ms": 1,
                                      "mode": "llm", "rule_only_reason": None,
                                      "batches_completed": 1}], gold, split="dev", variant="C",
                                  prompt_rounds=0)
    assert report["evaluation_gate"] == "PASS"
    assert report["false_duplicate"] == {"observed": 1, "unreviewed": 0}
    assert report["p3_classifier_gate"]["status"] == "BLOCKED"
    assert "false_duplicate_observed" in report["p3_classifier_gate"]["reason_codes"]


def test_prompt_rounds_recorded():
    assert predictor.build_report([], [], split="dev", variant="C", prompt_rounds=2)["prompt_rounds"] == 2
    assert predictor.build_report([], [], split="dev", variant="C", prompt_rounds=0)["evaluation_gate"] == "BLOCKED_MISSING_DEV_GOLD"
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
    assert report["n_gold"] == 0
    assert report["evaluation_gate"] == "BLOCKED_UNREVIEWED_DEV_GOLD"
    assert report["unreviewed_diagnostic"]["n_gold"] == 1
    assert "synthetic-cluster" in report["by_cluster"]
    assert "private span" not in json.dumps(report)


def test_explicit_dev_review_is_the_only_path_to_a_pass_gate(monkeypatch, tmp_path):
    current = doc()
    pool, _ = build_pool(current)
    pool.append({"pair_id": pair_id_for("synthetic", "a", "c"), "doc_id": "synthetic",
                 "a": "a", "b": "c", "stratum": "S1"})
    labels = [{"pair_id": p["pair_id"], "label": "CONFLICT", "label_invalid": False,
               "general": None, "referrer": None} for p in pool]
    review_path = tmp_path / "review/dev_classifier_review.jsonl"
    predictor.manifest.write_jsonl(review_path, [{
        "pair_id": pool[0]["pair_id"], "gold_label": "CONFLICT", "gold_direction": None,
        "approved": True, "source": "user-review",
    }, {
        "pair_id": pool[1]["pair_id"], "gold_label": "DUPLICATE", "gold_direction": None,
        "approved": True, "source": "user-review",
    }])
    lock = {"schema": predictor.DEV_REVIEW_SCHEMA, "sha256": predictor.file_digest(review_path),
            "n_rows": 2, "approved_by_label": {"CONFLICT": 1, "DUPLICATE": 1}}
    frozen = {"labeler": {"served_model": "gpt-4o-mini"},
              "clusters": [{"cluster_id": "synthetic-cluster", "doc_ids": ["synthetic"]}],
              "dev_review": lock}
    monkeypatch.setattr(predictor.manifest, "read_split", lambda *a, **k: [{"doc": current, "pool": pool, "labels": labels}])
    monkeypatch.setattr(predictor.manifest, "read_json", lambda *a, **k: frozen)
    monkeypatch.setattr(predictor, "predict_doc", lambda *a, **k: {
        "doc_id": "synthetic", "cluster_id": "synthetic-cluster",
        "predictions": [{"pair_id": pool[0]["pair_id"], "doc_id": "synthetic", "stratum": "S1",
                          "label": "CONFLICT", "direction": None},
                         {"pair_id": pool[1]["pair_id"], "doc_id": "synthetic", "stratum": "S1",
                          "label": "DUPLICATE", "direction": None}],
        "stats": {"served_model": "claude-test", "prompt_tokens": 1, "completion_tokens": 1,
                  "llm_calls": 1, "rejected": {}, "rejection_reason_version": "pair-rejections-v1",
                  "injection_signals": 0}, "mode": "llm", "rule_only_reason": None,
                  "batches_completed": 1, "latency_ms": 1, "prompt_version": predictor.PROMPT_VERSION})
    report = predictor.predict_split(tmp_path, split="dev", variant="C", llm=Client(),
                                     model="claude-test", dev_review=review_path)
    assert report["status"] == "OBSERVED"
    assert report["evaluation_gate"] == "PASS"
    assert report["p3_classifier_gate"]["status"] == "PASS"
    assert report["gold_provenance"]["approved"] == report["n_gold"] == 2
    assert report["dev_review"]["sha256"] == predictor.file_digest(review_path)


def test_reviewed_dev_loader_rejects_string_boolean(tmp_path):
    current = doc()
    pool, _ = build_pool(current)
    path = tmp_path / "review/dev.jsonl"
    predictor.manifest.write_jsonl(path, [{
        "pair_id": pool[0]["pair_id"], "gold_label": "CONFLICT", "gold_direction": None,
        "approved": "true", "source": "user-review",
    }])
    with pytest.raises(SystemExit) as error:
        predictor._read_reviewed_dev_gold(path, [{"doc": current, "pool": pool, "labels": []}], {})
    assert error.value.code == 2


def test_reviewed_dev_loader_rejects_non_object_row(tmp_path):
    current = doc()
    pool, _ = build_pool(current)
    path = tmp_path / "review/dev.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('["not-a-review-object"]\n', encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        predictor._read_reviewed_dev_gold(path, [{"doc": current, "pool": pool, "labels": []}], {})
    assert error.value.code == 2


def test_cli_missing_frozen_data_stops_without_network(monkeypatch, tmp_path):
    monkeypatch.setattr(predictor.manifest, "verify", lambda *a: ["missing"])
    assert run.main(["predict", "--data-dir", str(tmp_path), "--model", "claude-test"]) == 2


def test_cli_blocked_dev_report_returns_nonzero(monkeypatch, tmp_path):
    monkeypatch.setattr(predictor.manifest, "verify", lambda *a: [])
    monkeypatch.setattr(predictor, "predict_split", lambda *a, **k: {
        "status": "BLOCKED", "evaluation_gate": "BLOCKED_UNREVIEWED_DEV_GOLD",
    })
    monkeypatch.setattr(predictor, "render_report", lambda report: "BLOCKED")
    assert run.main(["predict", "--data-dir", str(tmp_path), "--model", "claude-test",
                     "--report-prefix", str(tmp_path / "report")]) == 2


def test_cli_heldout_preflight_stops_before_network(monkeypatch, tmp_path):
    from app.llm import client as llm_client

    from evals.contract_graph.pairs import bakeoff

    monkeypatch.setattr(predictor.manifest, "verify", lambda *a: [])
    calls = []

    def blocked(*args, **kwargs):
        calls.append((args, kwargs))
        raise SystemExit(2)

    monkeypatch.setattr(bakeoff, "preconditions", blocked)
    monkeypatch.setattr(llm_client, "NineRouterClient",
                        lambda: pytest.fail("held-out preflight must run before client construction"))
    assert run.main(["predict", "--data-dir", str(tmp_path), "--split", "heldout",
                     "--allow-heldout", "--model", "cx/gpt-5.5"]) == 2
    assert calls and calls[0][1]["served_model"] == "cx/gpt-5.5"


def test_review_dev_lock_can_record_review_before_report(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    review_path = data_dir / "review" / "dev_classifier_review.jsonl"
    review_path.parent.mkdir(parents=True)
    review_path.write_text("{}\n", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest.write_json(manifest_path, {})
    monkeypatch.setattr(run.manifest, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(run.manifest, "ensure_outside_repo", lambda *_: None)
    monkeypatch.setattr(run.manifest, "read_split", lambda *a, **k: [])
    monkeypatch.setattr(predictor, "_parse_dev_review",
                        lambda *a, **k: ([], "a" * 64, {"CONFLICT": 1, "DUPLICATE": 1}))
    args = SimpleNamespace(data_dir=data_dir, dev_review=review_path, manifest=manifest_path)

    assert run._review_dev_lock(args) == 0
    locked = manifest.read_json(manifest_path)
    assert locked["dev_review"]["sha256"] == "a" * 64
    assert "dev_report" not in locked


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


@pytest.mark.parametrize("malformed", [
    {"approved": True, "gold_label": "CONFLICT", "gold_direction": None, "source": "gpt"},
    {"approved": False, "gold_label": "DUPLICATE", "gold_direction": None, "source": "user-review"},
])
def test_heldout_review_loader_rejects_non_human_or_mislabeled_reject(tmp_path, malformed):
    current = doc()
    pool, _ = build_pool(current)
    selection = pool[0]
    data_dir = tmp_path / "data"
    review_dir = data_dir / "review"
    review_dir.mkdir(parents=True)
    selection_path = review_dir / "selection.jsonl"
    decisions_path = review_dir / "heldout_review.decisions.jsonl"
    manifest.write_jsonl(selection_path, [selection])
    manifest.write_jsonl(decisions_path, [{"pair_id": selection["pair_id"], **malformed}])
    frozen = {
        "review_selection": {"sha256": predictor.file_digest(selection_path), "n_rows": 1},
        "heldout_review": {"decisions_sha256": predictor.file_digest(decisions_path), "n_selected": 1},
    }
    with pytest.raises(SystemExit) as error:
        predictor._read_reviewed_gold(data_dir, frozen)
    assert error.value.code == 2


def _locked_hg1_files(tmp_path, *, selection_text, decisions_text):
    data_dir = tmp_path / "data"
    review_dir = data_dir / "review"
    review_dir.mkdir(parents=True)
    selection_path = review_dir / "selection.jsonl"
    decisions_path = review_dir / "heldout_review.decisions.jsonl"
    selection_path.write_text(selection_text, encoding="utf-8")
    decisions_path.write_text(decisions_text, encoding="utf-8")
    frozen = {
        "review_selection": {"sha256": predictor.file_digest(selection_path), "n_rows": 1},
        "heldout_review": {"decisions_sha256": predictor.file_digest(decisions_path), "n_selected": 1},
    }
    return data_dir, frozen


@pytest.mark.parametrize("decision_text", ["[]\n", "1\n", '{"approved": true}\n'])
def test_heldout_review_loader_rejects_malformed_decision_rows(tmp_path, decision_text):
    selection = '{"pair_id":"p1","doc_id":"d1","stratum":"S1","pi":1.0}\n'
    data_dir, frozen = _locked_hg1_files(tmp_path, selection_text=selection,
                                         decisions_text=decision_text)
    with pytest.raises(SystemExit) as error:
        predictor._read_reviewed_gold(data_dir, frozen)
    assert error.value.code == 2


@pytest.mark.parametrize("selection_text", ["[]\n", "1\n", '{"doc_id":"d1","stratum":"S1","pi":1.0}\n'])
def test_heldout_review_loader_rejects_malformed_selection_rows(tmp_path, selection_text):
    decisions = '{"pair_id":"p1","gold_label":"CONFLICT","gold_direction":null,"approved":true,"source":"user-review"}\n'
    data_dir, frozen = _locked_hg1_files(tmp_path, selection_text=selection_text,
                                         decisions_text=decisions)
    with pytest.raises(SystemExit) as error:
        predictor._read_reviewed_gold(data_dir, frozen)
    assert error.value.code == 2


def test_heldout_review_loader_rejects_duplicate_selection_ids(tmp_path):
    selection = ('{"pair_id":"p1","doc_id":"d1","stratum":"S1","pi":1.0}\n'
                 '{"pair_id":"p1","doc_id":"d1","stratum":"S1","pi":1.0}\n')
    decisions = '{"pair_id":"p1","gold_label":"CONFLICT","gold_direction":null,"approved":true,"source":"user-review"}\n'
    data_dir, frozen = _locked_hg1_files(tmp_path, selection_text=selection,
                                         decisions_text=decisions)
    with pytest.raises(SystemExit) as error:
        predictor._read_reviewed_gold(data_dir, frozen)
    assert error.value.code == 2


def test_heldout_review_loader_merges_locked_hg2_without_mutating_hg1(tmp_path):
    hg1_selection = {"pair_id": "p1", "doc_id": "d1", "stratum": "S1", "pi": 1.0}
    hg2_selection = {"pair_id": "p2", "doc_id": "d1", "stratum": "S2", "pi": 1.0}
    data_dir = tmp_path / "data"
    review_dir = data_dir / "review"
    review_dir.mkdir(parents=True)
    hg1_selection_path = review_dir / "selection.jsonl"
    hg1_decisions_path = review_dir / "heldout_review.decisions.jsonl"
    hg2_selection_path = review_dir / "hg2_selection.jsonl"
    hg2_decisions_path = review_dir / "hg2_review.decisions.jsonl"
    manifest.write_jsonl(hg1_selection_path, [hg1_selection])
    manifest.write_jsonl(hg1_decisions_path, [{"pair_id": "p1", "gold_label": "CONFLICT",
                                               "gold_direction": None, "approved": True,
                                               "source": "user-review"}])
    manifest.write_jsonl(hg2_selection_path, [hg2_selection])
    manifest.write_jsonl(hg2_decisions_path, [{"pair_id": "p2", "gold_label": "UNRELATED",
                                               "gold_direction": None, "approved": True,
                                               "source": "user-review", "decision": "approve"}])
    frozen = {"review_selection": {"sha256": predictor.file_digest(hg1_selection_path), "n_rows": 1},
              "heldout_review": {"decisions_sha256": predictor.file_digest(hg1_decisions_path),
                                  "n_selected": 1},
              "hg2": {"selection_path": "review/hg2_selection.jsonl",
                      "selection_sha256": predictor.file_digest(hg2_selection_path),
                      "selection_n_rows": 1, "decisions_path": "review/hg2_review.decisions.jsonl",
                      "decisions_sha256": predictor.file_digest(hg2_decisions_path),
                      "n_selected": 1}}
    gold = predictor._read_reviewed_gold(data_dir, frozen)
    assert [row["pair_id"] for row in gold] == ["p1", "p2"]
    assert gold[1]["doc_id"] == "d1" and gold[1]["stratum"] == "S2"
