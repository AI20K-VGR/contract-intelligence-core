#!/usr/bin/env python3
"""lens_session.py — read-only session-level lens over sessions.jsonl.

sessions.jsonl is the richest per-session telemetry (duration, tool mix, files
modified, subagent count) but had NO lens — the slot was registered as NOT_MEASURED.
This surfaces duration percentiles, the aggregate tool mix, totals, sessions/day, and
the top actor. Read-only + fail-soft (the shared iter_records_in_window swallows bad
lines / missing file)."""
import os
import sys
from collections import Counter

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import telemetry_paths  # noqa: E402

_SINK = "sessions.jsonl"
_MIN_SESSIONS = 5


def gather(days: int = 30, top: int = 10) -> dict:
    top = max(1, top)
    durations = []
    tools = Counter()
    files = 0
    subagents = 0
    by_day = Counter()
    actors = Counter()
    n = 0
    for rec in telemetry_paths.iter_records_in_window(_SINK, days):
        n += 1
        d = rec.get("duration_s")
        if isinstance(d, (int, float)) and not isinstance(d, bool):
            durations.append(d)
        t = rec.get("tools")
        if isinstance(t, dict):
            for k, v in t.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    tools[str(k)] += v
        f = rec.get("files_modified")
        if isinstance(f, (int, float)) and not isinstance(f, bool):
            files += f
        sa = rec.get("subagents")
        if isinstance(sa, (int, float)) and not isinstance(sa, bool):
            subagents += sa
        by_day[str(rec.get("ts") or "")[:10]] += 1
        a = rec.get("actor")
        if a:
            actors[str(a)] += 1
    return {
        "lens": "session",
        "days": days,
        "sessions": n,
        "duration_p50_s": telemetry_paths.percentile(durations, 50),
        "duration_p90_s": telemetry_paths.percentile(durations, 90),
        "files_modified_total": files,
        "subagents_total": subagents,
        "top_tools": [{"tool": k, "count": v} for k, v in tools.most_common(top)],
        "sessions_per_day": [{"day": k, "count": v} for k, v in sorted(by_day.items())],
        "top_actor": (actors.most_common(1)[0][0] if actors else None),
        "sufficient": n >= _MIN_SESSIONS,
        "gated": telemetry_paths.low_volume_gate(n, _MIN_SESSIONS),
    }


def render(agg) -> str:
    from telemetry_formatters import markdown_table
    head = "## lens: session"
    meta = ("_sessions: %s · dur p50: %ss · p90: %ss · files: %s · subagents: %s · "
            "top actor: %s · gated: %s_" % (
                agg.get("sessions"), agg.get("duration_p50_s"),
                agg.get("duration_p90_s"), agg.get("files_modified_total"),
                agg.get("subagents_total"), agg.get("top_actor"), agg.get("gated")))
    rows = [[r["tool"], str(r["count"])] for r in agg.get("top_tools", [])]
    table = markdown_table(["tool", "uses"], rows, align=["l", "r"])
    return "\n".join([head, meta, "", table])


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(gather(days=int(sys.argv[1]) if len(sys.argv) > 1 else 30),
                     ensure_ascii=False, indent=2))
