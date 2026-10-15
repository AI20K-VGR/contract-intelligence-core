from __future__ import annotations

from evals.contract_graph.pairs.recall_diagnostic import diagnose_trial


def _trial(**overrides):
    trial = {
        "variant": "E",
        "trial": 1,
        "predictions": [],
        "rejected": {"unrelated": 1},
        "traces": [],
        "over_budget": False,
    }
    trial.update(overrides)
    return trial


def test_diagnose_trial_separates_candidate_and_classifier_misses():
    gold = [
        {"pair_id": "miss", "doc_id": "d1", "gold_label": "CONFLICT"},
        {"pair_id": "unrelated", "doc_id": "d1", "gold_label": "DUPLICATE"},
        {"pair_id": "hit", "doc_id": "d1", "gold_label": "REFERENCE"},
    ]
    candidates = {
        "d1": {
            "missed": {"sources": ["SAME_KEY"], "score": 2.0},
            "unrelated": {"sources": ["SAME_ARTICLE"], "score": 1.0},
            "hit": {"sources": ["EXPLICIT_REF"], "score": 4.0},
        }
    }
    result = diagnose_trial(
        _trial(
            predictions=[
                {"pair_id": "hit", "doc_id": "d1", "label": "REFERENCE", "direction": "A"}
            ],
            rejected={"unrelated": 1},
        ),
        gold=gold,
        candidates=candidates,
    )

    by_pair = {row["pair_id"]: row for row in result["gold_outcomes"]}
    assert by_pair["miss"]["failure_class"] == "candidate_miss"
    assert by_pair["miss"]["candidate"] is None
    assert by_pair["unrelated"]["failure_class"] == "classifier_unrelated"
    assert by_pair["unrelated"]["candidate"]["score"] == 1.0
    assert by_pair["hit"]["failure_class"] == "correct"
    assert result["candidate_accounting"]["unaccounted"] == 0


def test_diagnose_trial_records_validation_and_provider_failures_without_raw_payloads():
    gold = [{"pair_id": "d1-p1", "doc_id": "d1", "gold_label": "CONFLICT"}]
    result = diagnose_trial(
        _trial(
            predictions=[],
            rejected={"bad_span": 1, "unrelated": 0},
            traces=[
                {
                    "doc_id": "d1",
                    "error_type": "TimeoutError",
                    "classification_failed": True,
                    "served_model": "gpt-5.5",
                }
            ],
            over_budget=True,
        ),
        gold=gold,
        candidates={"d1": {"d1-p1": {"sources": [], "score": 0.0}}},
    )

    assert result["failure_counts"]["validation_reject"] == 1
    assert result["provider_or_budget"]["provider_error_traces"] == 1
    assert result["provider_or_budget"]["over_budget"] is True
    assert result["gold_outcomes"][0]["failure_class"] == "unclassified_or_provider"
    assert "TimeoutError" not in result["gold_outcomes"][0]


def test_exact_pair_events_override_aggregate_rejection_attribution():
    gold = [
        {"pair_id": "p-unrelated", "doc_id": "d1", "gold_label": "CONFLICT"},
        {"pair_id": "p-invalid", "doc_id": "d1", "gold_label": "DUPLICATE"},
        {"pair_id": "p-missing", "doc_id": "d1", "gold_label": "REFERENCE"},
    ]
    candidates = {"d1": {row["pair_id"]: {"sources": ["S1"], "score": 1.0} for row in gold}}
    result = diagnose_trial(
        _trial(rejected={"unrelated": 1, "bad_span": 1}, pair_events=[
            {"pair_id": "p-unrelated", "outcome": "model_unrelated", "reason": "unrelated"},
            {"pair_id": "p-invalid", "outcome": "validator_reject", "reason": "ungrounded_span"},
            {"pair_id": "p-missing", "outcome": "no_answer", "reason": "no_answer"},
        ]),
        gold=gold,
        candidates=candidates,
    )
    by_pair = {row["pair_id"]: row for row in result["gold_outcomes"]}
    assert by_pair["p-unrelated"]["failure_class"] == "classifier_unrelated"
    assert by_pair["p-invalid"]["failure_class"] == "validation_reject"
    assert by_pair["p-missing"]["failure_class"] == "no_answer"
    assert all(row["evidence_scope"] == "pair" for row in by_pair.values())
    assert result["failure_counts"]["validation_reject"] == 1
    assert result["pair_event_accounting"]["candidate_terminal_events"] == 3
    assert result["pair_event_accounting"]["candidate_terminal_missing"] == 0
    assert result["pair_event_accounting"]["accepted_event_prediction_difference"] == 0


def test_abstained_event_has_its_own_failure_class():
    result = diagnose_trial(
        _trial(pair_events=[
            {"pair_id": "p-abstain", "outcome": "abstained", "reason": "abstained"},
        ]),
        gold=[{"pair_id": "p-abstain", "doc_id": "d1", "gold_label": "REFERENCE"}],
        candidates={"d1": {"p-abstain": {"sources": ["EXPLICIT_REF"], "score": 4.0}}},
    )
    outcome = result["gold_outcomes"][0]
    assert outcome["failure_class"] == "classifier_abstained"
    assert outcome["pair_event"]["outcome"] == "abstained"


def test_false_duplicate_is_a_hard_stop():
    result = diagnose_trial(
        _trial(
            predictions=[
                {"pair_id": "d1-p1", "doc_id": "d1", "label": "DUPLICATE", "direction": None}
            ],
            rejected={"unrelated": 0},
        ),
        gold=[{"pair_id": "d1-p1", "doc_id": "d1", "gold_label": "CONFLICT"}],
        candidates={"d1": {"d1-p1": {"sources": [], "score": 0.0}}},
    )

    assert result["hard_stops"] == ["false_duplicate"]
    assert result["false_duplicate"] == {"observed": 1, "unreviewed": 0}
