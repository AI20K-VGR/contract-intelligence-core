#!/usr/bin/env python3
"""standards_strict_gate — shell-runnable strict enforcement for the standards tree.

Re-runs the structural checks and exits non-zero when any finding has
severity=error (exit 0 on a clean tree). The builder and the checks keep the
"always exit 0 + emit JSON" contract; THIS is the separate orchestrator layer
that blocks.

It is a CI gate, not a tool-call hook: standards are per-clone INPUT, so blocking
a dev who is mid-authoring their own standards would be wrong. A malformed tree
is a build failure the author fixes. The presence gate (a sibling, not extended
here) answers a different question — "did the workflow step run?" — and is the
one wired into the tool-call path. A `core(root) -> findings` library entry is
provided so a future compliance hook could wrap the same logic without rework.

Exit codes: 0 = clean (no error findings), 2 = blocked (>=1 error finding). 2 is
the harness block convention; never exit 1 for a block. A human summary is always
written to stderr; stdout is reserved (not used for the block decision).

CLI:
    standards_strict_gate.py --root <project-dir>
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

import check_standards
import guard_policy
import standards_graph
from encoding_utils import configure_utf8_console

configure_utf8_console()

EXIT_OK = 0
EXIT_BLOCKED = 2


def core(root: Path) -> List[Dict[str, Any]]:
    """Build the standards graph and run the structural checks. The single
    library entry a future compliance hook would wrap (the named seam)."""
    graph = standards_graph.build_graph(Path(root))
    return check_standards.check(graph)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".",
                    help="project root (contains harness/standards/)")
    args = ap.parse_args()
    root = Path(args.root).resolve()

    graph = standards_graph.build_graph(root)
    findings = check_standards.check(graph)
    errors = [f for f in findings if f.get("severity") == "error"]
    warns = [f for f in findings if f.get("severity") == "warn"]

    n_nodes = len(graph.get("nodes", []))
    print(f"[standards_strict_gate] {n_nodes} nodes checked · "
          f"{len(errors)} errors · {len(warns)} warns", file=sys.stderr)

    if not errors:
        return EXIT_OK

    lines = ["[standards_strict_gate] BLOCKED on errors:"]
    for f in errors:
        aid = f.get("artifact_id") or "?"
        chk = f.get("check") or "?"
        detail = f.get("detail") or ""
        lines.append(f"  - {chk} · {aid} · {detail}")
    # Funnel the block-reason through the unified posture: block returns it (we
    # print + exit 2); warn emits it as `[advisory]` and off stays silent, both
    # exit 0 (the gate writes the audit line and any advisory itself).
    gated = guard_policy.gate(
        "standards_strict_gate", "\n".join(lines), hook="standards_strict_gate")
    if gated:
        print(gated, file=sys.stderr)
        return EXIT_BLOCKED
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
