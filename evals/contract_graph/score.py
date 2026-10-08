"""Score predicted amendment edges against VBHN auto-gold, per op, with Wilson 95% intervals.

Gold and predictions are paired one-to-one inside each pair (document pair), never across:
step 1 on the exact key (src_address, target_address), step 2 on src_address alone in order
of appearance (gold by note_no, predictions in predictor order). Leftover predictions are
``unmatched_predictions`` (they lower precision), leftover gold are misses (they lower recall).
Gold with op OTHER is counted, never scored; a prediction paired with it is set aside too.
A prediction that lists several targets (``target_addresses``, "điểm d1, d2 …") is one slot
per listed target: it can pair with as many gold as it lists, and no more.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

GROUND_TRUTH_LABEL = "vbhn-note auto-gold (approved=false)"
BASE_OPS = ("SUBSTITUTION", "INSERTION", "REPEAL")
OP_ORDER = BASE_OPS + ("REJECTION", "SCOPE_LIMIT")
OTHER = "OTHER"
LEXICAL_NOTE = (
    "`op_lexical_agreement` = đồng thuận từ vựng: gold lấy op từ động từ của chú thích VBHN và predictor "
    "map động từ của câu thao tác theo cùng quy ước, nên chỉ số này đo việc tìm đúng câu thao tác + động từ "
    "khớp, không đo phân loại đúng nghĩa (RT-09)."
)
_TALLY_KEYS = ("n_gold", "n_pred", "src_found", "op_agree", "target_correct")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def rate(passed: int, denominator: int) -> dict:
    lo, hi = wilson(passed, denominator)
    return {
        "passed": passed,
        "denominator": denominator,
        "rate": round(passed / denominator, 4) if denominator else None,
        "wilson95": [round(lo, 4), round(hi, 4)],
    }


def match(
    gold: list[dict], preds: list[dict]
) -> tuple[list[tuple[dict, dict]], list[dict], list[dict]]:
    """One pair's gold vs predictions → (pairs, missed gold, unmatched predictions)."""

    gold = sorted(gold, key=lambda g: g["note_no"])
    used = [False] * len(preds)
    paired: dict[int, int] = {}

    def take(gi: int, same) -> None:
        for pi, pred in enumerate(preds):
            if not used[pi] and same(gold[gi], pred):
                used[pi] = True
                paired[gi] = pi
                return

    for gi, g in enumerate(gold):
        if g.get("target_address"):
            take(
                gi,
                lambda g, p: (
                    p.get("src_address") == g["src_address"]
                    and p.get("target_address") == g["target_address"]
                ),
            )
    for gi in range(len(gold)):
        if gi not in paired:
            take(gi, lambda g, p: p.get("src_address") == g["src_address"])
    pairs = [(gold[gi], preds[paired[gi]]) for gi in sorted(paired)]
    missed = [g for gi, g in enumerate(gold) if gi not in paired]
    unmatched = [p for pi, p in enumerate(preds) if not used[pi]]
    return pairs, missed, unmatched


def expand_targets(preds: list[dict]) -> list[dict]:
    """One scoring slot per listed target: a prediction for "điểm d1, d2 …" may carry
    ``target_addresses`` and then pairs with (and is counted for precision) once per target,
    never more. Without the list it is a single slot on ``target_address``."""

    slots = []
    for pred in preds:
        targets = pred.get("target_addresses") or [pred.get("target_address")]
        slots.extend({**pred, "target_address": target} for target in targets)
    return slots


def score(gold: list[dict], preds: list[dict]) -> dict:
    pair_ids = sorted({g["pair_id"] for g in gold} | {p["pair_id"] for p in preds})
    report: dict = {
        "ground_truth": GROUND_TRUTH_LABEL,
        "by_pair": {},
        "unmatched_predictions": [],
        "missed_gold": [],
        "target_mismatches": [],
    }
    totals: dict = {}
    for pid in pair_ids:
        pair_gold = [g for g in gold if g["pair_id"] == pid]
        pair_preds = [p for p in preds if p["pair_id"] == pid]
        slots = expand_targets(pair_preds)
        pairs, missed, unmatched = match(pair_gold, slots)
        tallies = _tally(pair_gold, slots, pairs, unmatched)
        tallies["marker"] = _marker_tally(pair_preds)
        report["by_pair"][pid] = _block(tallies)
        _accumulate(totals, tallies)
        report["unmatched_predictions"].extend(_pred_row(pid, p) for p in unmatched)
        report["missed_gold"].extend(_gold_row(pid, g) for g in missed if g["op"] != OTHER)
        report["target_mismatches"].extend(
            {
                "pair_id": pid,
                "note_no": g["note_no"],
                "src_address": g["src_address"],
                "op": g["op"],
                "gold_target_address": g.get("target_address"),
                "pred_target_address": p.get("target_address"),
            }
            for g, p in pairs
            if g["op"] != OTHER and not _target_ok(g, p)
        )
    report["overall"] = _block(totals or _tally([], [], [], []))
    return report


def render_markdown(report: dict) -> str:
    title = report.get("predictor", "predictions")
    lines = [
        f"# Contract graph eval — {title}",
        "",
        f"- Ground truth: `{report['ground_truth']}` (chưa duyệt; không phải độ chính xác nghiệp vụ)",
    ]
    if "dataset" in report:
        ds = report["dataset"]
        lines.append(
            f"- Dataset: {ds.get('pairs')} cặp, manifest sha256 `{ds.get('manifest_sha256')}`"
        )
    lines += ["", "## Tổng", ""]
    lines += _op_table(report["overall"])
    lines += ["", f"> {LEXICAL_NOTE}", ""]
    overall = report["overall"]
    lines.append(
        f"- gold OTHER (đếm, không chấm): {overall['n_gold_other']}; pred ghép vào OTHER: {overall['n_pred_on_other']}"
    )
    lines.append(f"- marker_hit: {_fmt(overall['marker_hit'])}")
    lines += ["", "## Theo cặp", ""]
    header = (
        "pair",
        "n_gold",
        "src_found",
        "op_lexical_agreement",
        "op_precision",
        "target_accuracy",
    )
    lines += [_row(header), _row(("---",) * len(header))]
    for pid, block in report["by_pair"].items():
        a = block["all"]
        lines.append(
            _row(
                (
                    pid,
                    str(a["n_gold"]),
                    _fmt(a["src_found"]),
                    _fmt(a["op_lexical_agreement"]),
                    _fmt(a["op_precision"]),
                    _fmt(a["target_accuracy"]),
                )
            )
        )
    lines += ["", f"## Sai đích ({len(report['target_mismatches'])})", ""]
    lines += [
        f"- {m['pair_id']} [{m['note_no']}] {m['op']} {m['src_address']}: gold `{m['gold_target_address']}` "
        f"≠ pred `{m['pred_target_address']}`"
        for m in report["target_mismatches"]
    ]
    lines += ["", f"## Pred không ghép được gold ({len(report['unmatched_predictions'])})", ""]
    lines += [
        f"- {u['pair_id']} {u['op']} {u['src_address']} → `{u['target_address']}`"
        for u in report["unmatched_predictions"]
    ]
    lines += ["", f"## Gold bị bỏ sót ({len(report['missed_gold'])})", ""]
    lines += [
        f"- {m['pair_id']} [{m['note_no']}] {m['op']} {m['src_address']} → `{m['target_address']}`"
        for m in report["missed_gold"]
    ]
    return "\n".join(lines) + "\n"


def _tally(
    gold: list[dict], preds: list[dict], pairs: list[tuple[dict, dict]], unmatched: list[dict]
) -> dict:
    on_other = [p for g, p in pairs if g["op"] == OTHER]
    on_other_ids = {id(p) for p in on_other}
    # a prediction without a scorable op ("OTHER", missing) still counts as unmatched, never per op
    scored_preds = [
        p for p in preds if id(p) not in on_other_ids and p.get("op") not in (None, OTHER)
    ]
    ops = _ops(g["op"] for g in gold) | _ops(p["op"] for p in scored_preds)
    by_op = {op: dict.fromkeys(_TALLY_KEYS, 0) for op in _ordered(ops)}
    for g in gold:
        if g["op"] != OTHER:
            by_op[g["op"]]["n_gold"] += 1
    for p in scored_preds:
        by_op[p["op"]]["n_pred"] += 1
    for g, p in pairs:
        if g["op"] == OTHER:
            continue
        t = by_op[g["op"]]
        t["src_found"] += 1
        t["target_correct"] += _target_ok(g, p)
        if p.get("op") == g["op"]:
            t["op_agree"] += 1
    return {
        "by_op": by_op,
        "n_gold_other": sum(1 for g in gold if g["op"] == OTHER),
        "n_pred_on_other": len(on_other),
        "marker": _marker_tally(preds),
    }


def _marker_tally(preds: list[dict]) -> list[int]:
    with_marker = [p for p in preds if "marker_hit" in p]
    return [sum(1 for p in with_marker if p["marker_hit"]), len(with_marker)]


def _accumulate(totals: dict, tallies: dict) -> None:
    if not totals:
        totals.update({"by_op": {}, "n_gold_other": 0, "n_pred_on_other": 0, "marker": [0, 0]})
    for op, t in tallies["by_op"].items():
        acc = totals["by_op"].setdefault(op, dict.fromkeys(_TALLY_KEYS, 0))
        for key in _TALLY_KEYS:
            acc[key] += t[key]
    totals["by_op"] = {op: totals["by_op"][op] for op in _ordered(set(totals["by_op"]))}
    totals["n_gold_other"] += tallies["n_gold_other"]
    totals["n_pred_on_other"] += tallies["n_pred_on_other"]
    totals["marker"] = [
        totals["marker"][0] + tallies["marker"][0],
        totals["marker"][1] + tallies["marker"][1],
    ]


def _block(tallies: dict) -> dict:
    all_t = dict.fromkeys(_TALLY_KEYS, 0)
    for t in tallies["by_op"].values():
        for key in _TALLY_KEYS:
            all_t[key] += t[key]
    return {
        "by_op": {op: _metrics(t) for op, t in tallies["by_op"].items()},
        "all": _metrics(all_t),
        "n_gold_other": tallies["n_gold_other"],
        "n_pred_on_other": tallies["n_pred_on_other"],
        "marker_hit": rate(*tallies["marker"]),
    }


def _metrics(t: dict) -> dict:
    return {
        "n_gold": t["n_gold"],
        "n_pred": t["n_pred"],
        "src_found": rate(t["src_found"], t["n_gold"]),
        "op_lexical_agreement": rate(t["op_agree"], t["n_gold"]),
        "op_precision": rate(t["op_agree"], t["n_pred"]),
        "target_accuracy": rate(t["target_correct"], t["src_found"]),
    }


def _ops(values: Iterable[str]) -> set[str]:
    return {v for v in values if v != OTHER}


def _ordered(ops: set[str]) -> list[str]:
    known = [op for op in OP_ORDER if op in ops or op in BASE_OPS]
    return known + sorted(ops - set(OP_ORDER))


def _target_ok(g: dict, p: dict) -> bool:
    return bool(g.get("target_address")) and p.get("target_address") == g["target_address"]


def _gold_row(pid: str, g: dict) -> dict:
    return {
        "pair_id": pid,
        "note_no": g["note_no"],
        "src_address": g["src_address"],
        "op": g["op"],
        "target_address": g.get("target_address"),
    }


def _pred_row(pid: str, p: dict) -> dict:
    return {
        "pair_id": pid,
        "src_address": p.get("src_address"),
        "op": p.get("op"),
        "target_address": p.get("target_address"),
    }


def _op_table(block: dict) -> list[str]:
    header = (
        "op",
        "n_gold",
        "n_pred",
        "src_found",
        "op_lexical_agreement",
        "op_precision",
        "target_accuracy",
    )
    out = [_row(header), _row(("---",) * len(header))]
    rows = list(block["by_op"].items()) + [("ALL", block["all"])]
    for op, m in rows:
        out.append(
            _row(
                (
                    op,
                    str(m["n_gold"]),
                    str(m["n_pred"]),
                    _fmt(m["src_found"]),
                    _fmt(m["op_lexical_agreement"]),
                    _fmt(m["op_precision"]),
                    _fmt(m["target_accuracy"]),
                )
            )
        )
    return out


def _fmt(r: dict) -> str:
    if not r["denominator"]:
        return "0/0 (n/a)"
    lo, hi = r["wilson95"]
    return f"{r['passed']}/{r['denominator']} ({r['rate']:.3f}; CI95 {lo:.3f}–{hi:.3f})"


def _row(cells: tuple[str, ...]) -> str:
    return "| " + " | ".join(cells) + " |"
