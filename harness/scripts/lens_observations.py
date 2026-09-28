#!/usr/bin/env python3
"""lens_observations.py — judgment-signal lens (read-only, honesty-gated).

Surfaces the closed-vocab signals skills emit at their end-of-work checkpoint
(observations.jsonl). Counterpart to the deterministic lenses: those read what a hook
captures automatically, this reads what a skill DECIDED was worth recording.

The honesty gate is the whole point. The baseline is skill activity, read from the
EXISTING invocations.jsonl (no new hook needed). If that baseline is sparse, the lens
must NOT read the absence of signals as "nothing to improve" — it says the corpus is too
thin to judge. And when the baseline IS dense but no signals were emitted, it names the
UNDER-EMISSION (skills ran but the cooperative checkpoint did not fire), rather than
reporting a clean bill of health — the exact failure mode this channel exists to fix.
Pure gather → render-agnostic dict. READ-ONLY.
"""
import os
import sys
from collections import Counter

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import telemetry_paths  # noqa: E402

_MIN_INVOCATIONS = 5  # below this baseline the lens is low-volume gated (advice suppressed)


def gather(days: int = 30, top: int = 10) -> dict:
    top = max(1, top)
    signal_counts: Counter = Counter()
    skill_counts: Counter = Counter()
    total_obs = 0
    for rec in telemetry_paths.iter_records_in_window("observations.jsonl", days):
        sig = rec.get("signal")
        if not sig:
            continue
        signal_counts[str(sig)] += 1
        if rec.get("skill"):
            skill_counts[str(rec["skill"])] += 1
        total_obs += 1

    # Baseline = skill activity, from the existing invocations sink (NO new hook).
    baseline = sum(1 for _ in telemetry_paths.iter_records_in_window("invocations.jsonl", days))

    return {
        "lens": "observations",
        "days": days,
        "total_observations": total_obs,
        "baseline_invocations": baseline,
        "top_signals": [{"signal": s, "count": n} for s, n in signal_counts.most_common(top)],
        "by_skill": [{"skill": s, "count": n} for s, n in skill_counts.most_common(top)],
        "min_invocations": _MIN_INVOCATIONS,
        "sufficient": baseline >= _MIN_INVOCATIONS,
        "gated": telemetry_paths.low_volume_gate(baseline, _MIN_INVOCATIONS),
    }


def render(agg) -> str:
    from telemetry_formatters import markdown_table
    head = "## lens: observations"
    meta = "_signals: %s · baseline invocations: %s · sufficient: %s · gated: %s_" % (
        agg.get("total_observations"), agg.get("baseline_invocations"),
        agg.get("sufficient"), agg.get("gated"))

    if agg.get("gated"):
        body = (
            "_baseline is %s skill invocation(s) — below the %s threshold. Too thin to "
            "read the judgment-signal channel: an empty channel here means 'not enough "
            "activity yet', NOT 'nothing to improve'._"
            % (agg.get("baseline_invocations"), agg.get("min_invocations")))
        return "%s\n\n%s\n\n%s" % (head, meta, body)

    if agg.get("total_observations", 0) == 0:
        body = (
            "_%s skill invocation(s) in the window but **0** judgment signals emitted. "
            "The cooperative end-of-work checkpoint is under-firing — read this as "
            "under-reporting, not a clean bill of health._"
            % agg.get("baseline_invocations"))
        return "%s\n\n%s\n\n%s" % (head, meta, body)

    rows = [[r["signal"], str(r["count"])] for r in agg.get("top_signals", [])]
    table = markdown_table(["signal", "count"], rows, align=["l", "r"])
    return "%s\n\n%s\n\n%s" % (head, meta, table)
