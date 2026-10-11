"""Score pair-relation predictions against reviewed gold (P2/P3/P5), per label, stratum and doc.

Pairs are matched on ``pair_id`` (already order-free: ``sha256(doc_id|a|b)`` with a before b).
Per label ≠ UNRELATED:

- ``precision_conservative`` — correct / every prediction of the label. A prediction on a pair
  without reviewed gold counts as wrong (RT-01); this is the number a gate may use.
- ``precision_observed`` — correct / predictions that have reviewed gold.
- ``recall_observed`` — correct / reviewed gold positives of the label.
- ``precision_weighted`` / ``recall_weighted`` — Horvitz–Thompson ratio with weight ``1/pi`` of
  each reviewed pair of the HG-1 selection; reported only, no interval, never a gate.
- ``direction_accuracy`` — among label-correct pairs, same ``general``/``referrer`` side.

Every rate is ``score.rate`` (k/n + Wilson 95%). Blocks also split ``denominator`` (predictions),
``covered`` (with gold) and ``passed`` (correct).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping

from evals.contract_graph.pairs.labeler import DIRECTED, LABELS, UNRELATED
from evals.contract_graph.score import rate

SCORED = tuple(label for label in LABELS if label != UNRELATED)
ESTIMATOR = "horvitz-thompson"
QUALITY_SCHEMA = "contract-graph-quality-score/1"
FRAME_VERSION = "contract-graph-quality-frame/1"
QUALITY_MIN_N = 60
QUALITY_MIN_WILSON = 0.85


def score_relations(
    gold: Iterable[Mapping],
    preds: Iterable[Mapping],
    *,
    approved_only: bool,
    selection: Iterable[Mapping] | None = None,
) -> dict:
    gold = list(gold)
    preds_by: dict[str, Mapping] = {}
    for pred in preds:
        if pred["pair_id"] in preds_by:
            raise ValueError(f"two predictions for pair {pred['pair_id']}")
        preds_by[pred["pair_id"]] = pred
    gold_by = {
        g["pair_id"]: g
        for g in gold
        if g.get("gold_label") is not None and (g.get("approved") is True or not approved_only)
    }
    # A reviewed rejection is still human evidence that a predicted relation is
    # false. Keep it out of recall gold, but include it in the observed
    # false-duplicate veto. Unreviewed GPT suggestions remain separate.
    reviewed_by = {g["pair_id"]: g for g in gold if g.get("source") == "user-review"}
    sel = {s["pair_id"]: s for s in selection} if selection is not None else None
    meta: dict[str, dict] = {}
    for source in (preds_by.values(), gold, (sel or {}).values()):
        for record in source:
            entry = meta.setdefault(record["pair_id"], {})
            for key in ("stratum", "doc_id"):
                if record.get(key) is not None:
                    entry[key] = record[key]
    universe = sorted(set(preds_by) | set(gold_by))

    def blocks(keep: Callable[[str], bool]) -> dict:
        pids = [p for p in universe if keep(p)]
        return {label: _block(label, pids, preds_by, gold_by, sel) for label in SCORED}

    def split(key: str) -> dict:
        values = sorted({meta[p][key] for p in universe if key in meta.get(p, {})})
        return {v: blocks(lambda p, v=v: meta.get(p, {}).get(key) == v) for v in values}

    duplicates = [p for p, pred in preds_by.items() if pred.get("label") == "DUPLICATE"]
    sources = sorted({str(g.get("source")) for g in gold_by.values()})
    return {
        "ground_truth": {
            "sources": sources,
            "approved_only": approved_only,
            "label": "reviewed gold (approved=true)" if approved_only
            else "reviewed gold incl. unapproved labels",
        },
        "estimator": ESTIMATOR if sel is not None else None,
        "n_pred": len(preds_by),
        "n_gold": len(gold_by),
        "by_label": blocks(lambda p: True),
        "by_stratum": split("stratum"),
        "by_doc": split("doc_id"),
        "false_duplicate": {
            "observed": sum(1 for p in duplicates
                            if p in reviewed_by and reviewed_by[p].get("gold_label") != "DUPLICATE"),
            "unreviewed": sum(1 for p in duplicates if p not in reviewed_by),
        },
    }


def _frame_ids(frame: Iterable[str], name: str) -> set[str]:
    if isinstance(frame, (str, bytes, Mapping)):
        raise ValueError(f"{name} must be an iterable of unique pair IDs")
    try:
        values = list(frame)
    except TypeError as exc:
        raise ValueError(f"{name} must be an iterable of unique pair IDs") from exc
    if (not values or any(not isinstance(value, str) or not value for value in values)
            or len(values) != len(set(values))):
        raise ValueError(f"{name} must contain unique non-empty string pair IDs")
    return set(values)


def score_quality(
    gold: Iterable[Mapping],
    preds: Iterable[Mapping],
    *,
    recall_frame: Iterable[str],
    precision_frame: Iterable[str],
) -> dict:
    """Score exact-label quality against independent, immutable recall/precision frames.

    Every gold row must be an explicit human decision. Recall includes all approved
    positives in ``recall_frame`` whether or not a prediction exists. Precision counts
    every prediction in the candidate union; an unreviewed prediction is incorrect.
    """
    recall_ids = _frame_ids(recall_frame, "recall_frame")
    precision_ids = _frame_ids(precision_frame, "precision_frame")
    gold_by: dict[str, Mapping] = {}
    for row in gold:
        if not isinstance(row, Mapping):
            raise ValueError("gold rows must be objects")
        pair_id = row.get("pair_id")
        label = row.get("gold_label")
        direction = row.get("gold_direction")
        if (not isinstance(pair_id, str) or not pair_id or pair_id in gold_by
                or type(row.get("approved")) is not bool or row.get("approved") is not True
                or row.get("source") != "user-review"):
            raise ValueError("gold rows must be unique, explicitly approved human decisions")
        if label is not None and label not in LABELS:
            raise ValueError("gold label is unknown")
        if label in DIRECTED:
            if direction not in {"A", "B"}:
                raise ValueError("reviewed directed gold requires direction A or B")
        elif direction is not None:
            raise ValueError("non-directed gold must not carry a direction")
        gold_by[pair_id] = row
    if not recall_ids <= gold_by.keys():
        raise ValueError("every recall frame member must have approved reviewed gold")

    pred_by: dict[str, Mapping] = {}
    for row in preds:
        if not isinstance(row, Mapping):
            raise ValueError("prediction rows must be objects")
        pair_id, label, direction = row.get("pair_id"), row.get("label"), row.get("direction")
        if not isinstance(pair_id, str) or not pair_id or pair_id in pred_by:
            raise ValueError("prediction pair IDs must be unique non-empty strings")
        if pair_id not in precision_ids:
            raise ValueError("prediction is outside the locked precision frame")
        if label not in LABELS:
            raise ValueError("prediction label is unknown")
        if direction is not None and direction not in {"A", "B"}:
            raise ValueError("prediction direction is unknown")
        pred_by[pair_id] = row

    def label_correct(pid: str, label: str) -> bool:
        row = gold_by.get(pid)
        return bool(row and row.get("gold_label") == label)

    def exact_correct(pid: str, label: str) -> bool:
        if not label_correct(pid, label):
            return False
        if label in DIRECTED:
            return pred_by[pid].get("direction") in {"A", "B"} and pred_by[pid].get("direction") == gold_by[pid].get("gold_direction")
        return True

    by_label = {}
    for label in SCORED:
        predicted = [pid for pid, row in pred_by.items() if row.get("label") == label]
        positive_ids = [pid for pid in recall_ids if gold_by[pid].get("gold_label") == label]
        label_hits = sum(label_correct(pid, label) for pid in predicted)
        exact_hits = sum(exact_correct(pid, label) for pid in predicted)
        recall_hits = sum(pid in pred_by and exact_correct(pid, label) for pid in positive_ids)
        exact_direction_precision = (rate(exact_hits, len(predicted)) if label in DIRECTED else None)
        by_label[label] = {
            "precision_exact": rate(label_hits, len(predicted)),
            "precision_exact_direction": exact_direction_precision,
            "recall_exact": rate(recall_hits, len(positive_ids)),
            "recall_exact_label": rate(sum(pid in pred_by and label_correct(pid, label)
                                             for pid in positive_ids), len(positive_ids)),
        }

    duplicate_ids = [pid for pid, row in pred_by.items() if row.get("label") == "DUPLICATE"]
    false_duplicate = {
        "observed": sum(pid in gold_by and gold_by[pid].get("gold_label") != "DUPLICATE"
                         for pid in duplicate_ids),
        "unreviewed": sum(pid not in gold_by for pid in duplicate_ids),
    }
    return {"schema": QUALITY_SCHEMA, "frame_version": FRAME_VERSION,
            "recall_frame": {"n": len(recall_ids), "pair_ids": sorted(recall_ids)},
            "precision_frame": {"n": len(precision_ids), "pair_ids": sorted(precision_ids)},
            "n_gold": len(gold_by), "n_predictions": len(pred_by),
            "by_label": by_label, "false_duplicate": false_duplicate}


def quality_gate(report: Mapping, *, minimum_n: int = QUALITY_MIN_N,
                 wilson_floor: float = QUALITY_MIN_WILSON,
                 cluster_intervals: Mapping | None = None) -> dict:
    """Recompute a fail-closed readiness decision from raw scored counts."""
    if (not isinstance(report, Mapping) or report.get("schema") != QUALITY_SCHEMA
            or report.get("frame_version") != FRAME_VERSION
            or type(minimum_n) is not int or minimum_n <= 0
            or type(wilson_floor) not in (int, float) or isinstance(wilson_floor, bool)
            or not math.isfinite(float(wilson_floor)) or not 0 <= wilson_floor <= 1):
        return {"schema": "contract-graph-quality-gate/1", "status": "BLOCKED",
                "reason_codes": ["invalid_quality_schema_or_threshold"]}
    by_label = report.get("by_label")
    if not isinstance(by_label, Mapping):
        return {"schema": "contract-graph-quality-gate/1", "status": "BLOCKED",
                "reason_codes": ["missing_label_metrics"]}
    reasons = []
    required = {label: {} for label in SCORED}
    for label in SCORED:
        block = by_label.get(label)
        if not isinstance(block, Mapping):
            reasons.append(f"missing_{label.lower()}_metrics")
            continue
        metrics = ["precision_exact", "recall_exact"] + (["precision_exact_direction"] if label in DIRECTED else [])
        for metric_name in metrics:
            metric = block.get(metric_name)
            if not isinstance(metric, Mapping):
                reasons.append(f"missing_{label.lower()}_{metric_name}")
                continue
            passed, denominator, interval = metric.get("passed"), metric.get("denominator"), metric.get("wilson95")
            if (type(passed) is not int or type(denominator) is not int or denominator < 0
                    or passed < 0 or passed > denominator or denominator < minimum_n
                    or not isinstance(interval, list) or len(interval) != 2
                    or any(type(v) not in (int, float) or isinstance(v, bool)
                           or not math.isfinite(float(v)) or not 0 <= v <= 1 for v in interval)):
                reasons.append(f"invalid_or_insufficient_{label.lower()}_{metric_name}")
                continue
            expected = rate(passed, denominator)["wilson95"]
            if interval != expected:
                reasons.append(f"forged_{label.lower()}_{metric_name}_interval")
                continue
            required[label][metric_name] = {"n": denominator, "lower": interval[0]}
            if interval[0] < wilson_floor:
                reasons.append(f"below_floor_{label.lower()}_{metric_name}")
        cluster = (cluster_intervals.get(label, {}).get("precision_conservative")
                   if isinstance(cluster_intervals, Mapping) else None)
        cluster_lower = cluster.get("lower") if isinstance(cluster, Mapping) else None
        if (type(cluster_lower) not in (int, float) or isinstance(cluster_lower, bool)
                or not math.isfinite(float(cluster_lower)) or not 0 <= cluster_lower <= 1):
            reasons.append(f"missing_{label.lower()}_cluster_precision_interval")
        elif cluster_lower < wilson_floor:
            reasons.append(f"below_floor_{label.lower()}_cluster_precision")
    false_duplicate = report.get("false_duplicate")
    if (not isinstance(false_duplicate, Mapping)
            or any(type(false_duplicate.get(key)) is not int for key in ("observed", "unreviewed"))
            or false_duplicate.get("observed") != 0 or false_duplicate.get("unreviewed") != 0):
        reasons.append("false_duplicate_safety_veto")
    return {"schema": "contract-graph-quality-gate/1",
            "status": "PASS" if not reasons else "BLOCKED",
            "reason_codes": sorted(set(reasons)), "required": required,
            "minimum_n": minimum_n, "wilson_floor": wilson_floor}


def _block(
    label: str,
    pids: list[str],
    preds_by: Mapping[str, Mapping],
    gold_by: Mapping[str, Mapping],
    sel: Mapping[str, Mapping] | None,
) -> dict:
    predicted = [p for p in pids if p in preds_by and preds_by[p].get("label") == label]
    covered = [p for p in predicted if p in gold_by]
    correct = [p for p in covered if gold_by[p]["gold_label"] == label]
    positives = [p for p in pids if p in gold_by and gold_by[p]["gold_label"] == label]
    hits = set(correct)
    block = {
        "denominator": len(predicted),
        "covered": len(covered),
        "passed": len(correct),
        "precision_conservative": rate(len(correct), len(predicted)),
        "precision_observed": rate(len(correct), len(covered)),
        "recall_observed": rate(len(correct), len(positives)),
        "direction_accuracy": None,
        "precision_weighted": None,
        "recall_weighted": None,
    }
    if label in DIRECTED:
        same = sum(
            1 for p in correct
            if (preds_by[p].get("direction") or None) == (gold_by[p].get("gold_direction") or None)
        )
        block["direction_accuracy"] = rate(same, len(correct))
    if sel is not None:
        block["precision_weighted"] = _ht([p for p in covered if p in sel], hits, sel)
        block["recall_weighted"] = _ht([p for p in positives if p in sel], hits, sel)
    return block


def _ht(pids: list[str], hits: set[str], sel: Mapping[str, Mapping]) -> float | None:
    total = sum(1 / sel[p]["pi"] for p in pids)
    if not total:
        return None
    return round(sum(1 / sel[p]["pi"] for p in pids if p in hits) / total, 4)


def render_markdown(report: dict, title: str = "pair relations") -> str:
    """Numbers, labels, strata and ``doc_id`` only — never clause text or spans."""

    gt = report["ground_truth"]
    lines = [
        f"# Contract graph luồng 2 — {title}",
        "",
        f"- Ground truth: {gt['label']} — nguồn {', '.join(gt['sources']) or '—'}",
        f"- Dự đoán: {report['n_pred']}; gold: {report['n_gold']}",
        "- `precision_conservative`: dự đoán trên cặp chưa có gold duyệt tính là SAI (RT-01).",
    ]
    if report["estimator"]:
        lines.append(
            f"- Ước lượng có trọng số: `{report['estimator']}` (1/π), chỉ báo, không khoảng tin cậy."
        )
    fd = report["false_duplicate"]
    lines += [f"- false DUPLICATE: {fd['observed']} (chưa duyệt: {fd['unreviewed']})", "",
              "## Theo nhãn", ""]
    lines += _table(report["by_label"])
    for key, heading in (("by_stratum", "Theo tầng"), ("by_doc", "Theo văn bản")):
        lines += ["", f"## {heading}", ""]
        for name, blocks in report[key].items():
            lines += [f"### {name}", "", *_table(blocks), ""]
    return "\n".join(lines).rstrip() + "\n"


def _table(blocks: Mapping[str, dict]) -> list[str]:
    header = ("label", "denominator", "covered", "passed", "precision_conservative",
              "precision_observed", "recall_observed", "direction_accuracy",
              "precision_weighted", "recall_weighted")
    out = ["| " + " | ".join(header) + " |", "|" + " --- |" * len(header)]
    for label, b in blocks.items():
        cells = (
            label, str(b["denominator"]), str(b["covered"]), str(b["passed"]),
            _fmt(b["precision_conservative"]), _fmt(b["precision_observed"]),
            _fmt(b["recall_observed"]), _fmt(b["direction_accuracy"]),
            _num(b["precision_weighted"]), _num(b["recall_weighted"]),
        )
        out.append("| " + " | ".join(cells) + " |")
    return out


def _fmt(r: dict | None) -> str:
    if r is None:
        return "—"
    if not r["denominator"]:
        return "0/0"
    lo, hi = r["wilson95"]
    return f"{r['passed']}/{r['denominator']} ({r['rate']:.3f}; Wilson95 {lo:.3f}–{hi:.3f})"


def _num(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"
