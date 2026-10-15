from __future__ import annotations

import pytest

from evals.contract_graph.score import GROUND_TRUTH_LABEL, render_markdown, score, wilson


def g(no: int, src: str, op: str, target: str | None, pair: str = "p1") -> dict:
    return {"pair_id": pair, "note_no": no, "src_address": src, "op": op, "target_address": target}


def p(src: str, op: str, target: str | None, pair: str = "p1") -> dict:
    return {"pair_id": pair, "src_address": src, "op": op, "target_address": target}


def test_wilson_known_values():
    lo, hi = wilson(26, 26)
    assert lo == pytest.approx(0.87, abs=0.005)
    assert hi == pytest.approx(1.0)
    assert wilson(0, 0) == (0.0, 1.0)
    lo, hi = wilson(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-3)
    assert hi == pytest.approx(0.7634, abs=1e-3)


def test_per_op_metrics_have_explicit_denominators():
    report = score(
        [
            g(1, "khoan 1 dieu 1", "SUBSTITUTION", "khoan 2 dieu 3"),
            g(2, "khoan 2 dieu 1", "REPEAL", "khoan 3 dieu 7"),
        ],
        [p("khoan 1 dieu 1", "SUBSTITUTION", "khoan 2 dieu 3")],
    )

    sub = report["overall"]["by_op"]["SUBSTITUTION"]
    assert sub["n_gold"] == 1 and sub["n_pred"] == 1
    for metric in ("src_found", "op_lexical_agreement", "op_precision", "target_accuracy"):
        rate = sub[metric]
        assert set(rate) == {"passed", "denominator", "rate", "wilson95"}
        assert rate["passed"] == 1 and rate["denominator"] == 1
    rep = report["overall"]["by_op"]["REPEAL"]
    assert rep["src_found"] == {
        "passed": 0,
        "denominator": 1,
        "rate": 0.0,
        "wilson95": [0.0, 0.7935],
    }
    assert rep["op_precision"]["denominator"] == 0 and rep["op_precision"]["rate"] is None
    assert rep["target_accuracy"]["denominator"] == 0
    assert report["ground_truth"] == GROUND_TRUTH_LABEL == "vbhn-note auto-gold (approved=false)"


def test_prediction_without_gold_is_unmatched_and_lowers_precision():
    report = score(
        [g(1, "khoan 1 dieu 1", "SUBSTITUTION", "khoan 2 dieu 3")],
        [
            p("khoan 1 dieu 1", "SUBSTITUTION", "khoan 2 dieu 3"),
            p("khoan 2 dieu 1", "SUBSTITUTION", "khoan 2 dieu 4"),
        ],
    )

    sub = report["overall"]["by_op"]["SUBSTITUTION"]
    assert sub["op_precision"]["passed"] == 1 and sub["op_precision"]["denominator"] == 2
    assert report["unmatched_predictions"] == [
        {
            "pair_id": "p1",
            "src_address": "khoan 2 dieu 1",
            "op": "SUBSTITUTION",
            "target_address": "khoan 2 dieu 4",
        }
    ]


def test_target_accuracy_denominator_is_gold_with_prediction():
    report = score(
        [
            g(1, "khoan 1 dieu 1", "INSERTION", "khoan 5 dieu 6"),
            g(2, "khoan 2 dieu 1", "INSERTION", "khoan 7 dieu 7"),
            g(3, "khoan 3 dieu 1", "INSERTION", "khoan 1 dieu 9"),
        ],
        [
            p("khoan 1 dieu 1", "INSERTION", "khoan 4 dieu 6"),
            p("khoan 2 dieu 1", "INSERTION", "khoan 7 dieu 7"),
        ],
    )

    ins = report["overall"]["by_op"]["INSERTION"]
    assert ins["src_found"]["passed"] == 2 and ins["src_found"]["denominator"] == 3
    assert ins["target_accuracy"]["passed"] == 1 and ins["target_accuracy"]["denominator"] == 2
    assert [m["note_no"] for m in report["missed_gold"]] == [3]


def test_one_to_one_matching_with_shared_source():
    src = "diem e khoan 2 dieu 1"
    two_gold = [
        g(8, src, "INSERTION", "diem d1 khoan 2 dieu 3"),
        g(9, src, "INSERTION", "diem d2 khoan 2 dieu 3"),
    ]

    # (a) two gold, same src, two predictions with the right targets
    a = score(
        two_gold,
        [
            p(src, "INSERTION", "diem d1 khoan 2 dieu 3"),
            p(src, "INSERTION", "diem d2 khoan 2 dieu 3"),
        ],
    )
    assert a["overall"]["all"]["target_accuracy"]["passed"] == 2
    assert a["unmatched_predictions"] == []

    # (b) two gold, one prediction: one pair + one miss
    b = score(two_gold, [p(src, "INSERTION", "diem d1 khoan 2 dieu 3")])
    assert b["overall"]["all"]["src_found"] == {
        **b["overall"]["all"]["src_found"],
        "passed": 1,
        "denominator": 2,
    }
    assert [m["note_no"] for m in b["missed_gold"]] == [9]

    # (c) one gold, two predictions: the extra prediction is unmatched
    c = score(
        two_gold[:1],
        [
            p(src, "INSERTION", "diem d2 khoan 2 dieu 3"),
            p(src, "INSERTION", "diem d1 khoan 2 dieu 3"),
        ],
    )
    assert c["overall"]["all"]["target_accuracy"]["passed"] == 1
    assert len(c["unmatched_predictions"]) == 1
    assert c["unmatched_predictions"][0]["target_address"] == "diem d2 khoan 2 dieu 3"

    # (d) two gold, two predictions in swapped order: step 1 pairs on (src, target)
    d = score(
        two_gold,
        [
            p(src, "INSERTION", "diem d2 khoan 2 dieu 3"),
            p(src, "INSERTION", "diem d1 khoan 2 dieu 3"),
        ],
    )
    assert d["overall"]["all"]["target_accuracy"]["passed"] == 2


def test_other_gold_is_counted_not_scored():
    report = score(
        [
            g(1, "khoan 1 dieu 1", "OTHER", "khoan 1 dieu 5"),
            g(2, "khoan 2 dieu 1", "INSERTION", "khoan 2 dieu 5"),
        ],
        [
            p("khoan 1 dieu 1", "SUBSTITUTION", "khoan 1 dieu 5"),
            p("khoan 2 dieu 1", "INSERTION", "khoan 2 dieu 5"),
        ],
    )

    assert "OTHER" not in report["overall"]["by_op"]
    assert report["overall"]["n_gold_other"] == 1
    assert report["overall"]["n_pred_on_other"] == 1
    assert report["overall"]["all"]["src_found"]["denominator"] == 1
    assert report["overall"]["by_op"]["SUBSTITUTION"]["n_pred"] == 0
    assert report["unmatched_predictions"] == []


def test_prediction_listing_targets_matches_one_gold_per_listed_target():
    src = "diem e khoan 2 dieu 1"
    two_gold = [
        g(8, src, "INSERTION", "diem d1 khoan 2 dieu 3"),
        g(9, src, "INSERTION", "diem d2 khoan 2 dieu 3"),
        g(10, src, "INSERTION", "diem d3 khoan 2 dieu 3"),
    ]
    listed = {
        **p(src, "INSERTION", "diem d1 khoan 2 dieu 3"),
        "target_addresses": ["diem d1 khoan 2 dieu 3", "diem d2 khoan 2 dieu 3"],
    }

    # step 1 on (src, each listed target): one prediction covers two gold, never the third
    r = score(two_gold, [listed])
    a = r["overall"]["all"]
    assert (a["src_found"]["passed"], a["src_found"]["denominator"]) == (2, 3)
    assert a["target_accuracy"]["passed"] == 2
    assert [m["note_no"] for m in r["missed_gold"]] == [10]
    # precision counts the prediction once per listed target
    assert (a["op_precision"]["passed"], a["op_precision"]["denominator"]) == (2, 2)
    assert r["unmatched_predictions"] == []

    # wrong targets still pair by src (step 2), but at most once per listed target
    wrong = {**listed, "target_addresses": ["diem d1 dieu 3", "diem d2 dieu 3"]}
    r = score(two_gold, [wrong])
    assert r["overall"]["all"]["src_found"]["passed"] == 2
    assert r["overall"]["all"]["target_accuracy"]["passed"] == 0
    assert [m["pred_target_address"] for m in r["target_mismatches"]] == [
        "diem d1 dieu 3",
        "diem d2 dieu 3",
    ]

    # a listed target nobody claims is an unmatched prediction slot
    r = score(two_gold[:1], [listed])
    assert r["overall"]["all"]["op_precision"]["denominator"] == 2
    assert [u["target_address"] for u in r["unmatched_predictions"]] == ["diem d2 khoan 2 dieu 3"]


def test_op_metric_is_named_lexical_agreement():
    report = score(
        [g(1, "khoan 1 dieu 1", "SUBSTITUTION", "x")], [p("khoan 1 dieu 1", "SUBSTITUTION", "x")]
    )

    def keys(obj: object) -> set[str]:
        if isinstance(obj, dict):
            return set(obj) | set().union(*(keys(v) for v in obj.values()))
        if isinstance(obj, list):
            return set().union(*(keys(v) for v in obj)) if obj else set()
        return set()

    all_keys = keys(report)
    assert "op_lexical_agreement" in all_keys
    assert not all_keys & {"op_correct", "op_accuracy"}
    md = render_markdown(report)
    assert "op_lexical_agreement" in md
    assert "đồng thuận từ vựng" in md
    assert "vbhn-note auto-gold (approved=false)" in md


def test_report_has_by_pair_breakdown():
    gold = [
        g(1, "khoan 1 dieu 1", "SUBSTITUTION", "khoan 2 dieu 3", "a"),
        g(2, "khoan 2 dieu 1", "REPEAL", "khoan 3 dieu 7", "a"),
        g(1, "khoan 1 dieu 1", "SUBSTITUTION", "khoan 9 dieu 9", "b"),
    ]
    preds = [
        p("khoan 1 dieu 1", "SUBSTITUTION", "khoan 2 dieu 3", "a"),
        p("khoan 2 dieu 1", "REPEAL", "khoan 3 dieu 7", "a"),
        p("khoan 1 dieu 1", "SUBSTITUTION", "khoan 9 dieu 9", "b"),
    ]

    report = score(gold, preds)

    assert list(report["by_pair"]) == ["a", "b"]
    for pid in ("a", "b"):
        assert set(report["by_pair"][pid]) == set(report["overall"])
    total = sum(
        report["by_pair"][pid]["all"]["target_accuracy"]["passed"] for pid in report["by_pair"]
    )
    assert total == report["overall"]["all"]["target_accuracy"]["passed"] == 3
    # predictions are never paired across documents
    cross = score(
        [g(1, "khoan 1 dieu 1", "SUBSTITUTION", "x", "a")],
        [p("khoan 1 dieu 1", "SUBSTITUTION", "x", "b")],
    )
    assert cross["overall"]["all"]["src_found"]["passed"] == 0
