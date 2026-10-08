from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import COMMITTED_DATA, MINI_SOURCES, REPO_ROOT, seed_cache
from evals.contract_graph import pipeline_predictor, run_eval
from evals.contract_graph.score import wilson

from app.pipeline.contract_graph.review_policy import wilson_lower

REPORTS = REPO_ROOT / "evals" / "contract_graph" / "reports"
PREDICTOR = "evals.contract_graph.pipeline_predictor:predict"


@pytest.fixture
def suffix_dataset(tmp_path: Path) -> Path:
    from evals.contract_graph.dataset import build_pair, freeze

    cache = tmp_path / "cache"
    source = MINI_SOURCES[1]
    for key in ("amending_url", "vbhn_url"):
        seed_cache(cache, source[key], source[key].rsplit("/", 1)[1])
    out = tmp_path / "data"
    freeze([build_pair(source, cache, offline=True)], out)
    return out


def _score(data: Path, out: Path, predictor: str = PREDICTOR) -> dict:
    assert (
        run_eval.main(["score", "--data", str(data), "--predictor", predictor, "--out", str(out)])
        == 0
    )
    return json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))


def _wrong_unique(report: dict, pair: str | None = None) -> list[dict]:
    return [
        m
        for m in report["target_mismatches"]
        if m["pred_target_address"] is not None and (pair is None or m["pair_id"] == pair)
    ]


def test_pipeline_predictor_on_mini_fixture(mini_dataset: Path, tmp_path: Path):
    preds = pipeline_predictor.predict(mini_dataset / "mini")
    report = _score(mini_dataset, tmp_path / "out" / "mini")

    for pred in preds:
        assert set(pred) >= {"src_address", "op", "target_address"}
    overall = report["overall"]["all"]
    assert (overall["op_lexical_agreement"]["passed"], overall["n_gold"]) == (5, 5)
    assert _wrong_unique(report) == []
    item3 = [p for p in preds if p["src_address"] == "khoan 3 dieu 1"]
    assert [p["target_address"] for p in item3] == ["khoan 5 dieu 6"]
    # the parent item 2 is context only: no edge, so no unmatched prediction for it
    assert "khoan 2 dieu 1" not in [p["src_address"] for p in preds]
    assert report["unmatched_predictions"] == []


def test_pipeline_predictor_on_suffix_fixture(suffix_dataset: Path, tmp_path: Path):
    report = _score(suffix_dataset, tmp_path / "out" / "suffix")
    preds = pipeline_predictor.predict(suffix_dataset / "mini-suffix")

    overall = report["overall"]["all"]
    assert (overall["target_accuracy"]["passed"], overall["n_gold"]) == (4, 4)
    assert sorted(p["target_address"] for p in preds) == [
        "diem d1 khoan 2 dieu 3",
        "diem d2 khoan 2 dieu 3",
        "dieu 30a",
        "khoan 5a dieu 18",
    ]


def test_pipeline_predictor_article_only_mode(mini_dataset: Path):
    preds = pipeline_predictor.predict_article_only(mini_dataset / "mini")

    assert preds
    for pred in preds:
        target = pred["target_address"]
        assert target is None or (isinstance(target, str) and target)
        assert pred["status"] in ("UNIQUE", "AMBIGUOUS", "NOT_FOUND")
        assert (target is not None) == (pred["status"] == "UNIQUE")


def test_wilson_parity_app_vs_harness():
    for n in range(0, 101):
        for k in range(0, n + 1):
            assert wilson_lower(k, n) == wilson(k, n)[0], (k, n)


# ---- Tests After: committed reports ---------------------------------------------------------------


def _report(name: str) -> dict:
    return json.loads((REPORTS / f"{name}.json").read_text(encoding="utf-8"))


def test_committed_p3_reports_are_reproducible(tmp_path: Path):
    fresh = pipeline_predictor.write_reports(COMMITTED_DATA, tmp_path)

    for name, _ in pipeline_predictor.REPORTS:
        assert fresh[name] == _report(name), name
        for suffix in (".json", ".md"):
            committed = (REPORTS / f"{name}{suffix}").read_bytes().replace(b"\r\n", b"\n")
            assert (tmp_path / f"{name}{suffix}").read_bytes() == committed, name + suffix
        # the block on top of the plain run_eval report is only the P1 comparison
        plain = _score(
            COMMITTED_DATA, tmp_path / "plain" / name, dict(pipeline_predictor.REPORTS)[name]
        )
        assert {k: v for k, v in fresh[name].items() if k != "p1_baseline_comparison"} == plain


def test_p3_report_not_worse_than_baseline():
    p1, p3 = _report("p1-baseline"), _report("p3-operation-parser")
    assert p1["dataset"]["manifest_sha256"] == p3["dataset"]["manifest_sha256"]

    for op, base in p1["overall"]["by_op"].items():
        if base["n_gold"] == 0:
            continue
        new = p3["overall"]["by_op"][op]
        assert new["op_lexical_agreement"]["passed"] >= base["op_lexical_agreement"]["passed"], op
        assert new["target_accuracy"]["passed"] >= base["target_accuracy"]["passed"], op
        # RT-09 precision: predictions that agree with no gold must not grow
        base_noise = base["n_pred"] - base["op_precision"]["passed"]
        new_noise = new["n_pred"] - new["op_precision"]["passed"]
        assert new_noise <= base_noise, (op, new_noise, base_noise)
    assert len(p3["unmatched_predictions"]) <= len(p1["unmatched_predictions"])


def test_p3_nd50_no_wrong_unique_target():
    p3 = _report("p3-operation-parser")

    assert p3["by_pair"]["nd50-2021"]["all"]["n_gold"] == 26
    assert _wrong_unique(p3, "nd50-2021") == []
