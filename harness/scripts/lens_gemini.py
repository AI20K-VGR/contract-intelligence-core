#!/usr/bin/env python3
"""lens_gemini.py — read-only lens over the gemini partner job registry.

Reads harness/state/gemini/jobs.jsonl (written by gemini_companion, P4) and
aggregates by purpose+model: job count, token totals (from the ACP stats), the
pass/degrade split (a degrade is the RT-07 down-signal), and latency percentiles
paired from each job's running→terminal timestamps. Read-only + fail-soft: a
missing file or a torn line is skipped, never a crash — this is a usage lens, not
a gate. Registry-wired into analyze_telemetry so hs:insights surfaces it.
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import harness_paths  # noqa: E402
import telemetry_paths  # noqa: E402

_TERMINAL = {"done", "degraded", "inert", "failed", "cancelled"}


def _tokens(stats):
    if not isinstance(stats, dict):
        return 0
    # Print-mode stats normalize to total_tokens (the full accounting — dogfood
    # confirmed total = input + thoughts + candidates), so prefer it; fall back to
    # input+output for the legacy/flat shape that carried no total.
    total = stats.get("total_tokens")
    if total is not None:
        return int(total or 0)
    return int(stats.get("input_tokens", 0) or 0) + int(stats.get("output_tokens", 0) or 0)


def _aggregate(records) -> dict:
    """Pure aggregation over an iterable of job records. Terminal records are the
    unit of a 'job'; latency pairs each with its earlier running record by
    job_id."""
    running_ts = {}
    terminals = []
    for r in records:
        if not isinstance(r, dict):
            continue
        status = r.get("status")
        jid = r.get("job_id")
        if status == "running" and jid is not None:
            running_ts.setdefault(jid, r.get("ts"))
        elif status in _TERMINAL:
            terminals.append(r)

    groups = defaultdict(lambda: {"count": 0, "tokens": 0, "passed": 0,
                                  "degraded": 0, "failed": 0, "inert": 0, "_lat": []})
    degrade_total = 0
    for r in terminals:
        key = (r.get("purpose", "?"), r.get("model") or "?")
        g = groups[key]
        g["count"] += 1
        g["tokens"] += _tokens(r.get("stats"))
        status = r.get("status")
        if status == "done":
            g["passed"] += 1
        elif status == "degraded":
            g["degraded"] += 1
            degrade_total += 1
        elif status == "inert":
            g["inert"] += 1  # lane off is not a failure — count it apart
        elif status in ("failed", "cancelled"):
            g["failed"] += 1
        # latency: pair terminal ts with the job's running ts
        jid = r.get("job_id")
        t_end = telemetry_paths.parse_iso_ts(r.get("ts"))
        t_start = (telemetry_paths.parse_iso_ts(running_ts.get(jid))
                   if jid in running_ts else None)
        if t_start and t_end:
            g["_lat"].append((t_end - t_start).total_seconds() * 1000.0)

    by_group = []
    for (purpose, model), g in sorted(groups.items()):
        lat = g.pop("_lat")
        by_group.append({
            "purpose": purpose, "model": model,
            "count": g["count"], "tokens": g["tokens"],
            "token_avg": round(g["tokens"] / g["count"], 1) if g["count"] else 0,
            "passed": g["passed"], "degraded": g["degraded"],
            "failed": g["failed"], "inert": g["inert"],
            "latency_p50_ms": telemetry_paths.percentile(lat, 50),
            "latency_p95_ms": telemetry_paths.percentile(lat, 95),
        })

    return {
        "lens": "gemini",
        "total_jobs": len(terminals),
        "degrade_total": degrade_total,
        "by_group": by_group,
        "_lens_key": "gemini",
    }


def _iter_records(days):
    """Read jobs.jsonl fail-soft, filtering to the day window by terminal ts.
    A missing file yields nothing; a torn line is skipped."""
    path = harness_paths.state_dir() / "gemini" / "jobs.jsonl"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    cutoff = None
    if days is not None:
        try:
            from datetime import timedelta, timezone
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        except Exception:
            cutoff = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue  # torn/partial line — skip, never crash
        # Window BOTH terminal AND running records: a running record of any age was
        # yielded before, so a stale start ts could pair against an in-window
        # terminal and distort latency. Non-ts-bearing statuses pass untouched.
        status = rec.get("status")
        if cutoff is not None and (status in _TERMINAL or status == "running"):
            ts = telemetry_paths.parse_iso_ts(rec.get("ts"))
            if ts is not None and ts < cutoff:
                continue
        yield rec


def gather(days: int = 30, top: int = 10) -> dict:
    return _aggregate(_iter_records(days))


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="gemini partner job lens")
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args(argv)
    print(json.dumps(gather(days=args.days), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
