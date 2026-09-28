#!/usr/bin/env python3
"""lens_partner.py — read-only lens over the ccs partner-lane job registry.

Reads harness/state/partner/jobs.jsonl (written by partner_companion) and
aggregates by purpose+provider: job count, TOTAL COST (partner has real cost,
unlike the token-only gemini lane), the pass/degrade split, and latency
percentiles paired from each job's running->terminal timestamps. Read-only +
fail-soft: a missing file or a torn line is skipped, never a crash — this is
a usage lens, not a gate. Registry-wired into analyze_telemetry so hs:insights
surfaces it. Twin of lens_gemini.py, keyed on provider instead of model and
summing cost instead of tokens.
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


def _cost(rec):
    """A job record's cost lives directly on it (partner_companion stamps
    provenance["cost"] onto the terminal record) or, failing that, nested
    under provenance. Never self-computed — read what ccs reported, and
    treat a missing/non-numeric cost as 0 rather than crashing."""
    cost = rec.get("cost")
    if cost is None:
        prov = rec.get("provenance") or {}
        cost = prov.get("cost") if isinstance(prov, dict) else None
    if not isinstance(cost, (int, float)):
        return 0.0
    return float(cost)


def _aggregate(records) -> dict:
    """Pure aggregation over an iterable of job records. Terminal records are
    the unit of a 'job'; latency pairs each with its earlier running record
    by job_id."""
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

    groups = defaultdict(lambda: {"count": 0, "cost": 0.0, "passed": 0,
                                  "degraded": 0, "failed": 0, "inert": 0, "_lat": []})
    degrade_total = 0
    for r in terminals:
        key = (r.get("purpose", "?"), r.get("provider") or "?")
        g = groups[key]
        g["count"] += 1
        g["cost"] += _cost(r)
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
    for (purpose, provider), g in sorted(groups.items()):
        lat = g.pop("_lat")
        by_group.append({
            "purpose": purpose, "provider": provider,
            "count": g["count"], "cost": round(g["cost"], 4),
            "cost_avg": round(g["cost"] / g["count"], 4) if g["count"] else 0,
            "passed": g["passed"], "degraded": g["degraded"],
            "failed": g["failed"], "inert": g["inert"],
            "latency_p50_ms": telemetry_paths.percentile(lat, 50),
            "latency_p95_ms": telemetry_paths.percentile(lat, 95),
        })

    return {
        "lens": "partner",
        "total_jobs": len(terminals),
        "total_cost": round(sum(g["cost"] for g in by_group), 4),
        "degrade_total": degrade_total,
        "by_group": by_group,
        "_lens_key": "partner",
    }


def _iter_records(days):
    """Read jobs.jsonl fail-soft, filtering to the day window by terminal ts.
    A missing file yields nothing; a torn line is skipped."""
    path = harness_paths.state_dir() / "partner" / "jobs.jsonl"
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
        # Window BOTH terminal AND running records: a running record of any
        # age was yielded before, so a stale start ts could pair against an
        # in-window terminal and distort latency. Non-ts-bearing statuses
        # pass untouched.
        status = rec.get("status")
        if cutoff is not None and (status in _TERMINAL or status == "running"):
            ts = telemetry_paths.parse_iso_ts(rec.get("ts"))
            if ts is not None and ts < cutoff:
                continue
        yield rec


def gather(days: int = 30, top: int = 10) -> dict:
    return _aggregate(_iter_records(days))


def render(agg: dict) -> str:
    lines = ["## lens: partner", "",
             "total_jobs=%d total_cost=$%.4f degrade_total=%d"
             % (agg.get("total_jobs", 0), agg.get("total_cost", 0.0),
                agg.get("degrade_total", 0))]
    for g in agg.get("by_group", []):
        lines.append(
            "- %s/%s: count=%d cost=$%.4f passed=%d degraded=%d failed=%d "
            "p50=%sms p95=%sms" % (
                g["purpose"], g["provider"], g["count"], g["cost"],
                g["passed"], g["degraded"], g["failed"],
                g["latency_p50_ms"], g["latency_p95_ms"]))
    return "\n".join(lines)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="ccs partner-lane job lens")
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args(argv)
    print(json.dumps(gather(days=args.days), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
