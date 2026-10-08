from __future__ import annotations

from evals.contract_graph.pairs import score


def _gold(pid: str, label: str | None, direction: str | None = None, approved: bool = True,
          stratum: str = "S1", doc: str = "pd-1") -> dict:
    return {"pair_id": pid, "gold_label": label, "gold_direction": direction,
            "approved": approved, "source": "user-review", "stratum": stratum, "doc_id": doc}


def _pred(pid: str, label: str, direction: str | None = None, stratum: str = "S1",
          doc: str = "pd-1", **extra) -> dict:
    return {"pair_id": pid, "label": label, "direction": direction, "stratum": stratum,
            "doc_id": doc, **extra}


def test_conservative_precision_counts_unreviewed_as_wrong():
    preds = [_pred(f"p{i}", "CONFLICT") for i in range(70)]
    gold = [_gold(f"p{i}", "CONFLICT") for i in range(40)]
    gold += [_gold(f"p{i}", "UNRELATED") for i in range(40, 54)]
    gold += [_gold(f"g{i}", "CONFLICT") for i in range(10)]  # positives nobody predicted
    report = score.score_relations(gold, preds, approved_only=True)
    block = report["by_label"]["CONFLICT"]

    assert block["precision_conservative"]["passed"] == 40
    assert block["precision_conservative"]["denominator"] == 70
    assert block["precision_observed"]["passed"] == 40
    assert block["precision_observed"]["denominator"] == 54
    assert block["recall_observed"]["passed"] == 40
    assert block["recall_observed"]["denominator"] == 50
    assert (block["denominator"], block["covered"], block["passed"]) == (70, 54, 40)
    assert block["precision_conservative"]["wilson95"][1] < block["precision_observed"]["rate"]
    assert "UNRELATED" not in report["by_label"]
    assert report["ground_truth"]


def test_weighted_estimate_uses_inverse_pi():
    preds = [_pred("p1", "CONFLICT"), _pred("p2", "CONFLICT"), _pred("p3", "CONFLICT"),
             _pred("p4", "CONFLICT"), _pred("p5", "UNRELATED"), _pred("p6", "CONFLICT")]
    gold = [_gold("p1", "CONFLICT"), _gold("p2", "CONFLICT"), _gold("p3", "UNRELATED"),
            _gold("p4", "DUPLICATE"), _gold("p5", "CONFLICT")]
    selection = [
        {"pair_id": "p1", "stratum": "S1", "gpt_label": "CONFLICT", "pi": 1.0},
        {"pair_id": "p2", "stratum": "S1", "gpt_label": "CONFLICT", "pi": 0.5},
        {"pair_id": "p3", "stratum": "S1", "gpt_label": "CONFLICT", "pi": 0.25},
        {"pair_id": "p4", "stratum": "S1", "gpt_label": "CONFLICT", "pi": 1.0},
        {"pair_id": "p5", "stratum": "S1", "gpt_label": "UNRELATED", "pi": 0.5},
    ]
    report = score.score_relations(gold, preds, approved_only=True, selection=selection)
    block = report["by_label"]["CONFLICT"]

    assert report["estimator"] == "horvitz-thompson"
    assert block["precision_weighted"] == round(3 / 8, 4)
    assert block["recall_weighted"] == round(3 / 5, 4)
    # the weighted numbers carry no Wilson interval: they are reported, never gated
    assert not isinstance(block["precision_weighted"], dict)
    plain = score.score_relations(gold, preds, approved_only=True)
    assert plain["estimator"] is None
    assert plain["by_label"]["CONFLICT"]["precision_weighted"] is None


def test_false_duplicate_counted():
    preds = [_pred(f"d{i}", "DUPLICATE") for i in range(6)]
    gold = [_gold("d0", "DUPLICATE"), _gold("d1", "DUPLICATE"), _gold("d2", "DUPLICATE"),
            _gold("d3", "CONFLICT"), _gold("d4", "UNRELATED")]
    report = score.score_relations(gold, preds, approved_only=True)

    assert report["false_duplicate"] == {"observed": 2, "unreviewed": 1}
    assert report["by_label"]["DUPLICATE"]["precision_conservative"]["passed"] == 3


def test_approved_only_filters_unapproved_gold():
    preds = [_pred("p1", "CONFLICT"), _pred("p2", "CONFLICT"), _pred("p3", "CONFLICT")]
    gold = [_gold("p1", "CONFLICT"), _gold("p2", "CONFLICT", approved=False),
            _gold("p3", None, approved=False)]

    strict = score.score_relations(gold, preds, approved_only=True)["by_label"]["CONFLICT"]
    loose = score.score_relations(gold, preds, approved_only=False)["by_label"]["CONFLICT"]

    assert (strict["denominator"], strict["covered"], strict["passed"]) == (3, 1, 1)
    assert (loose["denominator"], loose["covered"], loose["passed"]) == (3, 2, 2)


def test_direction_accuracy_separate_from_label_match():
    preds = [_pred("p1", "GENERAL_SPECIFIC", "A"), _pred("p2", "GENERAL_SPECIFIC", "B"),
             _pred("p3", "REFERENCE", "A"), _pred("p4", "CONFLICT")]
    gold = [_gold("p1", "GENERAL_SPECIFIC", "A"), _gold("p2", "GENERAL_SPECIFIC", "A"),
            _gold("p3", "REFERENCE", "B"), _gold("p4", "CONFLICT")]
    report = score.score_relations(gold, preds, approved_only=True)["by_label"]

    assert report["GENERAL_SPECIFIC"]["precision_conservative"]["passed"] == 2
    assert report["GENERAL_SPECIFIC"]["direction_accuracy"]["passed"] == 1
    assert report["GENERAL_SPECIFIC"]["direction_accuracy"]["denominator"] == 2
    assert report["REFERENCE"]["direction_accuracy"]["passed"] == 0
    assert report["CONFLICT"]["direction_accuracy"] is None


def test_recall_by_stratum_and_by_doc():
    gold = [_gold("a", "CONFLICT", stratum="S1", doc="pd-1"),
            _gold("b", "CONFLICT", stratum="S2", doc="pd-1"),
            _gold("c", "CONFLICT", stratum="S2", doc="pd-2")]
    preds = [_pred("a", "CONFLICT", stratum="S1", doc="pd-1"),
             _pred("c", "CONFLICT", stratum="S2", doc="pd-2")]
    report = score.score_relations(gold, preds, approved_only=True)

    s1 = report["by_stratum"]["S1"]["CONFLICT"]["recall_observed"]
    s2 = report["by_stratum"]["S2"]["CONFLICT"]["recall_observed"]
    assert (s1["passed"], s1["denominator"]) == (1, 1)
    assert (s2["passed"], s2["denominator"]) == (1, 2)
    d1 = report["by_doc"]["pd-1"]["CONFLICT"]["recall_observed"]
    assert (d1["passed"], d1["denominator"]) == (1, 2)
    assert report["by_doc"]["pd-2"]["CONFLICT"]["recall_observed"]["passed"] == 1


def test_markdown_has_no_clause_text():
    secret = "Bên Mua thanh toán trong 30 ngày kể từ ngày nhận hàng"
    preds = [_pred("pair-1", "CONFLICT", span_a=secret, text_a=secret)]
    gold = [{**_gold("pair-1", "CONFLICT"), "note": secret}]
    md = score.render_markdown(score.score_relations(gold, preds, approved_only=True))

    assert secret not in md
    assert "Bên Mua" not in md
    assert "CONFLICT" in md and "pd-1" in md
