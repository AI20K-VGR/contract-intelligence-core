"""Scoring độc lập theo unit; chỉ tái sử dụng thống kê của Plan A."""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import asdict, replace
from datetime import datetime

from evals.unit_metrics import MetricSpec, RegressionDiff, UnitRecord, evaluate_metric

REQUIRED_METRICS = frozenset({
    "key_wrong_definite", "key_recall", "pair_false_duplicate", "pair_recall",
    "timeline_coverage", "timeline_edge", "timeline_target", "timeline_date_role",
    "timeline_date_value", "timeline_trigger", "proposed_effective_value",
    "citation_valid", "citation_extra", "value_fabricated", "certainty_safety",
    *(f"frame_coverage.{x}" for x in (
        "OBLIGATION", "RIGHT", "PROHIBITION", "REMEDY", "PARAMETER", "DEFINITION")),
    *(f"ordinary_slot.{x}" for x in (
        "actor", "beneficiary", "action", "modality_negation", "object_scope",
        "condition", "exception", "temporal_trigger", "deadline")),
    *(f"parameter_slot.{x}" for x in (
        "amount", "currency", "unit", "base", "period", "item_scope", "temporal_trigger")),
})

PAIR_DISPOSITIONS = frozenset({
    "GENERAL_VS_SPECIFIC", "NEEDS_REVIEW_BACKOFF", "SCOPE_DIFFERS",
    "NEEDS_REVIEW_UNPARSED", "NOT_COMPARABLE", "GRADUATED", "DUPLICATE",
    "COMPARABLE_DIFFERENCE", "CONFLICT_CANDIDATE", "CUMULATIVE",
})
SUPPORTED_METRICS = REQUIRED_METRICS | frozenset(
    f"pair_precision.{disposition}" for disposition in PAIR_DISPOSITIONS
)


def is_supported_metric(metric: object) -> bool:
    return isinstance(metric, str) and metric in SUPPORTED_METRICS


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("timestamp required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed


def validate_policy(policy: dict, *, expected_pins: dict[str, str] | None = None) -> dict:
    """Kiểm policy freeze; reference approval vẫn cần human evidence thật."""
    reasons = []
    if not isinstance(policy, dict):
        return {"status": "BLOCKED", "reasons": ["METRIC_POLICY_REQUIRED"]}
    if policy.get("approved_by") != "user" or not policy.get("approval_ref"):
        reasons.append("HUMAN_FREEZE_REQUIRED")
    frozen = None
    try:
        frozen = _timestamp(policy.get("frozen_at"))
    except (ValueError, TypeError):
        reasons.append("FREEZE_TIMESTAMP_INVALID")
    if policy.get("tuning_started_at") is not None:
        try:
            tuning = _timestamp(policy["tuning_started_at"])
            if frozen is not None and frozen >= tuning:
                reasons.append("POLICY_FROZEN_AFTER_TUNING")
        except (ValueError, TypeError):
            reasons.append("TUNING_TIMESTAMP_INVALID")
    pin_names = ("dev_baseline_hash", "dev_gold_hash", "scorer_hash",
                 "split_hash", "historical_plan_a_card_hash")
    if not all(policy.get(x) for x in pin_names):
        reasons.append("POLICY_PINS_REQUIRED")
    if any(not isinstance(policy.get(x), str)
           or re.fullmatch(r"[0-9a-f]{64}", policy[x]) is None for x in pin_names):
        reasons.append("POLICY_PINS_INVALID")
    if expected_pins:
        for name, expected in expected_pins.items():
            if policy.get(name) != expected:
                reasons.append(f"POLICY_PIN_MISMATCH:{name}")
    metrics = policy.get("metrics")
    if not isinstance(metrics, list):
        metrics = []
    names = [x.get("metric") for x in metrics if isinstance(x, dict)]
    if any(not is_supported_metric(name) for name in names):
        reasons.append("UNSUPPORTED_METRIC")
    if (len(names) != len(metrics) or any(not isinstance(n, str) for n in names)
            or len(set(names)) != len(names)
            or not REQUIRED_METRICS.issubset(names)
            or not any(isinstance(n, str) and n.startswith("pair_precision.") for n in names)):
        reasons.append("FULL_REQUIRED_METRIC_SPECS_REQUIRED")
    for spec in metrics:
        try:
            if (not isinstance(spec, dict) or not spec.get("unit")
                    or not spec.get("eligibility") or not spec.get("predicate")
                    or not spec.get("strata") or not spec.get("threshold_source")
                    or type(spec.get("minimum_units")) is not int
                    or spec["minimum_units"] <= 0
                    or type(spec.get("threshold")) not in (int, float)
                    or not math.isfinite(spec["threshold"])
                    or not 0 <= spec["threshold"] <= 1
                    or spec.get("direction") not in ("min", "max")):
                raise ValueError("invalid spec")
        except (ValueError, TypeError):
            reasons.append("METRIC_SPEC_INVALID")
    return {"status": "BLOCKED" if reasons else "POLICY_VALIDATED",
            "reasons": sorted(set(reasons))}


def _index(records: Sequence[UnitRecord]) -> dict[tuple[str, str, str], UnitRecord]:
    indexed = {}
    for record in records:
        key = (record.metric, record.item_id, record.unit_id)
        if key in indexed:
            raise ValueError(f"duplicate unit identity: {key}")
        indexed[key] = record
    return indexed


def compare_units(
    baseline: Sequence[UnitRecord], current: Sequence[UnitRecord],
    specs: Sequence[MetricSpec],
) -> RegressionDiff:
    old, new = _index(baseline), _index(current)
    regressions = {}
    for key, previous in old.items():
        predicted = new.get(key)
        if previous.passed and (predicted is None or not predicted.passed):
            regressions[key] = predicted or replace(previous, passed=False, detail="MISSING")
    tripwires = {spec.metric for spec in specs if spec.tripwire}
    for key, record in new.items():
        if (record.metric in tripwires and not record.passed
                and (key not in old or old[key].passed)):
            regressions[key] = record
    return RegressionDiff(tuple(regressions.values()))


def score_units(records: Sequence[UnitRecord], specs: Sequence[MetricSpec]) -> dict:
    _index(records)
    if not specs or len({spec.metric for spec in specs}) != len(specs):
        raise ValueError("required metric specifications missing or duplicated")
    declared_metrics = {spec.metric for spec in specs}
    if any(record.metric not in declared_metrics for record in records):
        raise ValueError("undeclared prediction metric")
    metrics = []
    for spec in specs:
        result = asdict(evaluate_metric(records, spec))
        result.pop("units")
        if result["status"] == "NOT_RUN":
            result["status"] = "NOT_MEASURED"
        metrics.append(result)
    statuses = {metric["status"] for metric in metrics}
    status = next((x for x in ("FAIL", "NOT_MEASURED", "UNDERPOWERED") if x in statuses),
                  "PASS(point)")
    return {"status": status, "metrics": metrics}
