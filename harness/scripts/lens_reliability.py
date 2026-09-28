#!/usr/bin/env python3
"""lens_reliability.py — per-script run count, failure rate, and duration
percentiles from hook-telemetry.jsonl (the records track_script_execution
writes: script, exit, optional ms). Pure gather → render-agnostic dict.
READ-ONLY.

`exit` is the coarsely-inferred signal (see track_script_execution.infer_exit —
authoritative is_error/interrupted, else an explicit non-zero exit phrase), so a
non-zero rate is a SIGNAL to inspect, not a precise failure count. `ms` is
best-effort (present only when the Pre/Post bash-timer paired), so percentiles
degrade to None when no run carried a duration. Fail-soft on bad lines.
"""

import os
import sys
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import telemetry_paths  # noqa: E402

_MIN_RUNS = 5  # below this the lens is low-volume gated (advice suppressed)


def gather(days: int = 30, top: int = 10) -> dict:
    top = max(1, top)
    stats = defaultdict(lambda: {"runs": 0, "failures": 0, "ms": []})
    total = 0
    # Shared read-path (dict-guarded, ts-windowed); only script-execution records
    # (track_script_execution) carry `script`.
    for rec in telemetry_paths.iter_records_in_window("hook-telemetry.jsonl", days):
        if not rec.get("script"):
            continue
        s = stats[rec["script"]]
        s["runs"] += 1
        total += 1
        try:
            if int(rec.get("exit", 0)) != 0:
                s["failures"] += 1
        except (TypeError, ValueError):
            pass  # unparseable exit → treated as success (matches infer_exit)
        ms = rec.get("ms")
        if isinstance(ms, (int, float)) and not isinstance(ms, bool):
            s["ms"].append(ms)

    scripts = []
    for name, s in stats.items():
        ms_sorted = sorted(s["ms"])
        scripts.append({
            "script": name,
            "runs": s["runs"],
            "failures": s["failures"],
            "fail_rate": (s["failures"] / s["runs"]) if s["runs"] else 0.0,
            "p50_ms": telemetry_paths.percentile(ms_sorted, 50),
            "p95_ms": telemetry_paths.percentile(ms_sorted, 95),
        })
    # worst (highest failure rate, then most-run) first — what to inspect
    scripts.sort(key=lambda r: (-r["fail_rate"], -r["runs"], r["script"]))
    return {
        "lens": "reliability",
        "days": days,
        "total_runs": total,
        "scripts": scripts[:top],
        "sufficient": total >= _MIN_RUNS,
        "min_runs": _MIN_RUNS,
        "gated": telemetry_paths.low_volume_gate(total, _MIN_RUNS),
    }


def render(agg) -> str:
    """Markdown for this lens (owned here, not in the analyze_telemetry spine)."""
    from telemetry_formatters import markdown_table
    head = "## lens: reliability"
    meta = "_script runs: %s · gated: %s_" % (agg.get("total_runs"), agg.get("gated"))
    scripts = agg.get("scripts", [])
    if not scripts:
        return "%s\n\n%s\n\n_no harness-script runs recorded in the window._" % (head, meta)

    def _ms(v):
        return "-" if v is None else str(v)
    rows = [[s["script"], str(s["runs"]), str(s["failures"]),
             "%.0f%%" % (s["fail_rate"] * 100), _ms(s["p50_ms"]), _ms(s["p95_ms"])]
            for s in scripts]
    table = markdown_table(["script", "runs", "fail", "fail%", "p50 ms", "p95 ms"],
                           rows, align=["l", "r", "r", "r", "r", "r"])
    note = ("\n\n_`fail%` uses the coarse inferred exit (is_error / explicit "
            "non-zero phrase), so it is a signal to inspect, not a precise count; "
            "`ms` is best-effort (only when the bash-timer paired)._")
    return "%s\n\n%s\n\n%s%s" % (head, meta, table, note)
