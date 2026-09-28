#!/usr/bin/env python3
"""lens_docs_build.py — docs-build outcome lens (read-only).

Reads the fine-grained build-outcome sink (`docs-build.jsonl`) that the docs-build
orchestrator emits at end-of-run: how many showcase builds ran in the window, how
many failed (and at which stage), and the latest published page/diagram counts. The
generic skill-invocation lens already counts THAT `/hs:docs-build` was called; this
lens reads what each build actually DID. Pure gather → render-agnostic dict. READ-ONLY.

Fail-soft on telemetry (bad lines skipped). An absent sink renders as "no builds in
the window", never an error.
"""
import os
import sys
from collections import Counter
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import telemetry_paths  # noqa: E402

_MIN_BUILDS = 5  # below this the lens is low-volume gated (advice suppressed)
_TS_MIN = datetime.min.replace(tzinfo=timezone.utc)  # sort sentinel for an unparseable ts


def gather(days: int = 30, top: int = 10) -> dict:
    top = max(1, top)
    total = 0
    outcomes: Counter = Counter()
    fail_stages: Counter = Counter()
    last_ok = None
    last_ok_ts = _TS_MIN
    for rec in telemetry_paths.iter_records_in_window("docs-build.jsonl", days):
        total += 1
        outcome = str(rec.get("outcome") or "unknown")
        outcomes[outcome] += 1
        if outcome == "failed":
            fail_stages[str(rec.get("stage") or "?")] += 1
        elif outcome == "ok":
            # Pick by PARSED timestamp, not iteration order: iter_records_in_window
            # unions the legacy sink with per-session shards, and shard read order
            # is by session-hash filename, not chronology, once any record carries
            # a `session` key (lens_perf_trend hits the same hazard). ">=" keeps
            # the later-iterated record on an exact tie.
            ts = telemetry_paths.parse_iso_ts(rec.get("ts")) or _TS_MIN
            if last_ok is None or ts >= last_ok_ts:
                last_ok = rec
                last_ok_ts = ts
    return {
        "lens": "docs_build",
        "days": days,
        "total_builds": total,
        "ok": outcomes.get("ok", 0),
        "failed": outcomes.get("failed", 0),
        "fail_stages": [{"stage": s, "count": n} for s, n in fail_stages.most_common(top)],
        "latest_ok": ({"pages": last_ok.get("pages"), "diagrams": last_ok.get("diagrams"),
                       "md_sourced": last_ok.get("md_sourced")} if last_ok else None),
        "min_builds": _MIN_BUILDS,
        "sufficient": total >= _MIN_BUILDS,
        "gated": telemetry_paths.low_volume_gate(total, _MIN_BUILDS),
    }


def render(agg) -> str:
    from telemetry_formatters import markdown_table
    head = "## lens: docs_build"
    total = agg.get("total_builds", 0)
    meta = "_builds: %s · ok: %s · failed: %s · gated: %s_" % (
        total, agg.get("ok"), agg.get("failed"), agg.get("gated"))

    if total == 0:
        return "%s\n\n%s\n\n_No docs-build runs recorded in the window._" % (head, meta)

    parts = [head, "", meta, ""]
    latest = agg.get("latest_ok")
    if latest:
        parts.append("_latest successful build: %s page(s), %s diagram(s), %s md-sourced._"
                     % (latest.get("pages"), latest.get("diagrams"), latest.get("md_sourced")))
        parts.append("")
    # The honesty gate is a CAVEAT, not a content suppressor (mirrors the sibling
    # lenses): fail-stage data still shows; the note only warns the window is thin.
    if agg.get("failed"):
        rows = [[r["stage"], str(r["count"])] for r in agg.get("fail_stages", [])]
        parts.append(markdown_table(["fail stage", "count"], rows, align=["l", "r"]))
    if agg.get("gated"):
        parts.append(
            "_window is %s build(s) — below the %s-build threshold. Too thin to draw "
            "conclusions: absent failures here mean 'not enough data', not 'all clear'._"
            % (total, agg.get("min_builds")))
    return "\n".join(parts).rstrip()
