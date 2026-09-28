#!/usr/bin/env python3
"""
build_traceability_matrix — render the story -> epic -> PRD -> BRD-goal -> metric
matrix as a markdown table, from the graph JSON. Plus an artifact/ID/status index.

CLI:
    build_traceability_matrix.py --root <project-dir>
        Emits JSON {matrix_markdown, index, graph}. Always exits 0.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

from encoding_utils import configure_utf8_console, emit_json, write_text_atomic
from spec_graph import build_graph, _now, ID_SENTINELS


def _natkey(s: str) -> list:
    """Natural-sort key: split numeric runs so S2 precedes S10 (lexicographic
    `rows.sort()` ordered S1, S10, S2 in the PO-facing matrix)."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def _visible_id(v: Any) -> Any:
    """Blank an internal id sentinel (`<missing-id>`/`<invalid-id>`) so it renders
    as a neutral `—`, never leaking the placeholder into the PO-facing output."""
    return None if v in ID_SENTINELS else v

configure_utf8_console()


def _cell(s: Any) -> str:
    # Markdown tables split cells on `|`, so any raw pipe inside a cell
    # bleeds into adjacent columns. Escape it as the standard `\|` so
    # GFM renders it visibly without breaking the table. Newlines collapse
    # to spaces for the same reason.
    text = "" if s is None else str(s)
    return text.replace("|", r"\|").replace("\n", " ").replace("\r", " ") or "—"


def build_matrix(graph: Dict[str, Any]) -> str:
    nodes_by_id = {n["id"]: n for n in graph["nodes"]}
    stories = [n for n in graph["nodes"] if n.get("type") == "story"]
    rows: List[List[str]] = []
    for s in stories:
        # epic/prd are coerced to str|None at the graph source, but guard the FK
        # lookups too so a future raw field can never be used as an unhashable key.
        ep = s.get("epic")
        epic = nodes_by_id.get(ep) if isinstance(ep, str) else None
        pr = epic.get("prd") if epic else None
        prd = nodes_by_id.get(pr) if isinstance(pr, str) else None
        raw_brd_goals = prd.get("brd_goals", []) if prd else []
        # Coerce list elements to str (a hand-edit may leave a non-str element) and
        # guard the bare-string case so the join neither raises (mixed-type list)
        # nor char-splits (`brd_goals: BRD-G1`) into garbled cells.
        brd_goals = [str(g) for g in raw_brd_goals if g is not None] if isinstance(raw_brd_goals, list) else []
        raw_metrics = s.get("metrics")
        metric_cell = (", ".join(str(m) for m in raw_metrics if m is not None)
                       if isinstance(raw_metrics, list) else "—") or "—"
        rows.append([
            _cell(_visible_id(s.get("id"))),
            _cell(epic.get("id") if epic else None),
            _cell(prd.get("id") if prd else None),
            _cell(", ".join(brd_goals)) if brd_goals else "—",
            _cell(metric_cell),
            _cell(s.get("status")),
            _cell(s.get("scope")),
            _cell(s.get("moscow")),
        ])

    rows.sort(key=lambda r: _natkey(r[0]))
    header = ["Story", "Epic", "PRD", "BRD Goals", "Metrics", "Status", "Scope", "MoSCoW"]
    sep = ["---"] * len(header)
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(sep) + " |"]
    for r in rows:
        lines.append("| " + " | ".join(r) + " |")
    if not rows:
        lines.append("| (no stories) |  |  |  |  |  |  |  |")
    return "\n".join(lines)


def build_index(graph: Dict[str, Any]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for n in graph["nodes"]:
        out.append({
            "id": _visible_id(n.get("id")) or "—",
            "type": n.get("type") or "—",
            "status": n.get("status") or "—",
            "file": n.get("file") or "—",
        })
    out.sort(key=lambda x: (str(x["type"]), str(x["id"])))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--write", action="store_true",
                    help="also write docs/product/visuals/traceability-matrix.md")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    graph = build_graph(root)
    matrix = build_matrix(graph)
    index = build_index(graph)

    out = {
        "schema_version": "1.0",
        "root": str(root),
        "generated_at": _now(),
        "matrix_markdown": matrix,
        "index": index,
        "graph": graph,
    }

    if args.write:
        # Fixed path read by humans/CI while a re-render may be in flight — write
        # atomically (temp + os.replace) so a concurrent reader never sees the file
        # mid-truncate. Regenerable content, so no writer-vs-writer lock is needed.
        target = root / "docs" / "product" / "visuals" / "traceability-matrix.md"
        write_text_atomic(target, f"# Traceability Matrix\n\n_Generated {out['generated_at']}_\n\n{matrix}\n")
        out["__written_to"] = str(target.relative_to(root))

    emit_json(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
