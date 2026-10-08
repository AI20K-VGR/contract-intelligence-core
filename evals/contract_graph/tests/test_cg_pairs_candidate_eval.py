from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_cg_pairs_corpus import contract_text, source
from test_cg_pairs_manifest import _assert_no_text, _stage

from evals.contract_graph.pairs import candidate_eval as ce
from evals.contract_graph.pairs import corpus, manifest, pool, run


def _labels(records: list[dict], positives: dict[str, str]) -> list[dict]:
    return [
        {"pair_id": r["pair_id"], "label": positives.get(r["pair_id"], "UNRELATED"),
         "general": "A" if positives.get(r["pair_id"]) == "GENERAL_SPECIFIC" else None,
         "referrer": None, "span_a": None, "span_b": None, "grounded": True,
         "label_invalid": False, "invalid_reason": None, "requested_model": "gpt-4o-mini",
         "served_model": "gpt-4o-mini-2024-07-18", "prompt_version": "pairs-labeler-v1",
         "request_digest": "0" * 64}
        for r in records
    ]


def _dev_entry():
    doc = corpus.build_doc(source("https://dev.test/1"), contract_text())
    records, _ = pool.build_pool(doc)
    candidates = ce.doc_candidates(doc, top_k=10**6)
    covered = {frozenset((c.node_a, c.node_b)) for c in candidates.candidates}
    same_article = next(r for r in records if r["stratum"] == "S1"
                        and frozenset((r["a"], r["b"])) in covered)
    uncovered = next(r for r in records if frozenset((r["a"], r["b"])) not in covered)
    positives = {same_article["pair_id"]: "DUPLICATE", uncovered["pair_id"]: "CONFLICT"}
    return {"doc": doc, "pool": records, "labels": _labels(records, positives)}, positives


def test_recall_by_source_and_marginal():
    entry, positives = _dev_entry()
    report = ce.measure_dev([entry])
    assert report["recall_full"]["denominator"] == len(positives) == 2
    assert report["recall_full"]["passed"] == 1
    same = report["by_source"]["SAME_ARTICLE"]
    assert same["passed"] >= 1 and same["denominator"] == 2
    marginal = report["by_source_marginal"]
    assert set(marginal) == {s.value for s in ce.PairSource}
    assert all(m["passed"] <= report["by_source"][s]["passed"] for s, m in marginal.items())
    assert report["ground_truth"] == "gpt-labels (approved=false), dev"


def test_recall_at_k_curve_monotonic():
    entry, _ = _dev_entry()
    report = ce.measure_dev([entry])
    curve = [report["recall_at_k"][str(k)]["passed"] for k in ce.K_GRID]
    assert curve == sorted(curve)
    assert curve[-1] <= report["recall_full"]["passed"]


def test_recall_by_stratum_uses_p1_strata():
    entry, positives = _dev_entry()
    report = ce.measure_dev([entry])
    stratum_of = {r["pair_id"]: r["stratum"] for r in entry["pool"]}
    expected = {}
    for pair_id in positives:
        expected[stratum_of[pair_id]] = expected.get(stratum_of[pair_id], 0) + 1
    assert {s: v["denominator"] for s, v in report["by_stratum"].items()} == expected
    assert set(report["by_stratum"]) <= set(pool.STRATA)


def test_choose_top_k_smallest_reaching_95_percent():
    curve = {10: 5, 20: 9, 30: 10, 40: 10, 60: 10, 80: 10}
    assert ce.choose_top_k(curve, 10)[0] == 30  # 9 < 0.95 × 10
    assert ce.choose_top_k({**curve, 20: 10}, 10)[0] == 20
    assert ce.choose_top_k({k: 1 for k in ce.K_GRID}, 10)[0] == 40  # never reached ⇒ keep 40


def test_heldout_split_refused_for_candidates(tmp_path: Path):
    assert run.main(["candidates", "--split", "heldout", "--data-dir", str(tmp_path)]) == 2


# -- held-out S4, selection, export (frozen synthetic data) -----------------------------------


@pytest.fixture
def frozen(tmp_path: Path):
    _stage(tmp_path)
    repo_manifest = tmp_path / "manifest.json"
    manifest.freeze(tmp_path, repo_manifest, frozen_at="2026-10-09T00:00:00Z")
    report = tmp_path / "l2-p2-candidates.json"
    manifest.write_json(report, {"candidates_version": ce.CANDIDATES_VERSION,
                                 "pairs_top_k": ce.PAIRS_TOP_K})
    return tmp_path, repo_manifest, report


class _FakeLabeler:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, pair: dict, node_a: dict, node_b: dict) -> dict:
        self.calls += 1
        label = "CONFLICT" if self.calls % 3 == 0 else "UNRELATED"
        return _labels([pair], {pair["pair_id"]: label})[0]


def test_extend_heldout_is_b_union_c_minus_pool(frozen):
    data_dir, repo_manifest, report = frozen
    fake = _FakeLabeler()
    ce.extend_heldout(data_dir, repo_manifest, report, label_fn=fake)
    entries = manifest.read_split(data_dir, "heldout", repo_manifest)  # verify still passes
    assert entries
    total = 0
    for entry in entries:
        doc = entry["doc"]
        variant_c = ce.doc_candidates(doc, top_k=ce.PAIRS_TOP_K)
        variant_b = ce.doc_candidates(doc, top_k=ce.PAIRS_TOP_K, sources=ce.VARIANT_B)
        pooled = {frozenset((r["a"], r["b"])) for r in entry["pool"]}
        expected = {frozenset((c.node_a, c.node_b))
                    for c in (*variant_b.candidates, *variant_c.candidates)} - pooled
        s4 = manifest.read_jsonl(data_dir / "heldout" / doc["doc_id"] / "s4.jsonl")
        assert {frozenset((r["a"], r["b"])) for r in s4} == expected
        assert all(r["stratum"] == "S4" for r in s4)
        assert not {frozenset((r["a"], r["b"])) for r in s4} & pooled
        total += len(s4)
    assert fake.calls == total
    block = manifest.read_json(repo_manifest)["extension_s4"]
    assert block["n_pairs"] == total
    assert (block["candidates_version"], block["top_k"]) == (ce.CANDIDATES_VERSION, ce.PAIRS_TOP_K)


def test_extend_heldout_refuses_version_mismatch(frozen):
    data_dir, repo_manifest, report = frozen
    manifest.write_json(report, {"candidates_version": ce.CANDIDATES_VERSION,
                                 "pairs_top_k": ce.PAIRS_TOP_K + 1})
    fake = _FakeLabeler()
    with pytest.raises(SystemExit) as exc:
        ce.extend_heldout(data_dir, repo_manifest, report, label_fn=fake)
    assert exc.value.code == 2
    assert fake.calls == 0


def test_extend_heldout_runs_verify_first(frozen):
    data_dir, repo_manifest, report = frozen
    doc_dir = next((data_dir / "heldout").iterdir())
    (doc_dir / "pool.jsonl").write_text("{}\n", encoding="utf-8")
    fake = _FakeLabeler()
    with pytest.raises(SystemExit) as exc:
        ce.extend_heldout(data_dir, repo_manifest, report, label_fn=fake)
    assert exc.value.code == 2
    assert fake.calls == 0


def test_review_selection_locked_in_manifest_before_export(frozen):
    data_dir, repo_manifest, report = frozen
    with pytest.raises(SystemExit) as exc:  # no selection yet
        ce.review_export(data_dir, repo_manifest)
    assert exc.value.code == 2
    ce.extend_heldout(data_dir, repo_manifest, report, label_fn=_FakeLabeler())
    selected = ce.review_select(data_dir, repo_manifest)
    locked = manifest.read_json(repo_manifest)["review_selection"]
    assert locked["n_rows"] == selected["n_rows"] > 0
    assert "S4" in locked["by_stratum"]
    rows = ce.review_export(data_dir, repo_manifest)
    assert rows == locked["n_rows"]
    selection = data_dir / "review" / "selection.jsonl"
    selection.write_text(selection.read_text(encoding="utf-8") + "\n{}\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        ce.review_export(data_dir, repo_manifest)
    assert exc.value.code == 2


def test_top_k_constant_matches_report():
    committed = run.CANDIDATES_REPORT.with_suffix(".json")
    report = json.loads(committed.read_text(encoding="utf-8"))
    assert (report["candidates_version"], report["pairs_top_k"]) == (
        ce.CANDIDATES_VERSION, ce.PAIRS_TOP_K)
    assert report["pairs_top_k_chosen"] == ce.PAIRS_TOP_K
    _assert_no_text(report)


def test_reports_have_no_clause_text(frozen):
    entry, _ = _dev_entry()
    _assert_no_text(ce.measure_dev([entry]))
    data_dir, repo_manifest, report = frozen
    ce.extend_heldout(data_dir, repo_manifest, report, label_fn=_FakeLabeler())
    ce.review_select(data_dir, repo_manifest)
    _assert_no_text(json.loads(repo_manifest.read_text(encoding="utf-8")))
