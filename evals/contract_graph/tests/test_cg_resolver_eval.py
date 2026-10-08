from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import COMMITTED_DATA, MINI_SOURCES, REPO_ROOT, seed_cache
from evals.contract_graph import resolver_eval
from evals.contract_graph.gold import canonical_address

from app.pipeline.contract_graph.address import canonical, parse_addresses

P1_BASELINE = REPO_ROOT / "evals" / "contract_graph" / "reports" / "p1-baseline.json"


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


def _rows(report: dict, shape: str, pair: str) -> dict:
    return {(r["note_no"]): r for r in report["tree_shapes"][shape]["rows"] if r["pair_id"] == pair}


@pytest.mark.parametrize(
    "text",
    [
        "điểm đ khoản 2 Điều 1",
        "điểm d khoản 2 Điều 1",
        "khoản 5 Điều 4",
        "Điều 7",
        "Phụ lục 01",
        "điểm d1 khoản 2 Điều 3",
        "điểm i1 khoản 1 Điều 3",
        "khoản 5a Điều 18",
        "khoản 05a Điều 018",
        "Điều 30a",
        "Điểm Đ khoản 2 Điều 1",
    ],
)
def test_gold_and_app_canonical_forms_agree(text):
    # forms the gold extractor emits; "Phụ lục số N" / Roman numerals are outside gold.py's
    # input grammar (anchor_target writes "phụ lục <n>"), see report limitations
    (addr,) = parse_addresses(text)

    assert canonical(addr) == canonical_address(text)


def test_resolver_eval_on_mini_fixture(mini_dataset: Path):
    report = resolver_eval.run(mini_dataset, ("full",), baseline_path=None)
    rows = _rows(report, "full", "mini")

    # item 1 / 4: plain addresses resolve exactly
    assert (rows[1]["status"], rows[1]["method"], rows[1]["correct"]) == ("UNIQUE", "EXACT", True)
    assert (rows[5]["status"], rows[5]["method"], rows[5]["correct"]) == ("UNIQUE", "EXACT", True)
    # item 3 (INSERTION): the new address, not the anchor
    assert rows[4]["status"] == "UNIQUE"
    assert rows[4]["pred_target_address"] == "khoan 5 dieu 6"
    assert rows[4]["correct"] is True
    # 2a / 2b under "khoản 1 và khoản 2 Điều 4": locked or AMBIGUOUS, never a wrong UNIQUE
    for note in (2, 3):
        assert rows[note]["multi_clause"] is True
        assert rows[note]["status"] in ("UNIQUE", "AMBIGUOUS")
        if rows[note]["status"] == "UNIQUE":
            assert rows[note]["correct"] is True
    assert report["tree_shapes"]["full"]["wrong_unique"] == []


def test_resolver_eval_on_suffix_fixture(suffix_dataset: Path):
    report = resolver_eval.run(suffix_dataset, ("full",), baseline_path=None)
    rows = _rows(report, "full", "mini-suffix")

    assert {n: (r["status"], r["pred_target_address"]) for n, r in rows.items()} == {
        1: ("UNIQUE", "diem d1 khoan 2 dieu 3"),
        2: ("UNIQUE", "diem d2 khoan 2 dieu 3"),
        3: ("UNIQUE", "khoan 5a dieu 18"),
        4: ("UNIQUE", "dieu 30a"),
    }
    assert all(r["correct"] for r in rows.values())
    preds = [
        slot["target_address"]
        for slot in report["tree_shapes"]["full"]["slots"]
        if slot["target_address"]
    ]
    assert not {"diem d khoan 2 dieu 3", "khoan 5 dieu 18", "dieu 30"} & set(preds)


def test_report_has_method_breakdown_and_wilson(mini_dataset: Path, tmp_path: Path):
    out = tmp_path / "out" / "p2"
    code = resolver_eval.main(
        ["--data", str(mini_dataset), "--out", str(out), "--tree-shape", "full", "--baseline", ""]
    )
    assert code == 0
    report = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    overall = report["tree_shapes"]["full"]["overall"]

    assert set(overall["status"]) == {"UNIQUE", "AMBIGUOUS", "NOT_FOUND"}
    assert sum(overall["status"].values()) == overall["items"] == 5
    for key in ("precision", "coverage", "accuracy"):
        assert set(overall[key]) == {"passed", "denominator", "rate", "wilson95"}
    assert "EXACT" in overall["by_method"]
    exact = overall["by_method"]["EXACT"]
    assert set(exact["precision"]) == {"passed", "denominator", "rate", "wilson95"}
    md = out.with_suffix(".md").read_text(encoding="utf-8")
    assert "EXACT" in md and "CI95" in md


def test_report_has_both_tree_shapes(mini_dataset: Path, tmp_path: Path):
    out = tmp_path / "out" / "p2"
    assert (
        resolver_eval.main(["--data", str(mini_dataset), "--out", str(out), "--baseline", ""]) == 0
    )
    report = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))

    assert set(report["tree_shapes"]) == {"full", "article-only"}
    collapsed = report["tree_shapes"]["article-only"]
    assert collapsed["overall"]["by_method"]["ANCESTOR"]["unique"] > 0
    wrong = [r for r in collapsed["rows"] if r["status"] == "UNIQUE" and not r["correct"]]
    assert collapsed["wrong_unique"] == wrong
    md = out.with_suffix(".md").read_text(encoding="utf-8")
    assert "full" in md and "article-only" in md
    assert "UNIQUE sai" in md


# ---- Tests After: committed dataset -------------------------------------------------------------


@pytest.fixture(scope="module")
def committed_report() -> dict:
    return resolver_eval.run(COMMITTED_DATA, ("full", "article-only"), baseline_path=P1_BASELINE)


def test_nd50_no_wrong_unique_on_multi_clause_items(committed_report: dict):
    rows = [
        r
        for r in committed_report["tree_shapes"]["full"]["rows"]
        if r["pair_id"] == "nd50-2021" and r["multi_clause"]
    ]

    assert len(rows) >= 10
    assert all(r["status"] in ("UNIQUE", "AMBIGUOUS") for r in rows), rows
    assert [r for r in rows if r["status"] == "UNIQUE" and not r["correct"]] == []


def test_nd50_correct_unique_not_below_p1_baseline(committed_report: dict):
    baseline = json.loads(P1_BASELINE.read_text(encoding="utf-8"))
    p1_correct = baseline["by_pair"]["nd50-2021"]["all"]["target_accuracy"]["passed"]
    nd50 = committed_report["tree_shapes"]["full"]["by_pair"]["nd50-2021"]

    assert committed_report["p1_baseline"]["nd50-2021"]["target_correct"] == p1_correct
    assert nd50["unique_correct"] >= p1_correct
