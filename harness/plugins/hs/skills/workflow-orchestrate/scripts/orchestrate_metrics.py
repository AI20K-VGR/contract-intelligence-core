#!/usr/bin/env python3
"""orchestrate_metrics.py — append-only cross-run metrics corpus for fan-out orchestration.

One JSON line per finished job appends to `plans/reports/orchestrate-history.jsonl` (a
non-markdown file under plans/, gitignored): run id, job id, runtime, model, task, duration,
status, exit code, attempts, arbiter verdict, and token/cost when the harness reports them.
Append-only, never a whole-file read-modify-write (code-standards §3), and every row is
stamped with `actor` + `ts` via resolve_actor — the attribution the upstream corpus omitted.

The corpus is ADVISORY input only: at report time the skill compares observed success rate /
duration / cost against the routing table and, when they contradict, adds a reviewable
"routing suggestions" section. It NEVER silently edits a routing reference mid-run.

resolve_actor lives in the harness hook runtime; this lane imports it one-way (walk up to the
harness root, add its hooks/ to the path). A resolution failure degrades to a neutral actor
rather than dropping the row.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _resolve_actor() -> str:
    """resolve_actor() from the harness hook runtime; a neutral fallback if it cannot load, so
    a metrics append never crashes the orchestrator."""
    try:
        here = Path(__file__).resolve()
        for anc in here.parents:
            hooks = anc / "hooks" / "hook_runtime.py"
            if hooks.is_file():
                if str(anc / "hooks") not in sys.path:
                    sys.path.insert(0, str(anc / "hooks"))
                from hook_runtime import resolve_actor  # noqa: E402
                return resolve_actor()
    except Exception:  # noqa: BLE001 — attribution is best-effort, never a crash surface
        pass
    return "unknown"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def history_path() -> str:
    """The cross-run metrics corpus under the harness state dir (gitignored), NOT plans/reports/
    — one shared `orchestrate-history.jsonl`. Reuses run_state.state_dir() (same resolver)."""
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    import run_state  # noqa: E402 — sibling script in the same skill scripts dir
    return str(run_state.state_dir() / "orchestrate-history.jsonl")


def append(history_path, record) -> dict:
    """Append one metrics row (with actor + ts injected) as a single JSON line. Append-only:
    open in 'a' mode, one line, never rewrite prior rows. Returns the stamped record."""
    row = dict(record)
    row.setdefault("actor", _resolve_actor())
    row.setdefault("ts", _now_iso())
    os.makedirs(os.path.dirname(os.path.abspath(history_path)), exist_ok=True)
    with open(history_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


if __name__ == "__main__":
    # `orchestrate_metrics.py <history.jsonl> '<json-record>'` appends one row.
    if len(sys.argv) >= 3:
        append(sys.argv[1], json.loads(sys.argv[2]))
