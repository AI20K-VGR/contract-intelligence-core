#!/usr/bin/env python3
"""lens_risk_flags.py — surface guarded-config paths written THROUGH THE SHELL.

bash_write_guard records a `write_guard_bypass` event to hook-telemetry.jsonl
whenever a gate-config path is written via a shell redirect/tee/sed -i/python
open() (a path the Write/Edit write_guard cannot see). This lens aggregates
those events by target so a human can confirm each was intended — recurring
bypasses of the same gate config are a tamper / workflow smell worth a look.

Read-only, advisory: it counts + ranks, never judges or blocks. The edited files
are tracked, so each bypass is also a git diff — this lens just makes the pattern
visible in one place. (cowork-logs harvest: risk-flag scan, adapted to the
harness's own telemetry signal.)
"""

import os
import sys
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import telemetry_paths  # noqa: E402

_MIN_EVENTS = 5  # below this the lens is low-volume gated (advice suppressed)
_BYPASS_EVENT = "write_guard_bypass"


def gather(days: int = 30, top: int = 10) -> dict:
    top = max(1, top)
    by_target = defaultdict(lambda: {"count": 0, "sessions": set()})
    total = 0
    # Shared read-path: dict-guarded, ts-windowed, non-object lines skipped.
    for rec in telemetry_paths.iter_records_in_window("hook-telemetry.jsonl", days):
        if rec.get("event") != _BYPASS_EVENT:
            continue
        target = rec.get("target") or "?"
        by_target[target]["count"] += 1
        sess = rec.get("session")
        if sess:
            by_target[target]["sessions"].add(sess)
        total += 1
    flags = sorted(
        ({"target": t, "count": v["count"], "sessions": len(v["sessions"])}
         for t, v in by_target.items()),
        key=lambda f: (-f["count"], f["target"]),
    )[:top]
    return {
        "lens": "risk_flags",
        "days": days,
        "total_bypasses": total,
        "flags": flags,
        "sufficient": total >= _MIN_EVENTS,
        "min_events": _MIN_EVENTS,
        "gated": telemetry_paths.low_volume_gate(total, _MIN_EVENTS),
    }


def render(agg) -> str:
    """Markdown for this lens (owned here, not in the analyze_telemetry spine)."""
    from telemetry_formatters import markdown_table
    head = "## lens: risk_flags"
    meta = "_guarded-path shell writes: %s · gated: %s_" % (
        agg.get("total_bypasses"), agg.get("gated"))
    flags = agg.get("flags", [])
    if not flags:
        return "%s\n\n%s\n\n_none — no gate config was written through the shell._" % (
            head, meta)
    rows = [[f["target"], str(f["count"]), str(f["sessions"])] for f in flags]
    table = markdown_table(["guarded path (written via shell)", "writes", "sessions"],
                           rows, align=["l", "r", "r"])
    note = ("\n\n_Each is a gate-config path written through the shell (bypassing "
            "write_guard) — tamper-visible as a git diff; confirm each was "
            "intended. Advisory, never a block._")
    return "%s\n\n%s\n\n%s%s" % (head, meta, table, note)
