from __future__ import annotations

import pytest

from evals.clause_frame_scoring import (
    REQUIRED_METRICS,
    compare_units,
    score_units,
    validate_policy,
)
from evals.unit_metrics import MetricSpec, UnitRecord


def unit(name, passed=True, metric="ordinary_slot.actor"):
    return UnitRecord(metric, "d1/frame1", name, passed, "d1", split="dev")


@pytest.mark.parametrize("current", [[unit("actor", False), unit("action")],
                                     [unit("action")], []])
def test_each_passed_unit_and_missing_item_blocks_regression(current):
    diff = compare_units([unit("actor"), unit("action")], current, [])
    assert any(x.unit_id == "actor" and not x.passed for x in diff.regressions)


def test_new_tripwire_failure_blocks_even_when_old_metric_stays_green():
    failed = unit("extra", False, "citation_valid")
    diff = compare_units([], [failed], [MetricSpec("citation_valid", 1, 60, 0)])
    assert diff.regressions == (failed,)


def test_duplicate_identity_is_setup_error_not_or_aggregation():
    with pytest.raises(ValueError, match="duplicate"):
        compare_units([unit("actor"), unit("actor")], [], [])


@pytest.mark.parametrize("metric", ["ordinary_slot.exception", "parameter_slot.base",
                                    "timeline_target"])
def test_required_family_cannot_be_masked_by_remedy(metric):
    specs = [MetricSpec(metric, 1, 1), MetricSpec("remedy", 1, 1)]
    report = score_units([unit("x", False, metric), unit("r", True, "remedy")], specs)
    assert report["status"] == "FAIL"
    assert report["metrics"][0]["status"] == "FAIL"


def test_zero_denominator_and_underpowered_are_not_pass():
    spec = MetricSpec("ordinary_slot.actor", .95, 60)
    assert score_units([], [spec])["status"] == "NOT_MEASURED"
    assert score_units([unit("actor")], [spec])["status"] == "UNDERPOWERED"


def test_intervals_do_not_replace_point_gate():
    records = [unit(str(i)) for i in range(60)]
    report = score_units(records, [MetricSpec("ordinary_slot.actor", .95)])
    assert report["status"] == "PASS(point)"
    assert report["metrics"][0]["wilson_lower"] < .95


def test_missing_full_metric_policy_cannot_be_ready():
    assert validate_policy({})["status"] == "BLOCKED"


def test_freeze_after_tuning_is_rejected():
    report = validate_policy({"approved_by": "user", "frozen_at": "2026-10-03T12:00:00Z",
                              "tuning_started_at": "2026-10-03T11:00:00Z"})
    assert "POLICY_FROZEN_AFTER_TUNING" in report["reasons"]


def test_policy_pins_are_checked_against_runtime_context():
    policy = {
        "approved_by": "user", "approval_ref": "ref",
        "frozen_at": "2026-10-03T12:00:00Z",
        "dev_baseline_hash": "baseline", "dev_gold_hash": "gold",
        "scorer_hash": "old-scorer", "split_hash": "split",
        "historical_plan_a_card_hash": "plan",
    }
    report = validate_policy(policy, expected_pins={"scorer_hash": "current-scorer"})
    assert "POLICY_PIN_MISMATCH:scorer_hash" in report["reasons"]


def test_unknown_prediction_metric_cannot_pass():
    with pytest.raises(ValueError, match="undeclared"):
        score_units([unit("bad", False, "undeclared")],
                    [MetricSpec("ordinary_slot.actor", .95, 60)])


def complete_policy(pair_metric="pair_precision.DUPLICATE"):
    return {
        "approved_by": "user", "approval_ref": "test-only",
        "frozen_at": "2026-10-03T12:00:00Z",
        **dict.fromkeys(("dev_baseline_hash", "dev_gold_hash", "scorer_hash",
                         "split_hash", "historical_plan_a_card_hash"), "a" * 64),
        "metrics": [
            {"metric": name, "unit": "test", "eligibility": "test",
             "predicate": "exact", "strata": ["test"], "minimum_units": 1,
             "threshold_source": "test-only", "threshold": 1, "direction": "min"}
            for name in sorted(REQUIRED_METRICS | {pair_metric})
        ],
    }


@pytest.mark.parametrize("metric", ["pair_precision.INVENTED", "pair_precision.",
                                    "ordinary_slot.invented"])
def test_policy_rejects_unknown_metric_even_with_complete_required_specs(metric):
    policy = complete_policy()
    policy["metrics"].append({**policy["metrics"][0], "metric": metric})
    assert "UNSUPPORTED_METRIC" in validate_policy(policy)["reasons"]


def test_known_pair_disposition_remains_valid_in_complete_policy():
    assert validate_policy(complete_policy())["status"] == "POLICY_VALIDATED"


@pytest.mark.parametrize("pin", ["dev_baseline_hash", "dev_gold_hash", "scorer_hash",
                                 "split_hash", "historical_plan_a_card_hash"])
def test_policy_requires_sha256_pins_not_arbitrary_labels(pin):
    policy = complete_policy()
    policy[pin] = "unverified-reference"
    assert "POLICY_PINS_INVALID" in validate_policy(policy)["reasons"]


@pytest.mark.parametrize("timestamp", ["2026-10-04T10:00:00", "garbage"])
def test_tuning_timestamp_must_be_timezone_aware(timestamp):
    policy = complete_policy()
    policy["tuning_started_at"] = timestamp
    assert "TUNING_TIMESTAMP_INVALID" in validate_policy(policy)["reasons"]
