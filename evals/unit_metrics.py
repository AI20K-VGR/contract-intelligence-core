"""Deterministic unit-level metrics and baseline comparison primitives."""

from __future__ import annotations

import json
import math
import os
import random
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_Z_95 = 1.959963984540054
_ALPHA_95 = 0.05


@dataclass(frozen=True, slots=True)
class MetricSpec:
    metric: str
    threshold: float
    unit_floor: int = 60
    max_failures: int | None = None

    def __post_init__(self) -> None:
        if not self.metric.strip():
            raise ValueError("metric must not be empty")
        if not 0 <= self.threshold <= 1:
            raise ValueError("threshold must be within [0, 1]")
        if self.unit_floor < 0:
            raise ValueError("unit_floor must be non-negative")
        if self.max_failures is not None and self.max_failures < 0:
            raise ValueError("max_failures must be non-negative")

    @property
    def tripwire(self) -> bool:
        return self.max_failures == 0 or self.threshold == 1.0


@dataclass(frozen=True, slots=True)
class UnitRecord:
    metric: str
    item_id: str
    unit_id: str
    passed: bool
    cluster: str
    detail: str | None = None
    split: str = "golden"

    def __post_init__(self) -> None:
        for name in ("metric", "item_id", "unit_id", "cluster"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")
        if type(self.passed) is not bool:
            raise ValueError("passed must be boolean")


@dataclass(frozen=True, slots=True)
class MetricResult:
    metric: str
    status: str
    passed: int
    failed: int
    n: int
    point: float | None
    wilson_lower: float | None
    wilson_upper: float | None
    cluster_lower: float | None
    cluster_upper: float | None
    zero_failure_upper_bound: float | None
    units: tuple[UnitRecord, ...] = field(default_factory=tuple, repr=False)


@dataclass(frozen=True, slots=True)
class RegressionDiff:
    regressions: tuple[UnitRecord, ...]
    setup_errors: tuple[str, ...] = ()


def wilson_interval(successes: int, total: int, confidence: float = 0.95) -> tuple[float, float]:
    _validate_counts(successes, total)
    z = _z_value(confidence)
    if total == 0:
        return (0.0, 1.0)
    point = successes / total
    denominator = 1 + z * z / total
    center = (point + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(point * (1 - point) / total + z * z / (4 * total * total)) / denominator
    return (max(0.0, center - margin), min(1.0, center + margin))


def zero_failure_upper_bound(total: int, confidence: float = 0.95) -> float:
    if total < 0:
        raise ValueError("total must be non-negative")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be within (0, 1)")
    if total == 0:
        return 1.0
    return 1 - (1 - confidence) ** (1 / total)


def cluster_bootstrap_ci(
    records: Sequence[UnitRecord] | Sequence[Mapping[str, Any]],
    cluster_key: str = "contract_id",
    B: int = 2000,
    seed: int = 0,
    confidence: float = 0.95,
) -> tuple[float, float]:
    if B <= 0:
        raise ValueError("B must be positive")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be within (0, 1)")
    if not records:
        return (0.0, 1.0)
    grouped: dict[str, list[bool]] = {}
    for record in records:
        cluster = _record_value(record, cluster_key)
        if cluster is None and cluster_key in {"contract_id", "cluster"}:
            cluster = _record_value(record, "cluster")
        passed = _record_value(record, "passed")
        if cluster is None or type(passed) is not bool:
            raise ValueError("records require a cluster key and boolean passed field")
        grouped.setdefault(str(cluster), []).append(passed)
    clusters = list(grouped.values())
    if len(clusters) < 2:
        count = sum(sum(values) for values in clusters)
        total = sum(map(len, clusters))
        point = count / total if total else 0.0
        return (point, point)

    rng = random.Random(seed)
    sample_count = len(clusters)
    samples: list[float] = []
    for _ in range(B):
        sampled = [clusters[rng.randrange(sample_count)] for _ in range(sample_count)]
        denominator = sum(map(len, sampled))
        samples.append(sum(sum(values) for values in sampled) / denominator)
    tail = (1 - confidence) / 2
    return (_quantile(samples, tail), _quantile(samples, 1 - tail))


def evaluate_metric(records: Iterable[UnitRecord], spec: MetricSpec) -> MetricResult:
    selected = tuple(record for record in records if record.metric == spec.metric)
    keys = [(record.item_id, record.unit_id) for record in selected]
    if len(keys) != len(set(keys)):
        raise ValueError(f"duplicate metric unit: {spec.metric}")
    passed = sum(record.passed for record in selected)
    failed = len(selected) - passed
    total = len(selected)
    point = passed / total if total else None
    if total:
        wilson_lower, wilson_upper = wilson_interval(passed, total)
        cluster_lower, cluster_upper = cluster_bootstrap_ci(selected)
        upper_bound = zero_failure_upper_bound(total) if failed == 0 else None
    else:
        wilson_lower = wilson_upper = cluster_lower = cluster_upper = upper_bound = None

    if total == 0:
        status = "NOT_RUN"
    elif spec.max_failures is not None and failed > spec.max_failures:
        status = "FAIL"
    elif total < spec.unit_floor:
        status = "UNDERPOWERED"
    elif point is not None and point >= spec.threshold:
        status = "PASS(point)"
    else:
        status = "FAIL"
    return MetricResult(
        metric=spec.metric,
        status=status,
        passed=passed,
        failed=failed,
        n=total,
        point=point,
        wilson_lower=wilson_lower,
        wilson_upper=wilson_upper,
        cluster_lower=cluster_lower,
        cluster_upper=cluster_upper,
        zero_failure_upper_bound=upper_bound,
        units=selected,
    )


def diff_regressions(
    baseline: Sequence[UnitRecord],
    current: Sequence[UnitRecord],
    specs: Sequence[MetricSpec],
    *,
    golden_version: str | None = None,
    scorer_version: str | None = None,
    baseline_golden_version: str | None = None,
    baseline_scorer_version: str | None = None,
) -> RegressionDiff:
    if baseline_golden_version is not None and golden_version != baseline_golden_version:
        raise ValueError("golden version drift")
    if baseline_scorer_version is not None and scorer_version != baseline_scorer_version:
        raise ValueError("scorer version drift")
    spec_by_metric = {spec.metric: spec for spec in specs}
    baseline_by_metric = _group_records(baseline)
    current_by_metric = _group_records(current)
    regressions: list[UnitRecord] = []
    for metric, spec in spec_by_metric.items():
        old = baseline_by_metric.get(metric, ())
        new = current_by_metric.get(metric, ())
        if spec.tripwire:
            old_failures = {(item.item_id, item.unit_id) for item in old if not item.passed}
            regressions.extend(
                record for record in new
                if not record.passed and (record.item_id, record.unit_id) not in old_failures
            )
            continue
        old_items: dict[str, bool] = {}
        new_items: dict[str, bool] = {}
        for record in old:
            old_items[record.item_id] = old_items.get(record.item_id, False) or record.passed
        for record in new:
            new_items[record.item_id] = new_items.get(record.item_id, False) or record.passed
        regressed = {item_id for item_id, was_passed in old_items.items() if was_passed and new_items.get(item_id) is False}
        regressions.extend(record for record in new if record.item_id in regressed and not record.passed)
    return RegressionDiff(tuple(regressions))


def build_report(
    metrics: Sequence[MetricResult],
    *,
    records: Sequence[UnitRecord] | None = None,
    card_approved: bool = False,
    tau_provisional: float | None = None,
    diagnostic_buckets: Mapping[str, Sequence[UnitRecord]] | None = None,
) -> dict[str, Any]:
    all_records = list(records) if records is not None else [unit for metric in metrics for unit in metric.units]
    by_split: dict[str, dict[str, dict[str, int]]] = {}
    for record in all_records:
        split_counts = by_split.setdefault(record.metric, {}).setdefault(record.split, {"passed": 0, "failed": 0, "n": 0})
        split_counts["passed"] += int(record.passed)
        split_counts["failed"] += int(not record.passed)
        split_counts["n"] += 1
    return {
        "metrics": [{key: value for key, value in asdict(metric).items() if key != "units"} for metric in metrics],
        "by_split": by_split,
        "card_approved": card_approved,
        "tau_provisional": tau_provisional,
        "diagnostic_buckets": {
            name: {"n": len(bucket), "gates": False, "label": "rò rỉ, không gate"}
            for name, bucket in (diagnostic_buckets or {}).items()
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = ["# AI2 unit metrics", "", "| Metric | x/n | Status | Wilson 95% | Cluster 95% |", "|---|---:|---|---:|---:|"]
    for metric in report.get("metrics", []):
        lines.append(
            f"| {metric['metric']} | {metric['passed']}/{metric['n']} | {metric['status']} | "
            f"{_interval(metric['wilson_lower'], metric['wilson_upper'])} | "
            f"{_interval(metric['cluster_lower'], metric['cluster_upper'])} |"
        )
    if not report.get("card_approved", False):
        lines.extend(["", "Card chưa được duyệt; kết quả là draft."])
    return "\n".join(lines) + "\n"


def exit_code(status: str | Mapping[str, Any]) -> int:
    if isinstance(status, Mapping):
        statuses = [str(item.get("status", "NOT_RUN")) for item in status.get("metrics", [])]
        status = max(statuses, key=_severity, default="NOT_RUN")
    if status in {"PASS", "PASS(point)"}:
        return 0
    if status == "FAIL":
        return 1
    if status in {"BLOCKED", "SETUP_ERROR"}:
        return 2
    if status in {"UNDERPOWERED", "NOT_RUN", "UNVERIFIED"}:
        return 3
    raise ValueError(f"unknown metric status: {status}")


def load_baseline(path: str | Path | None = None, *, git_ref: str | None = None) -> dict[str, Any]:
    if (path is None) == (git_ref is None):
        raise ValueError("provide exactly one of path or git_ref")
    if git_ref is not None:
        if ":" not in git_ref:
            raise ValueError("git_ref must be '<ref>:<path>'")
        result = subprocess.run(["git", "show", git_ref], check=True, capture_output=True, text=True, encoding="utf-8")
        payload = result.stdout
    else:
        payload = Path(path).read_text(encoding="utf-8")
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise TypeError("baseline must be a JSON object")
    return value


def write_baseline(
    path: str | Path,
    baseline: Mapping[str, Any],
    *,
    dirty: bool,
    draft: bool,
    card_approved: bool,
) -> None:
    if "CI" in os.environ:
        raise PermissionError("baseline writes are disabled in CI")
    if dirty:
        raise PermissionError("baseline writes refuse a dirty working tree")
    if draft:
        raise PermissionError("draft results cannot write a baseline")
    if not card_approved:
        raise PermissionError("baseline writes require an approved card")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    try:
        temporary.write_text(json.dumps(baseline, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _group_records(records: Sequence[UnitRecord]) -> dict[str, tuple[UnitRecord, ...]]:
    grouped: dict[str, list[UnitRecord]] = {}
    for record in records:
        grouped.setdefault(record.metric, []).append(record)
    return {key: tuple(value) for key, value in grouped.items()}


def _record_value(record: UnitRecord | Mapping[str, Any], key: str) -> Any:
    if isinstance(record, Mapping):
        return record.get(key)
    if key == "contract_id" and hasattr(record, "cluster"):
        return record.cluster
    return getattr(record, key, None)


def _validate_counts(successes: int, total: int) -> None:
    if total < 0 or successes < 0 or successes > total:
        raise ValueError("counts require 0 <= successes <= total")


def _z_value(confidence: float) -> float:
    if not 0 < confidence < 1:
        raise ValueError("confidence must be within (0, 1)")
    if confidence == 0.95:
        return _Z_95
    from statistics import NormalDist

    return NormalDist().inv_cdf((1 + confidence) / 2)


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _severity(status: str) -> int:
    return {"PASS": 0, "PASS(point)": 0, "UNVERIFIED": 1, "UNDERPOWERED": 1, "NOT_RUN": 1, "FAIL": 2, "BLOCKED": 3, "SETUP_ERROR": 3}.get(status, 3)


def _display(value: Any) -> str:
    return "—" if value is None else f"{value:.3f}"


def _interval(lower: Any, upper: Any) -> str:
    if lower is None or upper is None:
        return "—"
    return f"[{lower:.3f}, {upper:.3f}]"
