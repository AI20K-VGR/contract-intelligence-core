#!/usr/bin/env python3
"""lens_perf_trend.py — read-only p95 latency trend per hook script. READ-ONLY.

Reads the LIVE `ms` durations that track_script_execution already writes to
hook-telemetry.jsonl (the old perf-metrics.jsonl sink was dead — a lens with no
writer). Per script it takes p95 over the window and flags a regression by comparing
the early-half p95 to the late-half p95 with perf_telemetry.perf_regression's wide noise
band (advisory only — there is no block path here). One sample = no baseline = not
regressed.
"""

import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import telemetry_paths  # noqa: E402

_MIN_SAMPLES = 2  # need a baseline + a current before a trend means anything
_SINK = "hook-telemetry.jsonl"
_TS_MIN = datetime.min.replace(tzinfo=timezone.utc)  # sort sentinel for an unparseable ts


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def gather(days: int = 30, top: int = 10) -> dict:
    top = max(1, top)
    series = defaultdict(list)  # script -> [(ts, ms)]
    total = 0
    for rec in telemetry_paths.iter_records_in_window(_SINK, days):
        ms = _num(rec.get("ms"))
        if ms is None:
            continue
        # Store the PARSED datetime (not the raw string): a raw ts string sorts a
        # +07:00 offset AFTER an earlier +00:00 wall-clock, scrambling the
        # early/late regression split.
        series[rec.get("script") or "?"].append(
            (telemetry_paths.parse_iso_ts(rec.get("ts")), ms))
        total += 1

    import perf_telemetry as pt
    rows = []
    for label, pts in series.items():
        pts.sort(key=lambda t: t[0] or _TS_MIN)  # chronological by parsed datetime
        vals = [ms for _, ms in pts]
        p95 = telemetry_paths.percentile(vals, 95)
        # regression: compare the early-half p95 to the late-half p95 (needs enough
        # samples for both halves to mean anything); else no baseline → not regressed.
        if len(vals) >= _MIN_SAMPLES * 2:
            half = len(vals) // 2
            first_p95 = telemetry_paths.percentile(vals[:half], 95)
            last_p95 = telemetry_paths.percentile(vals[half:], 95)
            verdict = pt.perf_regression({"p95": last_p95}, {"p95": first_p95})
        else:
            first_p95 = last_p95 = p95
            verdict = {"regressed": False, "delta_pct": None}
        rows.append({
            "label": label,
            "samples": len(vals),
            "p95": p95,
            "first_p95": first_p95,
            "last_p95": last_p95,
            "delta_pct": verdict.get("delta_pct"),
            "regressed": bool(verdict.get("regressed")),
        })
    rows.sort(key=lambda r: (not r["regressed"], -((r["delta_pct"] or 0)),
                             -(r["p95"] or 0)))
    return {
        "lens": "perf_trend",
        "days": days,
        "total_samples": total,
        "labels": rows[:top],
        "sufficient": total >= _MIN_SAMPLES,
        "min_samples": _MIN_SAMPLES,
        "gated": telemetry_paths.low_volume_gate(total, _MIN_SAMPLES),
        "enforcement": "advisory",  # this lens never gates
    }


def render(agg) -> str:
    """Markdown for this lens (owned here, not in the analyze_telemetry spine)."""
    from telemetry_formatters import markdown_table
    head = "## lens: perf_trend"
    meta = "_perf samples: %s · gated: %s · advisory (never a gate)_" % (
        agg.get("total_samples"), agg.get("gated"))
    labels = agg.get("labels", [])
    if not labels:
        return ("%s\n\n%s\n\n_no perf samples recorded in the window._"
                % (head, meta))

    def _n(v):
        return "-" if v is None else ("%.0f" % v)

    def _d(v):
        return "-" if v is None else ("%+.0f%%" % v)

    rows = [[r["label"], str(r["samples"]), _n(r["first_p95"]), _n(r["last_p95"]),
             _d(r["delta_pct"]), "yes" if r["regressed"] else "no"]
            for r in labels]
    table = markdown_table(
        ["label", "n", "first p95", "last p95", "delta", "regressed"],
        rows, align=["l", "r", "r", "r", "r", "r"])
    note = ("\n\n_a regression is p95 up >20% over the window's first sample — a "
            "wide band for environment noise; ADVISORY, never a block._")
    return "%s\n\n%s\n\n%s%s" % (head, meta, table, note)
