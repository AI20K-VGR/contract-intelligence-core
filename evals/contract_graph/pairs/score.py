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

from collections.abc import Callable, Iterable, Mapping

from evals.contract_graph.pairs.labeler import DIRECTED, LABELS, UNRELATED
from evals.contract_graph.score import rate

SCORED = tuple(label for label in LABELS if label != UNRELATED)
ESTIMATOR = "horvitz-thompson"


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
        if g.get("gold_label") is not None and (g.get("approved") or not approved_only)
    }
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
                            if p in gold_by and gold_by[p]["gold_label"] != "DUPLICATE"),
            "unreviewed": sum(1 for p in duplicates if p not in gold_by),
        },
    }


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
