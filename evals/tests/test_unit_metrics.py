from __future__ import annotations

import pytest

from evals.unit_metrics import (
    MetricSpec,
    UnitRecord,
    cluster_bootstrap_ci,
    diff_regressions,
    evaluate_metric,
    exit_code,
    wilson_interval,
    write_baseline,
)


@pytest.mark.parametrize(
    ("passed", "total", "expected"),
    [
        (60, 60, (0.940, 1.000)),
        (57, 60, (0.863, 0.983)),
        (21, 24, (0.690, 0.957)),
    ],
)
def test_wilson_known_values(passed: int, total: int, expected: tuple[float, float]) -> None:
    lower, upper = wilson_interval(passed, total)
    assert lower == pytest.approx(expected[0], abs=0.001)
    assert upper == pytest.approx(expected[1], abs=0.001)


def test_cluster_bootstrap_wider_than_wilson_when_clustered() -> None:
    records = [
        UnitRecord("accuracy", f"q-{cluster}-{unit}", "answer", not (cluster == 0 and unit < 8), f"c{cluster}")
        for cluster in range(8)
        for unit in range(8)
    ]
    first = cluster_bootstrap_ci(records, B=1000, seed=17)
    second = cluster_bootstrap_ci(records, B=1000, seed=17)
    wilson_lower, _ = wilson_interval(sum(record.passed for record in records), len(records))
    assert first == second
    assert first[0] < wilson_lower


def test_floor_is_never_pass() -> None:
    spec = MetricSpec("accuracy", threshold=0.0, unit_floor=60)
    verdict = evaluate_metric([UnitRecord("accuracy", "q1", "u1", True, "c1")], spec)
    assert verdict.status == "UNDERPOWERED"
    assert verdict.status != "PASS"


def test_empty_metric_is_not_run_without_invented_counts_or_intervals() -> None:
    verdict = evaluate_metric([], MetricSpec("accuracy", threshold=0.9, unit_floor=60))
    assert verdict.status == "NOT_RUN"
    assert (verdict.passed, verdict.failed, verdict.n) == (0, 0, 0)
    assert verdict.point is None
    assert verdict.wilson_lower is None
    assert verdict.wilson_upper is None
    assert verdict.cluster_lower is None
    assert verdict.cluster_upper is None
    assert verdict.zero_failure_upper_bound is None


def test_blocking_zero_failure() -> None:
    spec = MetricSpec("fabrication", threshold=1.0, unit_floor=1, max_failures=0)
    verdict = evaluate_metric([UnitRecord("fabrication", "q1", "u1", False, "c1")], spec)
    assert verdict.status == "FAIL"
    assert verdict.passed == 0


def test_threshold_boundary_reports_lower_bounds() -> None:
    records = [UnitRecord("accuracy", f"q{i}", "answer", i >= 3, f"c{i % 8}") for i in range(60)]
    verdict = evaluate_metric(records, MetricSpec("accuracy", threshold=0.95, unit_floor=60))
    assert verdict.status == "PASS(point)"
    assert verdict.wilson_lower == pytest.approx(0.863, abs=0.001)
    assert verdict.cluster_lower is not None
    assert verdict.zero_failure_upper_bound is None


def test_zero_failure_upper_bound_is_reported_when_tripwire_is_clear() -> None:
    records = [UnitRecord("fabrication", f"q{i}", "value", True, f"c{i % 8}") for i in range(60)]
    verdict = evaluate_metric(records, MetricSpec("fabrication", threshold=1.0, unit_floor=60, max_failures=0))
    assert verdict.zero_failure_upper_bound == pytest.approx(0.0487, abs=0.001)


def test_regression_detection_and_version_drift() -> None:
    spec = MetricSpec("accuracy", threshold=0.9, unit_floor=1)
    baseline = [UnitRecord("accuracy", "q1", "answer", True, "c1")]
    current = [UnitRecord("accuracy", "q1", "answer", False, "c1")]
    result = diff_regressions(baseline, current, [spec], golden_version="g1", scorer_version="s1")
    assert result.regressions
    with pytest.raises(ValueError, match="version"):
        diff_regressions(baseline, current, [spec], golden_version="g1", scorer_version="s2", baseline_golden_version="g0")


def test_tripwire_new_item_fail_is_regression() -> None:
    spec = MetricSpec("fabrication", threshold=1.0, unit_floor=1, max_failures=0)
    baseline = [UnitRecord("fabrication", "old", "q#val#1", True, "c1")]
    current = [
        UnitRecord("fabrication", "old", "q#val#1", True, "c1"),
        UnitRecord("fabrication", "new", "q#val#2", False, "c2"),
    ]
    result = diff_regressions(baseline, current, [spec])
    assert [(record.item_id, record.unit_id) for record in result.regressions] == [("new", "q#val#2")]


def test_tripwire_new_unit_for_previously_failing_item_is_regression() -> None:
    spec = MetricSpec("fabrication", threshold=1.0, unit_floor=1, max_failures=0)
    baseline = [UnitRecord("fabrication", "q", "q#val#1", False, "c1")]
    current = baseline + [UnitRecord("fabrication", "q", "q#val#2", False, "c1")]
    result = diff_regressions(baseline, current, [spec])
    assert [(record.item_id, record.unit_id) for record in result.regressions] == [("q", "q#val#2")]


@pytest.mark.parametrize(("status", "expected"), [("PASS", 0), ("PASS(point)", 0), ("FAIL", 1), ("BLOCKED", 2), ("UNDERPOWERED", 3), ("NOT_RUN", 3)])
def test_exit_code_matrix(status: str, expected: int) -> None:
    assert exit_code(status) == expected


def test_write_baseline_refuses_in_ci_dirty_draft_or_unapproved(tmp_path, monkeypatch) -> None:
    baseline = {"schema_version": "ai2.unit-baseline.v1"}
    target = tmp_path / "baseline.json"
    monkeypatch.setenv("CI", "true")
    with pytest.raises(PermissionError, match="CI"):
        write_baseline(target, baseline, dirty=False, draft=False, card_approved=True)
    monkeypatch.delenv("CI")
    with pytest.raises(PermissionError, match="dirty"):
        write_baseline(target, baseline, dirty=True, draft=False, card_approved=True)
    with pytest.raises(PermissionError, match="draft"):
        write_baseline(target, baseline, dirty=False, draft=True, card_approved=True)
    with pytest.raises(PermissionError, match="approved"):
        write_baseline(target, baseline, dirty=False, draft=False, card_approved=False)
    assert not target.exists()
