#!/usr/bin/env python3
"""lens_subagent_outcomes.py — per-agent-type outcome distribution from
subagent-outcomes.jsonl (the records track_subagent_outcome writes:
agent_type, outcome). Pure gather → render-agnostic dict. READ-ONLY.

HONESTY: outcome is classified from the subagent's OWN transcript tail, but that
transcript's terminal record is typically NOT flushed when SubagentStop fires, so
the hook records `unknown` plus the authoritative transcript path. This lens
reclassifies those `unknown` records HERE, at read time, when the file is flushed
(its stop_reason is then available). Records with no stored path (older records,
hosts that omit it) or whose transcript is gone stay `unknown` — never fabricated.
The lens reports a `known_rate` (fraction of DEFINITE outcomes) rather than
implying every run was adjudicated; a window still dominated by pre-fix records
shows a low known_rate, which reflects WHEN the data was captured, not a quality
claim. Fail-soft on bad lines; skips parseable non-object lines.
"""

import os
import sys
from collections import Counter, defaultdict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import telemetry_paths  # noqa: E402
import subagent_classify  # noqa: E402

_MIN_RECORDS = 5  # below this the lens is low-volume gated
_UNKNOWN = {"unknown", "", None}


def _known_rate(counter) -> float:
    total = sum(counter.values())
    if not total:
        return 0.0
    known = sum(n for o, n in counter.items() if o not in _UNKNOWN)
    return known / total


def gather(days: int = 30, top: int = 10) -> dict:
    top = max(1, top)
    by_agent = defaultdict(Counter)
    overall = Counter()
    total = 0
    # Shared read-path: dict-guarded, ts-windowed, non-object lines skipped.
    for rec in telemetry_paths.iter_records_in_window("subagent-outcomes.jsonl", days):
        agent = rec.get("agent_type") or "unknown"
        outcome = rec.get("outcome") or "unknown"
        # Deferred classification: the hook records `unknown` when the subagent
        # transcript's terminal record isn't flushed yet at SubagentStop. By now
        # the file IS flushed, so reclassify from the stored authoritative path
        # (never fabricates — a missing/unflushed file stays `unknown`).
        if outcome in _UNKNOWN:
            recovered = subagent_classify.classify_from_transcript(rec.get("transcript"))
            if recovered not in _UNKNOWN:
                outcome = recovered
        by_agent[agent][outcome] += 1
        overall[outcome] += 1
        total += 1
    agents = []
    for agent, counter in by_agent.items():
        agents.append({
            "agent_type": agent,
            "runs": sum(counter.values()),
            "outcomes": dict(counter),
            "known_rate": _known_rate(counter),
        })
    agents.sort(key=lambda a: (-a["runs"], a["agent_type"]))
    return {
        "lens": "subagent_outcomes",
        "days": days,
        "total": total,
        "known_rate": _known_rate(overall),
        "agents": agents[:top],
        "sufficient": total >= _MIN_RECORDS,
        "min_records": _MIN_RECORDS,
        "gated": telemetry_paths.low_volume_gate(total, _MIN_RECORDS),
    }


def render(agg) -> str:
    """Markdown for this lens (owned here, not in the analyze_telemetry spine)."""
    from telemetry_formatters import markdown_table
    head = "## lens: subagent_outcomes"
    meta = "_subagent runs: %s · definite-outcome rate: %.0f%% · gated: %s_" % (
        agg.get("total"), agg.get("known_rate", 0) * 100, agg.get("gated"))
    agents = agg.get("agents", [])
    if not agents:
        return "%s\n\n%s\n\n_no subagent outcomes recorded in the window._" % (head, meta)
    rows = [[a["agent_type"], str(a["runs"]), "%.0f%%" % (a["known_rate"] * 100),
             ", ".join("%s:%d" % (o, n) for o, n in sorted(a["outcomes"].items()))]
            for a in agents]
    table = markdown_table(["agent type", "runs", "definite%", "outcomes"],
                           rows, align=["l", "r", "r", "l"])
    note = ("\n\n_Outcome is classified from the subagent's own transcript. That "
            "transcript is usually not flushed when SubagentStop fires, so the hook "
            "records `unknown` + the transcript path and this lens reclassifies at "
            "read time once the file is flushed. Records with no stored path (older "
            "records) or whose transcript is gone stay `unknown`, so a window "
            "dominated by older records shows a low definite%%. That reflects WHEN "
            "the data was captured, not a harness detection bug, and never a quality "
            "claim. Advisory._")
    return "%s\n\n%s\n\n%s%s" % (head, meta, table, note)
