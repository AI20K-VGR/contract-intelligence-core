"""Evaluation diagnostics must disclose denominators and exclusions without IDs."""

from __future__ import annotations

import pytest

from evals.clause_frame_release import evaluate_release
from evals.clause_frame_scoring import PAIR_DISPOSITIONS, REQUIRED_METRICS
from evals.unit_metrics import UnitRecord

PROFILES = (
    "SALES",
    "SUPPLY_SERVICE",
    "LEASE",
    "CONSTRUCTION_WORK",
    "EMPLOYMENT",
    "NDA",
)
BADNESS = {
    "key_wrong_definite",
    "pair_false_duplicate",
    "citation_extra",
    "value_fabricated",
}


def _policy() -> dict:
    names = REQUIRED_METRICS | {f"pair_precision.{item}" for item in PAIR_DISPOSITIONS}
    return {
        "approved_by": "user",
        "approval_ref": "synthetic-test-only",
        "frozen_at": "2026-10-03T01:00:00Z",
        **dict.fromkeys(
            (
                "dev_baseline_hash",
                "dev_gold_hash",
                "scorer_hash",
                "split_hash",
                "historical_plan_a_card_hash",
            ),
            "a" * 64,
        ),
        "metrics": [
            {
                "metric": metric,
                "unit": "pair" if metric.startswith("pair_") else "clause",
                "eligibility": "frozen-gold",
                "predicate": "exact",
                "strata": list(PROFILES),
                "minimum_units": 60,
                "stratum_minimum_units": 1,
                "threshold_source": "synthetic-test-only",
                "threshold": 0
                if metric in BADNESS
                else 1
                if metric in {"citation_valid", "certainty_safety"}
                else 0.95,
                "direction": "max" if metric in BADNESS else "min",
            }
            for metric in sorted(names)
        ],
    }


def test_release_reports_denominators_uncertainty_and_aggregate_exclusions() -> None:
    records = [
        UnitRecord(
            "pair_false_duplicate",
            f"pair-{index}",
            "unit",
            True,
            "dossier-sales",
            split="heldout",
        )
        for index in range(120)
    ]
    result = evaluate_release(
        records,
        records,
        _policy(),
        profiles={"dossier-sales": "SALES"},
        exclusions=[
            {
                "metric": "pair_false_duplicate",
                "item_id": "private-pair-1",
                "unit_id": "private-unit-1",
                "dossier_id": "dossier-sales",
                "category": "PAIR",
                "reason": "OUT_OF_SCOPE",
            },
            {
                "metric": "ordinary_slot.actor",
                "item_id": "private-clause-1",
                "unit_id": "private-unit-2",
                "dossier_id": "dossier-sales",
                "category": "CLAUSE",
                "reason": "SOURCE_AMBIGUOUS",
            },
        ],
    )

    metric = next(
        row
        for row in result["strata"]
        if row["metric"] == "pair_false_duplicate" and row["scope"] == "overall"
    )
    assert metric["n"] == 120
    assert metric["wilson_lower"] is not None
    assert metric["cluster_lower"] is not None
    assert result["eligibility"] == {
        "eligible_units": 120,
        "eligible_pair_units": 120,
        "excluded_units": 2,
        "exclusion_status": "REPORTED",
        "exclusions_by_category_reason": {
            "CLAUSE:SOURCE_AMBIGUOUS": 1,
            "PAIR:OUT_OF_SCOPE": 1,
        },
    }
    assert "private-" not in str(result)


def test_missing_exclusion_ledger_is_reported_as_unknown_not_zero() -> None:
    record = UnitRecord(
        "pair_false_duplicate", "pair-1", "unit", True, "dossier-sales", split="heldout"
    )
    result = evaluate_release(
        [record], [record], _policy(), profiles={"dossier-sales": "SALES"}
    )

    assert result["eligibility"]["eligible_units"] == 1
    assert result["eligibility"]["eligible_pair_units"] == 1
    assert result["eligibility"]["excluded_units"] is None
    assert result["eligibility"]["exclusion_status"] == "NOT_REPORTED"


def test_exclusion_report_rejects_unrecognized_codes_and_identifying_text() -> None:
    record = UnitRecord(
        "pair_false_duplicate", "pair-1", "unit", True, "dossier-sales", split="heldout"
    )

    with pytest.raises(ValueError, match="unsupported exclusion code"):
        evaluate_release(
            [record],
            [record],
            _policy(),
            profiles={"dossier-sales": "SALES"},
            exclusions=[_excluded_unit(category="pair C:\\private\\dossier.pdf")],
        )


def _excluded_unit(**overrides: str) -> dict[str, str]:
    return {
        "metric": "pair_false_duplicate",
        "item_id": "private-excluded-item",
        "unit_id": "private-excluded-unit",
        "dossier_id": "dossier-sales",
        "category": "PAIR",
        "reason": "OUT_OF_SCOPE",
        **overrides,
    }


@pytest.mark.parametrize("mutate", ["duplicate", "overlap"])
def test_exclusion_units_must_be_unique_and_disjoint_from_eligible(mutate: str) -> None:
    record = UnitRecord(
        "pair_false_duplicate",
        "eligible-item",
        "eligible-unit",
        True,
        "dossier-sales",
        split="heldout",
    )
    first = _excluded_unit()
    second = dict(first)
    if mutate == "overlap":
        first.update(
            metric=record.metric,
            item_id=record.item_id,
            unit_id=record.unit_id,
            dossier_id=record.cluster,
        )
    else:
        second = dict(first)

    with pytest.raises(ValueError, match="unique and disjoint"):
        evaluate_release(
            [record],
            [record],
            _policy(),
            profiles={"dossier-sales": "SALES"},
            exclusions=[first, second],
        )
