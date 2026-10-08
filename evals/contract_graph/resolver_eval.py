"""P2 address-resolver eval: resolve each amending item's target in the VBHN structure tree.

  python -m evals.contract_graph.resolver_eval --data evals/contract_graph/data \
      --out evals/contract_graph/reports/p2-resolver [--tree-shape full|article-only|both]

Items and their heads come from the P1 baseline parser (detection is not what this measures).
Each target is parsed (``parse_addresses``; a sub-item inherits from its parent item through
``parse_parent_context`` + ``inherit``), resolved with ``StructureIndex.resolve`` against
``segment(vbhn.txt)`` (``full``) or its article-only collapse (``article-only``: the AI1 tree
shape, RT-05), and the sub-items of one parent go through ``disambiguate_by_order``. Gold and
predictions are paired with ``score.match`` (one-to-one, RT-13); a sub-item listing several
targets ("điểm d1, d2") is one slot per target.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from evals.contract_graph.baseline_predictor import _operative_article, parse
from evals.contract_graph.dataset import MANIFEST, load_gold, verify_manifest
from evals.contract_graph.score import GROUND_TRUTH_LABEL, OTHER, match, rate
from evals.contract_graph.segment import collapse_to_articles, segment

AI_SERVICE = Path(__file__).resolve().parents[2] / "ai-service"
DEFAULT_BASELINE = Path(__file__).resolve().parent / "reports" / "p1-baseline.json"
SHAPES = ("full", "article-only")
STATUSES = ("UNIQUE", "AMBIGUOUS", "NOT_FOUND")
METHODS = ("EXACT", "ANCESTOR", "SELF", "ORDER_INFERENCE")
LIMITATIONS = (
    "Cây đích là VBHN (đã chứa phần sửa đổi), không phải văn bản gốc: INSERTION được chấm bằng "
    "địa chỉ mới (canonical), không bằng node; anchor/container được kiểm trên cây VBHN.",
    "Câu thao tác + head lấy từ parser baseline P1; item không được baseline phát hiện là gold "
    "bị bỏ sót (missed_gold), không phải lỗi resolver.",
    "ORDER_INFERENCE dựa trên giả định [ASSUMED] mục con liệt kê theo thứ tự văn bản gốc; "
    "số đúng/sai của nhánh này báo riêng.",
    "Gold tự trích từ chú thích VBHN (approved=false): không phải độ chính xác nghiệp vụ.",
    "Phụ lục: resolver đọc cả `Phụ lục số N` và số La Mã (`Phụ lục II` → `phu luc 2`); "
    "`gold.canonical_address` không đọc `số` và giữ La Mã (`phu luc ii`). Gold chỉ sinh địa chỉ "
    "phụ lục từ nhãn `Phụ lục <n>` của VBHN, bộ dữ liệu hiện không có gold phụ lục La Mã.",
)


def predict_slots(pair_dir: Path, shape: str) -> tuple[list[dict], int]:
    """One slot per resolved target of ``pair_dir`` + the number of context-only parent items."""

    StructuralNode, address, resolver = _app()
    pair_dir = Path(pair_dir)
    pair_id = pair_dir.name
    nodes = segment((pair_dir / "vbhn.txt").read_text(encoding="utf-8"), pair_id)
    if shape == "article-only":
        nodes = collapse_to_articles(nodes)
    elif shape != "full":
        raise ValueError(f"unknown tree shape {shape!r}")
    index = resolver.StructureIndex.build(
        [StructuralNode(**node) for node in nodes], {pair_id: "body"}
    )
    items = parse(
        (pair_dir / "amending.txt").read_text(encoding="utf-8"), _operative_article(pair_dir)
    )
    parents = _parents(items)
    with_children = set(parents.values())
    slots: list[dict] = []
    resolutions: list = []
    groups: dict[int, list[int]] = {}
    for i, item in enumerate(items):
        if i in with_children:
            continue  # a parent item ("một số điểm của khoản 1 và khoản 2 …") is context only
        parent = parents.get(i)
        context = (
            address.parse_parent_context(items[parent]["head"]) if parent is not None else None
        )
        multi = bool(context and len(context.khoan_options) > 1)
        found = address.parse_addresses(item["head"])
        base = {
            "pair_id": pair_id,
            "src_address": item["src_address"],
            "op": item["op"],
            "head": item["head"],
            "multi_clause": multi,
        }
        if not found:
            slots.append({**base, **_slot(None, "no_address")})
            resolutions.append(None)
            continue
        for addr in found:
            target = address.inherit(addr, context)
            res = index.resolve(
                target,
                parts=resolver.default_target_parts(index, None, target),
                require_existing=item["op"] != "INSERTION",
            )
            if parent is not None:
                groups.setdefault(parent, []).append(len(slots))
            slots.append({**base, **_slot(res)})
            resolutions.append(res)
    for members in groups.values():
        ordered = resolver.disambiguate_by_order([resolutions[m] for m in members], index)
        for m, res in zip(members, ordered):
            if res != resolutions[m]:
                slots[m].update(_slot(res))
    return slots, len(with_children)


def run(data_dir: Path, shapes: tuple[str, ...], baseline_path: Path | None) -> dict:
    data_dir = Path(data_dir)
    problems = verify_manifest(data_dir)
    if problems:
        raise ValueError("manifest check failed: " + "; ".join(problems))
    manifest_bytes = (data_dir / MANIFEST).read_bytes().replace(b"\r\n", b"\n")
    pair_ids = sorted(entry["pair_id"] for entry in json.loads(manifest_bytes)["pairs"])
    gold = {pid: load_gold(data_dir / pid) for pid in pair_ids}
    report: dict = {
        "ground_truth": GROUND_TRUTH_LABEL,
        "dataset": {
            "pairs": len(pair_ids),
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        },
        "parser": "baseline (P1 spike port): items + heads",
        "p1_baseline": _p1_baseline(baseline_path),
        "limitations": list(LIMITATIONS),
        "tree_shapes": {},
    }
    for shape in shapes:
        slots: dict[str, list[dict]] = {}
        context_items = 0
        for pid in pair_ids:
            slots[pid], n_context = predict_slots(data_dir / pid, shape)
            context_items += n_context
        report["tree_shapes"][shape] = {**_score(gold, slots), "context_items": context_items}
    return report


def render_markdown(report: dict) -> str:
    shapes = list(report["tree_shapes"])
    ds = report["dataset"]
    lines = [
        "# Contract graph eval — P2 address resolver",
        "",
        f"- Ground truth: `{report['ground_truth']}` (chưa duyệt; không phải độ chính xác nghiệp vụ)",
        f"- Dataset: {ds['pairs']} cặp, manifest sha256 `{ds['manifest_sha256']}`",
        f"- Parser: {report['parser']}; hình dạng cây: {', '.join(shapes)} "
        "(`article-only` chỉ báo cáo, không gate — RT-05)",
        "- precision = UNIQUE đúng / UNIQUE; coverage = UNIQUE / items; accuracy = UNIQUE đúng / "
        "items; items = gold (op ≠ OTHER) đã ghép được slot của parser.",
        "",
        "## Tổng",
        "",
    ]
    header = ("shape", "scope", "items", "UNIQUE", "AMBIGUOUS", "NOT_FOUND", "UNIQUE đúng")
    header += ("precision", "coverage", "accuracy")
    lines += [_row(header), _row(("---",) * len(header))]
    for shape in shapes:
        block = report["tree_shapes"][shape]
        scopes = [("all", block["overall"]), ("multi-clause", block["multi_clause"]["overall"])]
        if "nd50-2021" in block["by_pair"]:
            scopes += [
                ("nd50-2021", block["by_pair"]["nd50-2021"]),
                ("nd50-2021 multi-clause", block["multi_clause"]["by_pair"].get("nd50-2021")),
            ]
        lines += [_block_row(shape, scope, b) for scope, b in scopes if b]
    lines += ["", "## Theo method", ""]
    header = ("shape", "method", "UNIQUE", "đúng", "precision")
    lines += [_row(header), _row(("---",) * len(header))]
    for shape in shapes:
        for method, m in report["tree_shapes"][shape]["overall"]["by_method"].items():
            lines.append(
                _row((shape, method, str(m["unique"]), str(m["correct"]), _fmt(m["precision"])))
            )
    lines += ["", "## So với P1 baseline (RT-10)", ""]
    header = ("pair", "P1 target_correct") + tuple(f"P2 {s} UNIQUE đúng" for s in shapes)
    lines += [_row(header), _row(("---",) * len(header))]
    for pid in report["tree_shapes"][shapes[0]]["by_pair"]:
        p1 = report["p1_baseline"].get(pid, {})
        cells = [pid, f"{p1['target_correct']}/{p1['target_denominator']}" if p1 else "n/a"]
        for shape in shapes:
            b = report["tree_shapes"][shape]["by_pair"][pid]
            cells.append(f"{b['unique_correct']}/{b['items']}")
        lines.append(_row(tuple(cells)))
    for shape in shapes:
        block = report["tree_shapes"][shape]
        lines += ["", f"## {shape}: UNIQUE sai ({len(block['wrong_unique'])})", ""]
        lines += [
            f"- {r['pair_id']} [{r['note_no']}] {r['op']} {r['src_address']} ({r['method']}): "
            f"gold `{r['gold_target_address']}` ≠ pred `{r['pred_target_address']}`"
            for r in block["wrong_unique"]
        ]
        order = block["order_inference"]
        lines += [
            "",
            f"- {shape}: ORDER_INFERENCE chốt {order['locked']} (đúng {order['correct']}, "
            f"sai {order['wrong']}); mục cha chỉ làm ngữ cảnh: {block['context_items']}; "
            f"gold bị bỏ sót: {len(block['missed_gold'])}; slot không ghép gold: "
            f"{len(block['unmatched_slots'])}",
        ]
    lines += ["", "## Giới hạn", ""]
    lines += [f"- {item}" for item in report["limitations"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.contract_graph.resolver_eval")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="writes <out>.json and <out>.md")
    parser.add_argument("--tree-shape", choices=("full", "article-only", "both"), default="both")
    parser.add_argument(
        "--baseline",
        default=str(DEFAULT_BASELINE),
        help="p1-baseline.json for the RT-10 comparison; empty string to skip",
    )
    args = parser.parse_args(argv)
    shapes = SHAPES if args.tree_shape == "both" else (args.tree_shape,)
    try:
        report = run(args.data, shapes, Path(args.baseline) if args.baseline else None)
    except ValueError as exc:
        print(f"refusing to score: {exc}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    _write(
        args.out.parent / f"{args.out.name}.json",
        json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
    )
    _write(args.out.parent / f"{args.out.name}.md", render_markdown(report))
    for shape in shapes:
        o = report["tree_shapes"][shape]["overall"]
        print(
            f"{shape}: items {o['items']}, UNIQUE {o['status']['UNIQUE']} "
            f"(đúng {o['unique_correct']}), AMBIGUOUS {o['status']['AMBIGUOUS']}, "
            f"NOT_FOUND {o['status']['NOT_FOUND']}"
        )
    return 0


def _parents(items: list[dict]) -> dict[int, int]:
    """Sub-item index → index of its parent item ("diem a khoan 2 dieu 1" → "khoan 2 dieu 1")."""

    out: dict[int, int] = {}
    latest: dict[str, int] = {}
    for i, item in enumerate(items):
        src = item["src_address"] or ""
        if src.startswith("diem "):
            parent_src = src.split(" ", 2)[2]
            if parent_src in latest:
                out[i] = latest[parent_src]
        latest[src] = i
    return out


def _slot(res, reason: str | None = None) -> dict:
    if res is None:
        return {
            "status": "NOT_FOUND",
            "method": None,
            "target_address": None,
            "candidates": 0,
            "reason": reason,
        }
    unique = res.status == "UNIQUE"
    return {
        "status": str(res.status),
        "method": str(res.method) if unique and res.method else None,
        "target_address": res.canonical if unique else None,
        "candidates": len(res.candidates),
        "reason": ",".join(res.residual) if res.status == "NOT_FOUND" and res.residual else None,
    }


def _score(gold: dict[str, list[dict]], slots: dict[str, list[dict]]) -> dict:
    rows, missed, unmatched = [], [], []
    for pid in sorted(gold):
        pairs, miss, unm = match(gold[pid], slots[pid])
        for g, s in pairs:
            if g["op"] == OTHER:
                continue
            rows.append(
                {
                    "pair_id": pid,
                    "note_no": g["note_no"],
                    "op": g["op"],
                    "src_address": g["src_address"],
                    "gold_target_address": g.get("target_address"),
                    "pred_target_address": s["target_address"],
                    "status": s["status"],
                    "method": s["method"],
                    "multi_clause": s["multi_clause"],
                    "correct": bool(
                        s["status"] == "UNIQUE"
                        and g.get("target_address")
                        and s["target_address"] == g["target_address"]
                    ),
                }
            )
        missed += [
            {
                "pair_id": pid,
                "note_no": g["note_no"],
                "op": g["op"],
                "src_address": g["src_address"],
            }
            for g in miss
            if g["op"] != OTHER
        ]
        unmatched += [
            {k: s[k] for k in ("pair_id", "src_address", "op", "status", "target_address")}
            for s in unm
        ]
    multi = [r for r in rows if r["multi_clause"]]
    locked = [r for r in rows if r["method"] == "ORDER_INFERENCE"]
    return {
        "overall": _block(rows),
        "by_pair": {pid: _block([r for r in rows if r["pair_id"] == pid]) for pid in sorted(gold)},
        "multi_clause": {
            "overall": _block(multi),
            "by_pair": {
                pid: _block([r for r in multi if r["pair_id"] == pid])
                for pid in sorted(gold)
                if any(r["pair_id"] == pid for r in multi)
            },
        },
        "order_inference": {
            "locked": len(locked),
            "correct": sum(r["correct"] for r in locked),
            "wrong": sum(not r["correct"] for r in locked),
        },
        "rows": rows,
        "wrong_unique": [r for r in rows if r["status"] == "UNIQUE" and not r["correct"]],
        "missed_gold": missed,
        "unmatched_slots": unmatched,
        "slots": [s for pid in sorted(slots) for s in slots[pid]],
    }


def _block(rows: list[dict]) -> dict:
    unique = [r for r in rows if r["status"] == "UNIQUE"]
    correct = sum(r["correct"] for r in unique)
    by_method = {}
    for method in METHODS:
        hits = [r for r in unique if r["method"] == method]
        ok = sum(r["correct"] for r in hits)
        by_method[method] = {"unique": len(hits), "correct": ok, "precision": rate(ok, len(hits))}
    return {
        "items": len(rows),
        "status": {s: sum(1 for r in rows if r["status"] == s) for s in STATUSES},
        "unique_correct": correct,
        "precision": rate(correct, len(unique)),
        "coverage": rate(len(unique), len(rows)),
        "accuracy": rate(correct, len(rows)),
        "by_method": by_method,
    }


def _p1_baseline(path: Path | None) -> dict:
    if path is None:
        return {}
    by_pair = json.loads(Path(path).read_text(encoding="utf-8"))["by_pair"]
    return {
        pid: {
            "target_correct": block["all"]["target_accuracy"]["passed"],
            "target_denominator": block["all"]["target_accuracy"]["denominator"],
        }
        for pid, block in sorted(by_pair.items())
    }


def _block_row(shape: str, scope: str, b: dict) -> str:
    s = b["status"]
    return _row(
        (
            shape,
            scope,
            str(b["items"]),
            str(s["UNIQUE"]),
            str(s["AMBIGUOUS"]),
            str(s["NOT_FOUND"]),
            str(b["unique_correct"]),
            _fmt(b["precision"]),
            _fmt(b["coverage"]),
            _fmt(b["accuracy"]),
        )
    )


def _fmt(r: dict) -> str:
    if not r["denominator"]:
        return "0/0 (n/a)"
    lo, hi = r["wilson95"]
    return f"{r['passed']}/{r['denominator']} ({r['rate']:.3f}; CI95 {lo:.3f}–{hi:.3f})"


def _row(cells: tuple[str, ...]) -> str:
    return "| " + " | ".join(cells) + " |"


def _write(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _app():
    """The ai-service modules under test (``ai-service`` is not a package of this repo root)."""

    if str(AI_SERVICE) not in sys.path:
        sys.path.insert(0, str(AI_SERVICE))
    from app.contracts.models import StructuralNode
    from app.pipeline.contract_graph import address, resolver

    return StructuralNode, address, resolver


if __name__ == "__main__":
    sys.exit(main())
