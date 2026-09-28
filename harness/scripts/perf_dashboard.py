#!/usr/bin/env python3
"""perf_dashboard.py — render the hook self-timing stream into ONE static HTML.

Reads the diag core_timing records (state/diag/diag.jsonl, written by the dispatcher)
and computes, per hook, p50 / p95 / max / mean and a spawn-per-day count, then renders
a self-contained HTML file (inline CSS, no CDN) ranked slowest-first — "which hook is
worth its spawn". On-demand (no daemon). DuckDB is used when present (faster on a large
stream); the default is a pure-python percentile so the dashboard needs zero deps and
stays self-contained.
"""

import argparse
import json
import os
import sys
from pathlib import Path


def _state_dir() -> Path:
    raw = os.environ.get("HARNESS_STATE_DIR")
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parent.parent / "state"


def read_timing(source) -> list:
    """core_timing records from a diag.jsonl file (or a state dir). Fail-open → []."""
    p = Path(source)
    if p.is_dir():
        p = p / "diag" / "diag.jsonl"
    if not p.is_file():
        return []
    out = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("event") == "core_timing" and "elapsed_ms" in rec:
                out.append(rec)
    except OSError:
        return []
    return out


def percentile(values, p) -> float:
    """Linear-interpolated p-th percentile (numpy-style). Empty → 0.0."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    k = (p / 100.0) * (len(s) - 1)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return float(s[lo] + (s[hi] - s[lo]) * (k - lo))


def aggregate(records) -> dict:
    """{hook: {count, p50, p95, max, mean}} over elapsed_ms."""
    by_hook = {}
    for r in records:
        by_hook.setdefault(r.get("hook", "?"), []).append(float(r.get("elapsed_ms", 0)))
    agg = {}
    for hook, vals in by_hook.items():
        agg[hook] = {
            "count": len(vals),
            "p50": round(percentile(vals, 50), 3),
            "p95": round(percentile(vals, 95), 3),
            "max": round(max(vals), 3),
            "mean": round(sum(vals) / len(vals), 3),
        }
    return agg


def spawn_per_day(records) -> dict:
    """{YYYY-MM-DD: count} of timing records (a proxy for hook-core executions)."""
    per_day = {}
    for r in records:
        day = str(r.get("ts", ""))[:10]
        if day:
            per_day[day] = per_day.get(day, 0) + 1
    return per_day


def slowest(agg) -> list:
    """[(hook, stats), ...] ranked by p95 descending."""
    return sorted(agg.items(), key=lambda kv: kv[1]["p95"], reverse=True)


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render_html(agg, per_day) -> str:
    """A self-contained HTML report (inline CSS, no external resource)."""
    if not agg:
        rows = '<tr><td colspan="5">no data — run some hooks first</td></tr>'
    else:
        rows = "".join(
            "<tr><td>%s</td><td>%d</td><td>%.2f</td><td>%.2f</td><td>%.2f</td></tr>"
            % (_esc(h), s["count"], s["p50"], s["p95"], s["max"])
            for h, s in slowest(agg))
    day_rows = "".join("<tr><td>%s</td><td>%d</td></tr>" % (_esc(d), n)
                       for d, n in sorted(per_day.items())) or \
        '<tr><td colspan="2">no data</td></tr>'
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<title>harness hook timing</title><style>"
        "body{font:14px/1.5 system-ui,sans-serif;margin:2rem;color:#111}"
        "h1{font-size:1.2rem}table{border-collapse:collapse;margin:1rem 0}"
        "th,td{border:1px solid #ccc;padding:4px 10px;text-align:right}"
        "th:first-child,td:first-child{text-align:left}"
        "caption{font-weight:600;text-align:left;margin-bottom:.3rem}"
        "</style></head><body>"
        "<h1>Harness hook self-timing</h1>"
        "<table><caption>Per-hook cost (slowest first, ms)</caption>"
        "<tr><th>hook</th><th>count</th><th>p50</th><th>p95</th><th>max</th></tr>"
        + rows + "</table>"
        "<table><caption>Core executions per day</caption>"
        "<tr><th>day</th><th>count</th></tr>" + day_rows + "</table>"
        "</body></html>")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="render hook self-timing to static HTML")
    ap.add_argument("--out", default=None, help="output HTML path (default: state/diag/dashboard.html)")
    ap.add_argument("--state", default=None, help="state dir (default: HARNESS_STATE_DIR)")
    args = ap.parse_args(argv)
    state = Path(args.state) if args.state else _state_dir()
    records = read_timing(state)
    html = render_html(aggregate(records), spawn_per_day(records))
    out = Path(args.out) if args.out else state / "diag" / "dashboard.html"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
    except OSError as e:
        print("perf_dashboard: cannot write %s (%s)" % (out, e), file=sys.stderr)
        return 1
    print("perf_dashboard: wrote %s (%d hooks, %d records)"
          % (out, len(aggregate(records)), len(records)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
