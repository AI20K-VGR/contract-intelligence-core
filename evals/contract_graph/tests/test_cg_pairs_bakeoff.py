from __future__ import annotations

import copy
import csv
import hashlib
import json
import os
from types import SimpleNamespace

import pytest

from evals.contract_graph.dataset import _json_line
from evals.contract_graph.pairs import bakeoff, manifest, review, run
from evals.contract_graph.pairs.pool import pair_id_for

CODE_FILES = ("pair_candidates.py", "pair_classifier.py", "pair_builder.py", "predictor.py", "bakeoff.py", "score.py", "client.py")

@pytest.fixture
def frozen(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setattr(manifest, "REPO_ROOT", tmp_path)
    hg2_review = tmp_path / bakeoff.HG2_REVIEW_PATH
    hg2_sizing = tmp_path / bakeoff.HG2_SIZING_PATH
    hg2_review.parent.mkdir(parents=True, exist_ok=True)
    hg2_review.write_text("HG-2 review receipt\n", encoding="utf-8")
    hg2_sizing.write_text('{"method":"wilson_lower"}\n', encoding="utf-8")
    selected = [{"pair_id": pair_id_for("d", "a", "b"), "doc_id": "d", "a": "a", "b": "b",
                 "stratum": "S1", "gpt_label": "CONFLICT", "pi": 1.0}]
    manifest.write_jsonl(data / "review/selection.jsonl", selected)
    decisions = [{"pair_id": selected[0]["pair_id"], "gold_label": "CONFLICT", "gold_direction": None,
                  "approved": True, "source": "user-review"}]
    manifest.write_jsonl(data / "review/heldout_review.decisions.jsonl", decisions)
    lock = {"labeler": {"served_model": "gpt-4o-mini"}, "docs": [], "clusters": [],
            "extension_s4": {"candidates_version": bakeoff.CANDIDATES_VERSION,
                             "top_k": bakeoff.PAIRS_TOP_K, "files": {}},
            "dev_review": {"schema": bakeoff.predictor.DEV_REVIEW_SCHEMA, "sha256": "d" * 64,
                           "n_rows": 2, "approved_by_label": {"CONFLICT": 1, "DUPLICATE": 1}},
            "hg2": {"schema": bakeoff.HG2_SCHEMA, "status": "PASS", "human_approved": True,
                    "manifest_locked": True, "review_path": bakeoff.HG2_REVIEW_PATH.as_posix(),
                    "sizing_path": bakeoff.HG2_SIZING_PATH.as_posix(),
                    "review_sha256": bakeoff.file_digest(hg2_review),
                    "sizing_sha256": bakeoff.file_digest(hg2_sizing),
                    "recall_floor": {"method": "wilson_lower", "min": 0.85,
                                     "labels": list(bakeoff.SCORED)}},
            "review_selection": {"sha256": bakeoff.file_digest(data / "review/selection.jsonl"), "n_rows": 1},
            "heldout_review": {"decisions_sha256": bakeoff.file_digest(data / "review/heldout_review.decisions.jsonl"),
                               "n_selected": 1, "n_approve": 1, "n_relabel": 0, "n_reject": 0}}
    path = tmp_path / "manifest.json"
    manifest.write_json(path, lock)
    dev = {"schema": bakeoff.predictor.REPORT_SCHEMA, "scoring_schema": bakeoff.predictor.SCORING_SCHEMA,
           "code_sha256": bakeoff._code_fingerprints(),
           "status": "OBSERVED", "evaluation_gate": "PASS",
           "gold_provenance": {"approved": 2, "unapproved": 0, "invalid_approval": 0,
                                "scoring": "approved_only"},
           "false_duplicate": {"observed": 0, "unreviewed": 0},
           "p3_classifier_gate": {"schema": bakeoff.predictor.P3_GATE_SCHEMA, "status": "PASS",
                                  "required_labels": {"CONFLICT": {"gold_positive": 1, "correct": 1},
                                                       "DUPLICATE": {"gold_positive": 1, "correct": 1}},
                                  "false_duplicate_observed": 0, "reason_codes": []},
           "dev_review": {"schema": bakeoff.predictor.DEV_REVIEW_SCHEMA, "sha256": "d" * 64,
                          "n_rows": 2, "approved_by_label": {"CONFLICT": 1, "DUPLICATE": 1},
                          "source": "user-review", "manifest_locked": True},
           "prompt_version": bakeoff.PROMPT_VERSION, "prompt_rounds": 0, "n_candidates": 1,
           "by_label": {label: {"denominator": 1 if label in {"CONFLICT", "DUPLICATE"} else 0,
                                 "recall_observed": {"denominator": 1 if label in {"CONFLICT", "DUPLICATE"} else 0,
                                                      "passed": 1 if label in {"CONFLICT", "DUPLICATE"} else 0}}
                       for label in review.POSITIVE_LABELS},
           "calls_per_doc": {"dev": 1}, "tokens_per_doc": {"dev": {"prompt": 100, "completion": 10}},
           "latency_ms": {"p50": 10}}
    dev["report_sha256"] = bakeoff.predictor.report_digest(dev)
    dev_artifact = tmp_path / "evals/contract_graph/reports/l2-p3-classifier-dev.json"
    manifest.write_json(dev_artifact, dev)
    lock["dev_report"] = {"schema": bakeoff.DEV_REPORT_LOCK_SCHEMA,
                           "path": "evals/contract_graph/reports/l2-p3-classifier-dev.json",
                           "sha256": bakeoff.file_digest(dev_artifact)}
    manifest.write_json(path, lock)
    monkeypatch.setattr(manifest, "verify", lambda *_: [])
    monkeypatch.setattr(manifest, "ensure_outside_repo", lambda *_: None)
    monkeypatch.setattr(manifest, "read_split", lambda *_: [{"doc": {"doc_id": "d"}, "pool": selected,
                                                          "labels": [{"pair_id": selected[0]["pair_id"], "label": "CONFLICT"}]}])
    monkeypatch.setattr(bakeoff.predictor, "candidate_set", lambda *_, **__: SimpleNamespace(
        candidates=[SimpleNamespace(node_a="a", node_b="b")]))
    return data, path, dev, selected


def preflight(frozen, **kwargs):
    data, path, dev, _ = frozen
    kwargs.setdefault("require_commit_lock", False)
    return bakeoff.preconditions(data, repo_manifest=path, dev_report=dev, **kwargs)


def report(k=60, n=60):
    gold, preds, selection = [], [], []
    for label in review.POSITIVE_LABELS:
        for i in range(n):
            pid = f"{label}-{i}"
            gold.append({"pair_id": pid, "doc_id": f"d{i % 20}", "stratum": "S1", "approved": True,
                         "gold_label": label if i < k else "UNRELATED", "gold_direction": "A", "source": "user-review"})
            preds.append({"pair_id": pid, "doc_id": f"d{i % 20}", "stratum": "S1", "label": label,
                          "direction": "A" if label in {"GENERAL_SPECIFIC", "REFERENCE"} else None})
            selection.append({"pair_id": pid, "pi": 1.0, "gpt_label": label, "stratum": "S1", "doc_id": f"d{i % 20}"})
    trace_rows = [{"doc_id": f"d{i}", "served_model": "claude-test", "model": "claude-test",
                   "prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120,
                   "llm_calls": 1, "fallback_without_json_format": False, "classification_failed": False} for i in range(20)]
    per_doc = {f"d{i}": {"llm_calls": 1, "prompt_tokens": 100, "completion_tokens": 20,
                          "total_tokens": 120, "n_predictions": sum(p["doc_id"] == f"d{i}" for p in preds)}
                for i in range(20)}
    trials = [{"variant": variant, "trial": trial, "predictions": copy.deepcopy(preds),
               "decisions_sha256": "a" * 64, "requested_model": "claude-test", "served_model": ["claude-test"], "prompt_version": bakeoff.PROMPT_VERSION,
               "elapsed_s": 1, "prompt_tokens": 2000, "completion_tokens": 400,
               "n_docs": 20, "by_cluster": {}, "cluster_intervals": {}, "budget": {"tokens": 100000, "seconds": 10},
               "over_budget": False,
               "review_lock_commit": "c" * 40, "started_at": "2026-10-09T03:00:00+00:00",
               "finished_at": "2026-10-09T03:00:01+00:00", "llm_calls": 20,
               "traces": copy.deepcopy(trace_rows), "doc_provenance": copy.deepcopy(per_doc),
               "code_sha256": {name: "f" * 64 for name in CODE_FILES}}
              for variant in ("C", "B") for trial in (1, 2)]
    result = {"manifest": {"heldout_review": {"decisions_sha256": "a" * 64},
                           "docs": [{"doc_id": f"d{i}", "cluster_id": f"c{i}", "split": "heldout"} for i in range(20)]},
              "review_lock": {"commit": "c" * 40, "committed_at": "2026-10-09T02:00:00+00:00"},
              "review_lock_commit": "c" * 40, "review_lock_committed_at": "2026-10-09T02:00:00+00:00",
              "code_sha256": {name: "f" * 64 for name in CODE_FILES}, "decisions_sha256": "a" * 64,
            "prompt_version": bakeoff.PROMPT_VERSION, "variants_run": ["C", "B"], "trials": trials,
            "gold": gold, "selection": selection,
            "candidate_universe": [{"pair_id": row["pair_id"], "doc_id": row["doc_id"], "stratum": row["stratum"]}
                                    for row in selection],
            "feasibility": {}, "cluster_of_doc": {f"d{i}": f"c{i}" for i in range(20)}}
    lock_report(result)
    return result


def lock_report(r):
    ids = {g["pair_id"] for g in r["gold"]}
    r["selection"] = [s for s in r["selection"] if s["pair_id"] in ids]
    r["manifest"]["review_selection"] = {"sha256": hashlib.sha256("".join(_json_line(s) for s in r["selection"]).encode()).hexdigest(),
                                           "n_rows": len(r["selection"])}
    canonical = [{k: g[k] for k in ("pair_id", "gold_label", "gold_direction", "approved", "source", "decision") if k in g}
                 for g in sorted(r["gold"], key=lambda g: g["pair_id"])]
    digest = hashlib.sha256("".join(_json_line(d) for d in canonical).encode("utf-8")).hexdigest()
    r["manifest"]["heldout_review"]["decisions_sha256"] = r["decisions_sha256"] = digest
    for t in r["trials"]:
        t["decisions_sha256"] = digest


def test_precondition_verify_failure_exits_2(frozen, monkeypatch):
    monkeypatch.setattr(manifest, "verify", lambda *_: ["changed"])
    with pytest.raises(SystemExit) as error:
        preflight(frozen)
    assert error.value.code == 2


@pytest.mark.parametrize("mutation", [
    {"status": "BLOCKED"},
    {"evaluation_gate": "BLOCKED_UNREVIEWED_DEV_GOLD"},
    {"gold_provenance": {"approved": 0, "unapproved": 1, "invalid_approval": 0}},
])
def test_precondition_refuses_unobserved_or_unreviewed_dev(frozen, mutation):
    frozen[2].update(mutation)
    with pytest.raises(SystemExit) as error:
        preflight(frozen)
    assert error.value.code == 2


@pytest.mark.parametrize("field", ["schema", "scoring_schema", "code_sha256"])
def test_precondition_refuses_stale_dev_report(frozen, field):
    frozen[2][field] = "stale" if field != "code_sha256" else {}
    with pytest.raises(SystemExit) as error:
        preflight(frozen)
    assert error.value.code == 2


def test_precondition_refuses_p3_gate_or_review_lock_bypass(frozen):
    for mutation in (
        {"p3_classifier_gate": {"schema": bakeoff.predictor.P3_GATE_SCHEMA, "status": "BLOCKED"}},
        {"dev_review": {"schema": bakeoff.predictor.DEV_REVIEW_SCHEMA, "sha256": "e" * 64,
                         "n_rows": 2, "approved_by_label": {"CONFLICT": 1, "DUPLICATE": 1},
                         "source": "user-review", "manifest_locked": True}},
    ):
        frozen[2].update(mutation)
        with pytest.raises(SystemExit) as error:
            preflight(frozen)
        assert error.value.code == 2
        frozen[2].update({"p3_classifier_gate": {"schema": bakeoff.predictor.P3_GATE_SCHEMA, "status": "PASS",
                                                    "required_labels": {"CONFLICT": {"gold_positive": 1, "correct": 1},
                                                                         "DUPLICATE": {"gold_positive": 1, "correct": 1}},
                                                    "false_duplicate_observed": 0, "reason_codes": []},
                          "dev_review": {"schema": bakeoff.predictor.DEV_REVIEW_SCHEMA, "sha256": "d" * 64,
                                         "n_rows": 2, "approved_by_label": {"CONFLICT": 1, "DUPLICATE": 1},
                                         "source": "user-review", "manifest_locked": True}})


def test_precondition_refuses_missing_hg2_gate(frozen):
    lock = manifest.read_json(frozen[1])
    lock.pop("hg2")
    manifest.write_json(frozen[1], lock)
    with pytest.raises(SystemExit) as error:
        preflight(frozen)
    assert error.value.code == 2


def test_precondition_refuses_hg2_artifact_tamper(frozen):
    lock = manifest.read_json(frozen[1])
    review_path = manifest.REPO_ROOT / lock["hg2"]["review_path"]
    review_path.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        preflight(frozen)
    assert error.value.code == 2


@pytest.mark.parametrize("metric", ["false_duplicate", "recall"])
def test_precondition_refuses_float_p3_metric(frozen, metric):
    if metric == "false_duplicate":
        frozen[2]["false_duplicate"]["observed"] = 0.0
    else:
        frozen[2]["by_label"]["CONFLICT"]["recall_observed"]["passed"] = 1.0
    frozen[2]["report_sha256"] = bakeoff.predictor.report_digest(frozen[2])
    lock = manifest.read_json(frozen[1])
    dev_path = manifest.REPO_ROOT / lock["dev_report"]["path"]
    manifest.write_json(dev_path, frozen[2])
    lock["dev_report"]["sha256"] = bakeoff.file_digest(dev_path)
    manifest.write_json(frozen[1], lock)
    with pytest.raises(SystemExit) as error:
        preflight(frozen)
    assert error.value.code == 2


def test_precondition_default_checks_commit_lock(frozen, monkeypatch):
    called = []

    def fail_lock(*_):
        called.append(True)
        bakeoff._blocked("test commit lock")

    monkeypatch.setattr(bakeoff, "_review_lock", fail_lock)
    with pytest.raises(SystemExit) as error:
        preflight(frozen, require_commit_lock=True)
    assert error.value.code == 2 and called == [True]


def test_precondition_refuses_boolean_p3_metric(frozen):
    frozen[2]["p3_classifier_gate"]["required_labels"]["CONFLICT"]["correct"] = True
    frozen[2]["report_sha256"] = bakeoff.predictor.report_digest(frozen[2])
    with pytest.raises(SystemExit) as error:
        preflight(frozen)
    assert error.value.code == 2


def test_precondition_review_incomplete_exits_2(frozen):
    (frozen[0] / "review/heldout_review.decisions.jsonl").unlink()
    with pytest.raises(SystemExit) as error:
        preflight(frozen)
    assert error.value.code == 2


def test_precondition_selection_hash_mismatch_exits_2(frozen):
    (frozen[0] / "review/selection.jsonl").write_text("[]\n")
    with pytest.raises(SystemExit) as error:
        preflight(frozen)
    assert error.value.code == 2


def test_precondition_candidates_outside_gold_universe_exits_2(frozen, monkeypatch):
    monkeypatch.setattr(bakeoff.predictor, "candidate_set", lambda *_, **__: SimpleNamespace(
        candidates=[SimpleNamespace(node_a="a", node_b="new")]))
    with pytest.raises(SystemExit) as error:
        preflight(frozen)
    assert error.value.code == 2


@pytest.mark.parametrize("served", ["gh/gpt-4o-mini", "unknown", None])
def test_precondition_served_model_family(frozen, served):
    with pytest.raises(SystemExit) as error:
        preflight(frozen, served_model=served)
    assert error.value.code == 2


def test_precondition_accepts_google_classifier(frozen):
    result = preflight(frozen, served_model="gemini/gemini-3.8-flash")
    assert result["variants"] == ["C", "B"]


def test_precondition_accepts_different_openai_classifier(frozen):
    result = preflight(frozen, served_model="gpt-6-sol")
    assert result["variants"] == ["C", "B"]


def test_feasibility_drops_variant_e(frozen):
    assert preflight(frozen)["variants"] == ["C", "B"]
    frozen[2]["by_label"]["GENERAL_SPECIFIC"]["denominator"] = 40
    frozen[2]["report_sha256"] = bakeoff.predictor.report_digest(frozen[2])
    lock = manifest.read_json(frozen[1])
    dev_path = manifest.REPO_ROOT / lock["dev_report"]["path"]
    manifest.write_json(dev_path, frozen[2])
    lock["dev_report"]["sha256"] = bakeoff.file_digest(dev_path)
    manifest.write_json(frozen[1], lock)
    assert preflight(frozen)["variants"] == ["C", "B", "E"]


def test_gate_uses_conservative_precision():
    r = report(40, 70)
    r["gold"] = [g for g in r["gold"] if not g["pair_id"].startswith("CONFLICT-") or int(g["pair_id"].split("-")[-1]) < 54]
    lock_report(r)
    block = bakeoff.decide(r)["per_label"]["CONFLICT"]
    assert (block["k"], block["n"]) == (40, 70)


def test_weighted_estimate_reported_not_gating():
    r = report(57, 70)
    for g in r["gold"]:
        if g["pair_id"].startswith("DUPLICATE-"):
            g["gold_label"] = "DUPLICATE"
    r["gold"] = [g for g in r["gold"] if g["gold_label"] != "UNRELATED"]
    lock_report(r)
    decision = bakeoff.decide(r)
    assert decision["per_label"]["CONFLICT"]["precision_weighted"] == 1.0
    assert decision["verdict"] == "HUMAN_DECISION"


def test_metric_prints_single_number(tmp_path, capsys):
    manifest.write_json(tmp_path / "t1/C.json", {"recall_any": {"rate": .25}})
    manifest.write_json(tmp_path / "t2/C.json", {"recall_any": {"rate": .5}})
    assert run.main(["bakeoff", "metric", "C", "--out", str(tmp_path)]) == 0
    assert capsys.readouterr().out == "0.5\n"


def test_metric_dry_run_has_no_trial_or_model_call(tmp_path, capsys):
    assert run.main(["bakeoff", "metric", "C", "--out", str(tmp_path), "--dry-run"]) == 0
    assert capsys.readouterr().out == "0.0\n" and not list(tmp_path.iterdir())


def test_mcnemar_counts_b_and_c_on_same_items():
    gold = [{"pair_id": str(i), "gold_label": "CONFLICT", "approved": True} for i in range(4)]
    a = [{"pair_id": str(i), "label": "CONFLICT"} for i in (0, 1)]
    b = [{"pair_id": str(i), "label": "CONFLICT"} for i in (1, 2, 3)]
    counts = bakeoff.compare_items(gold, a, b)
    assert (counts["b"], counts["c"], counts["n_items"]) == (1, 2, 4)


def test_decide_insufficient_n():
    assert bakeoff.decide(report(59, 59))["verdict"] == "KEEP_OFF_INSUFFICIENT_N"


def test_decide_below_threshold():
    r = report(56, 60)
    # False DUPLICATE is tested independently; keep this label perfect.
    for g in r["gold"]:
        if g["pair_id"].startswith("DUPLICATE-"):
            g["gold_label"] = "DUPLICATE"
    lock_report(r)
    assert bakeoff.decide(r)["verdict"] == "KEEP_OFF_BELOW_THRESHOLD"
    near = report(57, 60)
    assert bakeoff.decide(near)["per_label"]["CONFLICT"]["passed"]
    assert bakeoff.decide(report(60, 60))["verdict"] == "ENABLE_CANDIDATE"


def test_decide_false_duplicate_veto():
    assert bakeoff.decide(report(59, 60))["verdict"] == "KEEP_OFF_FALSE_DUPLICATE"


def test_decide_uses_worse_trial():
    r = report()
    r["trials"][1]["predictions"] = []
    for stats in r["trials"][1]["doc_provenance"].values():
        stats["n_predictions"] = 0
    assert bakeoff.decide(r)["verdict"] == "KEEP_OFF_INSUFFICIENT_N"


def test_decide_refuses_decisions_sha_mismatch():
    r = report()
    r["trials"][-1]["decisions_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="SHA"):
        bakeoff.decide(r)


def test_decide_thresholds_imported_from_review_policy():
    from app.pipeline.contract_graph import review_policy
    assert bakeoff.decide(report())["thresholds"] == {
        "min_n": review_policy.MIN_N, "min_wilson_lower": review_policy.MIN_WILSON_LOWER}


def test_reports_have_no_clause_text():
    r = report()
    r["text"] = "PRIVATE_CLAUSE"
    r["trials"][0]["by_label"] = {"text": "PRIVATE_CLAUSE"}
    assert "PRIVATE_CLAUSE" not in bakeoff.render_report(r)


def test_review_import_cli_exact_selection_and_lock(frozen, tmp_path):
    data, path, _, selected = frozen
    initial = manifest.read_json(path)
    initial["heldout_review"] = None
    manifest.write_json(path, initial)
    csv_path = tmp_path / "review.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=review.SHEET_COLUMNS)
        writer.writeheader()
        writer.writerow({"pair_id": selected[0]["pair_id"], "doc_id": "d", "gpt_label": "CONFLICT", "decision": "approve"})
    assert run.main(["review-import", "--csv", str(csv_path), "--data-dir", str(data), "--manifest", str(path)]) == 0
    assert manifest.read_json(path)["heldout_review"]["n_approve"] == 1


def test_hg2_lock_requires_explicit_human_gate(tmp_path):
    with pytest.raises(SystemExit) as error:
        bakeoff.lock_hg2(tmp_path / "data", repo_manifest=tmp_path / "manifest.json")
    assert error.value.code == 2


def test_hg2_import_validates_and_does_not_promote_draft(frozen, tmp_path, monkeypatch):
    data, path, _, selected = frozen
    second = {"pair_id": pair_id_for("d", "a", "c"), "doc_id": "d", "a": "a", "b": "c",
              "stratum": "S1", "gpt_label": "UNRELATED", "pi": 1.0}
    hg2_path = data / bakeoff.HG2_SELECTION_REL
    manifest.write_jsonl(hg2_path, [second])
    sizing = manifest.REPO_ROOT / bakeoff.HG2_SIZING_PATH
    manifest.write_json(sizing, {"proposal": {"selection_sha256": bakeoff.file_digest(hg2_path),
                                                "n_rows": 1}})
    monkeypatch.setattr(manifest, "read_split", lambda *_: [{"doc": {"doc_id": "d"},
                                                              "pool": [selected[0], second],
                                                              "labels": [{"pair_id": selected[0]["pair_id"], "label": "CONFLICT"},
                                                                          {"pair_id": second["pair_id"], "label": "UNRELATED"}]}])
    csv_path = tmp_path / "hg2.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=review.SHEET_COLUMNS)
        writer.writeheader()
        writer.writerow({"pair_id": second["pair_id"], "doc_id": "d", "gpt_label": "UNRELATED",
                         "gpt_direction": "", "decision": "approve"})
    before = manifest.read_json(path)
    lock = bakeoff.import_hg2_review(data, csv_path, repo_manifest=path)
    assert lock["n_selected"] == 1
    assert manifest.read_jsonl(data / bakeoff.HG2_DECISIONS_REL)[0]["source"] == "user-review"
    assert manifest.read_json(path) == before


def test_hg2_lock_records_explicit_gate_and_receipt(frozen, tmp_path, monkeypatch):
    data, path, _, selected = frozen
    second = {"pair_id": pair_id_for("d", "a", "c"), "doc_id": "d", "a": "a", "b": "c",
              "stratum": "S1", "gpt_label": "UNRELATED", "pi": 1.0}
    hg2_path = data / bakeoff.HG2_SELECTION_REL
    manifest.write_jsonl(hg2_path, [second])
    sizing = manifest.REPO_ROOT / bakeoff.HG2_SIZING_PATH
    manifest.write_json(sizing, {"proposal": {"selection_sha256": bakeoff.file_digest(hg2_path),
                                                "n_rows": 1}})
    monkeypatch.setattr(manifest, "read_split", lambda *_: [{"doc": {"doc_id": "d"},
                                                              "pool": [selected[0], second],
                                                              "labels": [{"pair_id": selected[0]["pair_id"], "label": "CONFLICT"},
                                                                          {"pair_id": second["pair_id"], "label": "UNRELATED"}]}])
    csv_path = tmp_path / "hg2.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=review.SHEET_COLUMNS)
        writer.writeheader()
        writer.writerow({"pair_id": second["pair_id"], "doc_id": "d", "gpt_label": "UNRELATED",
                         "gpt_direction": "", "decision": "approve"})
    bakeoff.import_hg2_review(data, csv_path, repo_manifest=path)
    unlocked = manifest.read_json(path)
    unlocked.pop("hg2")
    manifest.write_json(path, unlocked)
    lock = bakeoff.lock_hg2(data, repo_manifest=path, recall_floor=.85,
                            human_approved=True, scope_consent=True)
    assert lock["status"] == "PASS" and lock["manifest_locked"] is True
    assert "Human decision recorded" in (manifest.REPO_ROOT / bakeoff.HG2_REVIEW_PATH).read_text("utf-8")
    assert manifest.read_json(sizing)["status"] == "PASS"


def test_trial_matrix_and_model_consistency():
    for mutate in (lambda r: r["trials"].pop(),
                   lambda r: r["trials"][-1].update(served_model=["claude-other"]),
                   lambda r: r["trials"][-1].update(prompt_version="changed"),
                   lambda r: r["trials"][-1].update(code_sha256={"pair_classifier.py": "changed"})):
        r = report()
        mutate(r)
        with pytest.raises(ValueError):
            bakeoff.decide(r)


def test_decide_refuses_trial_requested_model_mutation():
    r = report()
    r["trials"][0]["requested_model"] = "claude-other"
    with pytest.raises(ValueError, match="requested model"):
        bakeoff.decide(r)


def test_decide_over_budget_requires_human_decision():
    r = report()
    r["trials"][2]["over_budget"] = True
    r["trials"][2]["budget"] = {"tokens": 100, "seconds": 10}
    result = bakeoff.decide(r)
    assert result["verdict"] == "HUMAN_DECISION"
    assert result["budget_blocked_variants"] == ["B"]


def test_decide_insufficient_n_precedes_non_gating_budget_advisory():
    r = report(59, 59)
    r["trials"][2]["over_budget"] = True
    r["trials"][2]["budget"] = {"tokens": 100, "seconds": 10}
    result = bakeoff.decide(r)
    assert result["verdict"] == "KEEP_OFF_INSUFFICIENT_N"
    assert result["budget_blocked_variants"] == ["B"]


def test_min_n_observed_rate_is_not_all_pass():
    assert bakeoff.minimum_sample(.85) is None
    assert bakeoff.minimum_sample(.95) >= 60


def test_report_gold_mutation_is_rejected():
    r = report()
    r["gold"][0]["gold_label"] = "UNRELATED"
    with pytest.raises(ValueError, match="gold SHA"):
        bakeoff.decide(r)


@pytest.mark.parametrize("mutation", ["pi", "gold_doc", "cluster", "no_code", "trace_model", "commit", "started_before_lock", "pred_doc", "cost"])
def test_decide_refuses_unbound_trial_provenance(mutation):
    r = report()
    if mutation == "pi":
        r["selection"][0]["pi"] = .001
    elif mutation == "gold_doc":
        r["gold"][0]["doc_id"] = "different"
    elif mutation == "cluster":
        r["cluster_of_doc"]["d0"] = "different"
    elif mutation == "no_code":
        for t in r["trials"]:
            t.pop("code_sha256")
    elif mutation == "trace_model":
        r["trials"][0]["traces"][0]["served_model"] = "gpt-4o-mini"
    elif mutation == "commit":
        r["trials"][0]["review_lock_commit"] = "invalid"
    elif mutation == "pred_doc":
        r["trials"][0]["predictions"][0]["doc_id"] = "d1"
    elif mutation == "cost":
        r["trials"][0]["prompt_tokens"] = 999
    else:
        r["trials"][0]["started_at"] = "2000-01-01T00:00:00+00:00"
    with pytest.raises(ValueError):
        bakeoff.decide(r)


def test_decide_refuses_lock_summary_mutation():
    r = report()
    r["review_lock"]["commit"] = "d" * 40
    for trial in r["trials"]:
        trial["review_lock_commit"] = "d" * 40
    with pytest.raises(ValueError, match="review lock summary"):
        bakeoff.decide(r)


def test_decide_refuses_prediction_outside_candidate_universe():
    r = report()
    r["trials"][0]["predictions"][0]["pair_id"] = "outside-universe"
    with pytest.raises(ValueError, match="candidate universe"):
        bakeoff.decide(r)


def test_decide_refuses_trace_doc_coverage_mutation():
    r = report()
    for trace in r["trials"][0]["traces"]:
        trace["doc_id"] = "d0"
    with pytest.raises(ValueError, match="document trace coverage"):
        bakeoff.decide(r)


@pytest.mark.parametrize("missing", ["prompt_tokens", "completion_tokens", "total_tokens"])
def test_runner_missing_usage_field_writes_no_artifact(frozen, tmp_path, monkeypatch, missing):
    data, path, dev, selected = frozen
    client = SimpleNamespace(traces=[])
    monkeypatch.setattr(bakeoff, "_review_lock", lambda *_: {"commit": "c" * 40,
                                                                 "committed_at": "2026-10-09T02:00:00+00:00"})
    def predicted(doc, **kwargs):
        trace = {"served_model": "claude-test", "model": "claude-test", "prompt_tokens": 10,
                 "completion_tokens": 2, "total_tokens": 12, "fallback_without_json_format": False}
        trace.pop(missing)
        client.traces.append(trace)
        return {"doc_id": "d", "cluster_id": "d", "predictions": [{"pair_id": selected[0]["pair_id"], "doc_id": "d",
                   "label": "CONFLICT", "direction": None, "stratum": "S1"}],
                "stats": {"served_model": "claude-test", "prompt_tokens": 10, "completion_tokens": 2, "llm_calls": 1},
                "mode": "llm", "rule_only_reason": None, "batches_completed": 1, "latency_ms": 4,
                "prompt_version": bakeoff.PROMPT_VERSION}
    monkeypatch.setattr(bakeoff.predictor, "predict_doc", predicted)
    out = tmp_path / "out"
    with pytest.raises(SystemExit) as error:
        bakeoff.run("C", 1, out_dir=out, model="claude-test", data_dir=data, repo_manifest=path,
                    llm=client, allow_heldout=True, dev_report=dev)
    assert error.value.code == 2 and not (out / "t1/C.json").exists()


def test_decide_refuses_error_trace_even_with_successful_trace():
    r = report()
    error_trace = dict(r["trials"][0]["traces"][0])
    error_trace["error_type"] = "TimeoutError"
    error_trace["doc_id"] = "d1"
    r["trials"][0]["traces"].append(error_trace)
    r["trials"][0]["llm_calls"] = 2
    r["trials"][0]["prompt_tokens"] = 200
    r["trials"][0]["completion_tokens"] = 40
    with pytest.raises(ValueError, match="provider error"):
        bakeoff.decide(r)


def test_decide_accepts_parse_error_as_failed_classification():
    r = report()
    r["trials"][0]["traces"][0]["error_type"] = "ResponseParseError"
    r["trials"][0]["traces"][0]["classification_failed"] = True
    r["trials"][0]["predictions"] = [p for p in r["trials"][0]["predictions"] if p["doc_id"] != "d0"]
    r["trials"][0]["doc_provenance"]["d0"]["n_predictions"] = 0
    result = bakeoff.decide(r)
    assert result["recommendation_only"] is True


def test_decide_rejects_parse_error_with_unknown_model():
    r = report()
    r["trials"][0]["traces"][0]["error_type"] = "ResponseParseError"
    r["trials"][0]["traces"][0]["classification_failed"] = True
    r["trials"][0]["traces"][0]["served_model"] = "unknown-model"
    with pytest.raises(ValueError, match="served model"):
        bakeoff.decide(r)


def test_decide_requires_exact_trace_call_count():
    r = report()
    r["trials"][0]["llm_calls"] = 999
    with pytest.raises(ValueError, match="call count"):
        bakeoff.decide(r)


def test_decide_rejects_invalid_direction_for_undirected_label():
    r = report()
    next(pred for pred in r["trials"][0]["predictions"] if pred["label"] == "CONFLICT")["direction"] = "A"
    with pytest.raises(ValueError, match="direction"):
        bakeoff.decide(r)


def test_decide_recomputes_over_budget_from_measured_values():
    r = report()
    r["trials"][0]["budget"] = {"tokens": 100, "seconds": 0.5}
    r["trials"][0]["over_budget"] = False
    with pytest.raises(ValueError, match="over_budget"):
        bakeoff.decide(r)


def test_runner_claim_blocks_provider_before_concurrent_call(frozen, tmp_path, monkeypatch):
    data, path, dev, _ = frozen
    out = tmp_path / "out"
    target = out / "t1/C.json"
    claim = target.with_suffix(target.suffix + ".claim")
    claim.parent.mkdir(parents=True)
    claim.write_text(json.dumps({"pid": os.getpid(), "token": "owner"}), encoding="utf-8")
    calls = []
    monkeypatch.setattr(bakeoff, "_review_lock", lambda *_: {"commit": "c" * 40,
                                                                 "committed_at": "2026-10-09T02:00:00+00:00"})
    monkeypatch.setattr(bakeoff, "preconditions", lambda *_, **__: {
        "variants": ["C", "B"], "decisions_sha256": "a" * 64,
        "feasibility": {}, "code_sha256": {},
    })
    monkeypatch.setattr(bakeoff.predictor, "predict_doc", lambda *args, **kwargs: calls.append(1))
    with pytest.raises(SystemExit) as error:
        bakeoff.run("C", 1, out_dir=out, model="claude-test", data_dir=data, repo_manifest=path,
                    allow_heldout=True, dev_report=dev)
    assert error.value.code == 2 and calls == []


def test_trial_claim_recovers_dead_owner_and_cleans_up(tmp_path):
    target = tmp_path / "out/t1/C.json"
    claim = target.with_suffix(target.suffix + ".claim")
    claim.parent.mkdir(parents=True)
    claim.write_text(json.dumps({"pid": 2_147_483_647, "token": "dead"}), encoding="utf-8")
    acquired, token = bakeoff._acquire_claim(target)
    assert acquired == claim and claim.is_file()
    bakeoff._release_claim(acquired, token)
    assert not claim.exists()


def test_offline_assembly_binds_actual_gold_and_trial_provenance(frozen, tmp_path, monkeypatch):
    data, path, _dev, selected = frozen
    original = manifest.read_json(path)
    original["docs"] = [{"doc_id": "d", "cluster_id": "c", "split": "heldout"}]
    original["clusters"] = [{"doc_ids": ["d"], "cluster_id": "c"}]
    manifest.write_json(path, original)
    checked = preflight(frozen)
    monkeypatch.setattr(bakeoff, "preconditions", lambda *_, **__: checked)
    monkeypatch.setattr(bakeoff, "_review_lock", lambda *_: {"commit": "c" * 40, "committed_at": "2026-10-09T02:00:00+00:00"})
    out = tmp_path / "assembly"
    for variant in ("C", "B"):
        for trial in (1, 2):
            manifest.write_json(out / f"t{trial}/{variant}.json", {
                "variant": variant, "trial": trial, "n_docs": 1, "predictions": [{"pair_id": selected[0]["pair_id"],
                    "doc_id": "d", "stratum": "S1", "label": "CONFLICT", "direction": None}],
                "decisions_sha256": checked["decisions_sha256"], "requested_model": "claude-test", "served_model": ["claude-test"],
                "prompt_version": bakeoff.PROMPT_VERSION, "code_sha256": checked["code_sha256"],
                "review_lock_commit": "c" * 40, "started_at": "2026-10-09T03:00:00+00:00", "finished_at": "2026-10-09T03:00:01+00:00",
                    "llm_calls": 1, "prompt_tokens": 10, "completion_tokens": 2, "elapsed_s": 1, "budget": {"tokens": 100, "seconds": 10}, "over_budget": False,
                    "doc_provenance": {"d": {"llm_calls": 1, "prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12, "n_predictions": 1}},
                "traces": [{"doc_id": "d", "served_model": "claude-test", "model": "claude-test", "prompt_tokens": 10, "completion_tokens": 2,
                            "total_tokens": 12, "llm_calls": 1, "fallback_without_json_format": False, "classification_failed": False}],
                "recall_any": {"rate": .123}, "by_label": {"text": "PRIVATE_TRIAL"}})
    assembled = bakeoff.assemble_report(out, data, repo_manifest=path)
    assert assembled["cluster_of_doc"] == {"d": "c"}
    assert assembled["scoreboard"]["C"]["recall_any_trials"][0]["rate"] == 1.0
    assert bakeoff.decide(assembled)["verdict"] == "KEEP_OFF_INSUFFICIENT_N"
    assert "PRIVATE_TRIAL" not in bakeoff.render_report(assembled)
    mutated = manifest.read_json(out / "t1/C.json")
    mutated["predictions"][0]["stratum"] = "S3"
    manifest.write_json(out / "t1/C.json", mutated)
    with pytest.raises(ValueError, match="universe"):
        bakeoff.assemble_report(out, data, repo_manifest=path)


def test_runner_saves_safe_trace_and_never_overwrites(frozen, tmp_path, monkeypatch):
    data, path, dev, selected = frozen
    client = SimpleNamespace(traces=[])
    monkeypatch.setattr(bakeoff, "_review_lock", lambda *_: {"commit": "c" * 40, "committed_at": "2026-10-09T02:00:00+00:00"})
    def predicted(doc, **kwargs):
        client.traces.append({"served_model": "claude-test", "model": "claude-test", "prompt_tokens": 10, "completion_tokens": 2,
                              "total_tokens": 12, "fallback_without_json_format": False,
                              "latency_ms": 4, "system": "PRIVATE_PROMPT", "span_a": "PRIVATE_SPAN", "api_key": "PRIVATE_KEY"})
        return {"doc_id": "d", "cluster_id": "d", "predictions": [{"pair_id": selected[0]["pair_id"], "doc_id": "d",
                   "label": "CONFLICT", "direction": None, "stratum": "S1"}],
                "stats": {"served_model": "claude-test", "prompt_tokens": 10, "completion_tokens": 2, "llm_calls": 1},
                "mode": "llm", "rule_only_reason": None, "batches_completed": 1, "latency_ms": 4,
                "prompt_version": bakeoff.PROMPT_VERSION}
    monkeypatch.setattr(bakeoff.predictor, "predict_doc", predicted)
    out = tmp_path / "out"
    result = bakeoff.run("C", 1, out_dir=out, model="claude-test", data_dir=data, repo_manifest=path,
                         llm=client, allow_heldout=True, dev_report=dev)
    assert result["recall_any"]["passed"] == result["recall_any"]["denominator"] == 1
    assert result["prompt_tokens"] == 10 and result["review_lock_commit"] == "c" * 40
    serialized = (out / "t1/C.json").read_text(encoding="utf-8")
    assert not any(secret in serialized for secret in ("PRIVATE_PROMPT", "PRIVATE_SPAN", "PRIVATE_KEY"))
    with pytest.raises(SystemExit) as error:
        bakeoff.run("C", 1, out_dir=out, model="claude-test", data_dir=data, repo_manifest=path,
                    llm=client, allow_heldout=True, dev_report=dev)
    assert error.value.code == 2 and len(client.traces) == 1


def test_production_cloned_clients_use_global_trace_buffer():
    from app.llm.client import NineRouterClient
    client = object.__new__(NineRouterClient)
    client.traces = []
    assert bakeoff._trace_buffer(client) is NineRouterClient.all_traces


def test_runner_requires_explicit_heldout_before_calls(frozen, tmp_path):
    with pytest.raises(SystemExit) as error:
        bakeoff.run("C", 1, out_dir=tmp_path, model="claude-test", data_dir=frozen[0], repo_manifest=frozen[1])
    assert error.value.code == 2


def test_runner_refuses_blocked_dev_before_heldout_calls(frozen, tmp_path, monkeypatch):
    data, path, dev, _ = frozen
    dev["status"] = "BLOCKED"
    calls = []
    monkeypatch.setattr(bakeoff.predictor, "predict_doc", lambda *args, **kwargs: calls.append(1))
    with pytest.raises(SystemExit) as error:
        bakeoff.run("C", 1, out_dir=tmp_path, model="claude-test", data_dir=data,
                    repo_manifest=path, allow_heldout=True, dev_report=dev)
    assert error.value.code == 2 and calls == []


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "direction", "sha"])
def test_importer_refuses_changed_review(frozen, tmp_path, mutation):
    data, path, _, selected = frozen
    initial = manifest.read_json(path)
    initial["heldout_review"] = None
    manifest.write_json(path, initial)
    row = {"pair_id": selected[0]["pair_id"], "doc_id": "d", "gpt_label": "CONFLICT", "decision": "approve"}
    rows = [row]
    if mutation == "duplicate":
        rows *= 2
    elif mutation == "missing":
        rows = []
    elif mutation == "direction":
        row["gpt_direction"] = "A"
    else:
        (data / "review/selection.jsonl").write_text("[]\n")
    csv_path = tmp_path / "invalid.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=review.SHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    assert run.main(["review-import", "--csv", str(csv_path), "--data-dir", str(data), "--manifest", str(path)]) == 2
    assert manifest.read_json(path)["heldout_review"] is None


def test_committed_decision_matches_report():
    prefix = manifest.REPO_ROOT / "evals/contract_graph/reports/l2-p5"
    report_path = prefix.with_name("l2-p5-bakeoff.json")
    decision_path = prefix.with_name("l2-p5-decision.json")
    if not report_path.is_file() or not decision_path.is_file():
        pytest.skip("P5 live artifacts pending; phase is not complete")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("prompt_version") != bakeoff.PROMPT_VERSION:
        pytest.skip("committed P5 artifact predates the current classifier prompt; P5 must be rerun after P3/P4")
    if report.get("schema") != "contract-graph-pairs-bakeoff/1":
        pytest.skip("committed P5 artifact has an obsolete report schema; P5 must be rerun")
    if report.get("code_sha256") != bakeoff._code_fingerprints():
        pytest.skip("committed P5 artifact predates the current code fingerprint; P5 must be rerun after P3/P4")
    expected = json.loads(decision_path.read_text(encoding="utf-8"))
    expected["budget_blocked_variants"] = sorted({t["variant"] for t in report["trials"] if t["over_budget"]})
    assert bakeoff.decide(report) == expected
