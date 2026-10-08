"""P3 predictor: the runtime ``plan_edges`` on (operative body of the amending text, VBHN tree).

  python -m evals.contract_graph.pipeline_predictor --data evals/contract_graph/data \
      --out-dir evals/contract_graph/reports

writes ``p3-operation-parser`` (full tree) and ``p3-operation-parser-article-only``: each is
exactly the ``run_eval score`` report of that predictor (``--predictor
evals.contract_graph.pipeline_predictor:predict`` / ``:predict_article_only``) plus a
``p1_baseline_comparison`` block (JSON key + Markdown section) against ``p1-baseline.json``.

The amending article is one source node ``Điều <operative_article>`` in a file with role
``annex``; the target tree is ``segment(vbhn.txt)`` (``predict``) or its article-only collapse
(``predict_article_only``, the AI1 tree shape — RT-05) in a file with role ``body``. Same code
as ``run_idp``; only the input distribution differs. One prediction per planned edge
(operation unit × target address); an unresolved target is ``target_address: None``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from evals.contract_graph import run_eval
from evals.contract_graph.baseline_predictor import _operative_article
from evals.contract_graph.normalize import _outside_quotes, operative_body
from evals.contract_graph.segment import collapse_to_articles, segment

AI_SERVICE = Path(__file__).resolve().parents[2] / "ai-service"
AMENDING_FILE = "amending"
DEFAULT_BASELINE = Path(__file__).resolve().parent / "reports" / "p1-baseline.json"
REPORTS = (
    ("p3-operation-parser", "evals.contract_graph.pipeline_predictor:predict"),
    (
        "p3-operation-parser-article-only",
        "evals.contract_graph.pipeline_predictor:predict_article_only",
    ),
)
GATE_PAIR = "nd50-2021"
NL = "\n"


def predict(pair_dir: Path) -> list[dict]:
    return _predict(Path(pair_dir), "full")


def predict_article_only(pair_dir: Path) -> list[dict]:
    return _predict(Path(pair_dir), "article-only")


def _predict(pair_dir: Path, shape: str) -> list[dict]:
    StructuralNode, builder, resolver, documents = _app()
    pair_id = pair_dir.name
    amending = (pair_dir / "amending.txt").read_text(encoding="utf-8")
    # Every article of the amending text is a source node, as run_idp sees every node: operations
    # also live outside the manifest's operative article ("Điều 2. Bãi bỏ Điều 4 và Điều 11").
    sources = []
    operative = _operative_article(pair_dir)
    for article in _amending_articles(amending, operative):
        body = _own_article(operative_body(amending, article, str(int(article) + 1)), article)
        heading = re.match(rf"Điều\s+{re.escape(article)}\s*\.\s*", body)
        sources.append(
            StructuralNode(
                node_id=f"{pair_id}:amending:{article}",
                type="CLAUSE",
                raw_label=f"Điều {article}",
                text=body[heading.end() :] if heading else body,
                source_file_id=AMENDING_FILE,
            )
        )
    targets = segment((pair_dir / "vbhn.txt").read_text(encoding="utf-8"), pair_id)
    if shape == "article-only":
        targets = collapse_to_articles(targets)
    index = resolver.StructureIndex.build(
        [*sources, *(StructuralNode(**node) for node in targets)],
        {AMENDING_FILE: "annex", pair_id: "body"},
    )
    # Identity of the VBHN's base document = the one the manifest's operative article names
    # (BL-005, direction B). Runtime has no such identity yet, so it refuses every named document.
    operative_node = next(s for s in sources if s.raw_label == f"Điều {operative}")
    base = documents.named_document((operative_node.text or "").split("\n", 1)[0])
    known = {base} if base else set()
    return [
        {
            "src_address": plan.source_address,
            "op": plan.op.value,
            "target_address": plan.target_address if plan.status == "UNIQUE" else None,
            "status": str(plan.status),
            "method": plan.method.value if plan.method and plan.status == "UNIQUE" else None,
            "standard": plan.standard,
            "head": plan.source_span[:160],
        }
        for plan in builder.plan_edges(sources, index, known_documents=known)
        # a refused foreign-document target is an issue at runtime, not an edge
        if plan.status != "FOREIGN_DOCUMENT"
    ]


def _amending_articles(amending: str, operative: str) -> list[str]:
    """Article numbers with a heading outside quotes, ascending; the operative one always kept."""

    outside = _outside_quotes(amending)
    found = {
        m.group(1)
        for m in re.finditer(r"(?:^|(?<=[.:;”\"] ))Điều\s+(\d+)\s*\.", amending, re.M)
        if outside(m.start())
    }
    return sorted(found | {operative}, key=int)


def write_reports(data: Path, out_dir: Path, baseline: Path = DEFAULT_BASELINE) -> dict[str, dict]:
    p1 = json.loads(Path(baseline).read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for name, spec in REPORTS:
        prefix = Path(out_dir) / name
        if run_eval.main(["score", "--data", str(data), "--predictor", spec, "--out", str(prefix)]):
            raise RuntimeError(f"run_eval refused to score {name}")
        json_path, md_path = prefix.with_suffix(".json"), prefix.with_suffix(".md")
        report = json.loads(json_path.read_text(encoding="utf-8"))
        report["p1_baseline_comparison"] = compare_to_baseline(report, p1)
        _write(json_path, json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + NL)
        _write(md_path, md_path.read_text(encoding="utf-8") + _comparison_markdown(report))
        out[name] = report
    return out


def compare_to_baseline(report: dict, p1: dict) -> dict:
    """Per op: recall (``op_lexical_agreement``, ``target_correct``) and noise (predictions
    agreeing with no gold, RT-09) of this report next to P1; plus UNIQUE-but-wrong targets."""

    if report["dataset"]["manifest_sha256"] != p1["dataset"]["manifest_sha256"]:
        raise ValueError("p1-baseline was scored on another dataset")

    def row(block: dict) -> dict:
        return {
            "n_gold": block["n_gold"],
            "n_pred": block["n_pred"],
            "op_lexical_agreement": block["op_lexical_agreement"]["passed"],
            "target_correct": block["target_accuracy"]["passed"],
            "noise": block["n_pred"] - block["op_precision"]["passed"],
        }

    ops = list(dict.fromkeys([*p1["overall"]["by_op"], *report["overall"]["by_op"]]))
    empty = {
        "n_gold": 0,
        "n_pred": 0,
        "op_lexical_agreement": {"passed": 0},
        "target_accuracy": {"passed": 0},
        "op_precision": {"passed": 0},
    }
    return {
        "by_op": {
            op: {
                "p1": row(p1["overall"]["by_op"].get(op, empty)),
                "p3": row(report["overall"]["by_op"].get(op, empty)),
            }
            for op in ops
        },
        "all": {"p1": row(p1["overall"]["all"]), "p3": row(report["overall"]["all"])},
        "unmatched_predictions": {
            "p1": len(p1["unmatched_predictions"]),
            "p3": len(report["unmatched_predictions"]),
        },
        "wrong_unique_targets": {
            "all": _wrong_unique(report),
            GATE_PAIR: _wrong_unique(report, GATE_PAIR),
        },
    }


def _wrong_unique(report: dict, pair: str | None = None) -> int:
    return sum(
        1
        for m in report["target_mismatches"]
        if m["pred_target_address"] is not None and (pair is None or m["pair_id"] == pair)
    )


def _comparison_markdown(report: dict) -> str:
    cmp = report["p1_baseline_comparison"]
    lines = [
        "",
        "## So với P1 baseline",
        "",
        "noise = n_pred − pred khớp op với gold (RT-09: không được tăng so với P1).",
        "",
        "| op | n_gold | op_lexical_agreement P1 → P3 | target_correct P1 → P3 "
        "| n_pred P1 → P3 | noise P1 → P3 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for op, both in [*cmp["by_op"].items(), ("ALL", cmp["all"])]:
        a, b = both["p1"], both["p3"]
        lines.append(
            f"| {op} | {b['n_gold']} | {a['op_lexical_agreement']} → {b['op_lexical_agreement']} "
            f"| {a['target_correct']} → {b['target_correct']} | {a['n_pred']} → {b['n_pred']} "
            f"| {a['noise']} → {b['noise']} |"
        )
    unmatched, wrong = cmp["unmatched_predictions"], cmp["wrong_unique_targets"]
    lines += [
        "",
        f"- unmatched_predictions: P1 {unmatched['p1']} → P3 {unmatched['p3']}",
        f"- đích UNIQUE sai: toàn bộ {wrong['all']}; {GATE_PAIR}: {wrong[GATE_PAIR]}",
    ]
    return NL.join(lines) + NL


def _write(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline=NL) as fh:
        fh.write(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.contract_graph.pipeline_predictor")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    args = parser.parse_args(argv)
    for name, report in write_reports(args.data, args.out_dir, args.baseline).items():
        cmp = report["p1_baseline_comparison"]
        print(
            f"{name}: "
            + ", ".join(
                f"{op} agree {v['p1']['op_lexical_agreement']}->{v['p3']['op_lexical_agreement']}"
                f" target {v['p1']['target_correct']}->{v['p3']['target_correct']}"
                f" noise {v['p1']['noise']}->{v['p3']['noise']}"
                for op, v in cmp["by_op"].items()
            )
        )
    return 0


def _own_article(body: str, article: str) -> str:
    """Cut at the next article heading that opens a line without a quote. ``operative_body``
    skips headings it believes quoted; one missing closing quote in the source (tt01-2022-bct)
    then carries the next articles, which amend other documents, into this one."""

    # Any later line-start heading ends this article, not only ``article + 1``: with every article
    # now a source node, a table-of-contents "Điều 2." line would otherwise swallow Điều 1's body.
    heading = re.match(rf"Điều\s+{re.escape(article)}\s*\.", body)
    next_heading = re.compile(r"^Điều\s+\d+[a-zđ]?\s*\.", re.M)
    m = next_heading.search(body, heading.end() if heading else 0)
    return body[: m.start()].rstrip() if m else body


def _app():
    """The ai-service modules under test (``ai-service`` is not a package of this repo root)."""

    if str(AI_SERVICE) not in sys.path:
        sys.path.insert(0, str(AI_SERVICE))
    from app.contracts.models import StructuralNode
    from app.pipeline.contract_graph import builder, documents, resolver

    return StructuralNode, builder, resolver, documents


if __name__ == "__main__":
    sys.exit(main())
