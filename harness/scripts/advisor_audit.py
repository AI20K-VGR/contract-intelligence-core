#!/usr/bin/env python3
"""advisor_audit.py — deterministic, advisory drift review of Advisor verdicts.

The Advisor (`hs:escalation-consultant`, model `fable`) is the terminal oracle for
escalation calls no other agent can resolve. Nothing audits IT: a single-source,
plausible-sounding verdict from the Advisor is exactly the confab-shape the grid
anti-confab contract rejects everywhere else, with no detection loop on the Advisor
itself. This script closes that gap — a READ-ONLY scanner over an append-only JSONL
sidecar of Advisor verdicts (upstream writer is a separate follow-up; this reader is
graceful when that sidecar is not wired yet — see `run_audit`'s "sink not wired" path).

Ported from FrankCode's `advisor-audit.md` QA methodology (weekly drift review). This
is a SCANNER, not an emitter: unlike `emit_observation.py` (a skill appends ONE signal
per call), this reads MANY days of records and reports a pattern.

Workflow per call_site: bucket verdicts -> compute 4 drift signals (override-rate,
flipped-verdict, repeat-prompt, malformed-rate) -> drift_score -> escalate to the
maintainer (human) when a call_site's score is >3 sigma above this window's baseline.
Flipped-verdict on an identical `inputs_hash` is zero-tolerance: it always escalates,
regardless of sigma. Escalation routes to the HUMAN maintainer, never back to the
Advisor — asking the Advisor to audit itself is the anti-pattern this script replaces.

Non-blocking / advisory only: never exits non-zero for audit findings (R5). All
thresholds/weights live in `harness/data/advisor-audit.yaml` (SSOT) — no hardcoded
float in this file (mirrors the harness's tier-SSOT float discipline elsewhere).

CLI:
    advisor_audit.py [--sink PATH] [--config PATH] [--out PATH] [--format md|json]
                      [--escalation-dir DIR]
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, pstdev

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import wilson  # noqa: E402 — the interval engine, reachable only after the insert above

_DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "data" / "advisor-audit.yaml"
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# A verdict's `reasoning` starting with one of these signals a malformed/failed call
# (budget cap, wire/auth failure, or a shape the Advisor's own gate rejected) rather
# than a real judgment — ported verbatim from advisor-audit.md workflow step 5.
MALFORMED_PREFIXES = (
    "advisor-gate:", "budget-cap", "opus-call-failed",
    "malformed-json", "invalid-verdict-shape",
)
# caller_action values that count as an "override" of the Advisor's verdict.
OVERRIDE_ACTIONS = {"overridden", "re-asked"}


def load_config(path=None) -> dict:
    """Load thresholds/weights from the YAML SSOT. A missing/malformed file falls back
    to the documented defaults rather than crashing an advisory tool (R5)."""
    import yaml_io
    p = Path(path) if path is not None else _DEFAULT_CONFIG
    try:
        data = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    except (OSError, yaml_io.YAMLError):
        data = {}
    # `or {}` only replaces a falsy None/empty; a YAML whose top level parses
    # to a list/scalar stays non-dict and every `.get` below would raise. An
    # advisory tool must fall back to defaults, never crash on a bad shape (R5).
    if not isinstance(data, dict):
        data = {}
    # Sub-shapes must be guarded too: a list-valued `thresholds:`/`weights:`
    # would raise AttributeError on .get, and a non-numeric value (e.g.
    # `override_rate: high`) would raise ValueError on the cast. An advisory
    # tool falls back to the documented default per field, never crashes (R5).
    thresholds = data.get("thresholds")
    weights = data.get("weights")
    interval = data.get("interval")
    if not isinstance(thresholds, dict):
        thresholds = {}
    if not isinstance(weights, dict):
        weights = {}

    def _num(mapping, key, default, cast):
        try:
            return cast(mapping.get(key, default))
        except (TypeError, ValueError):
            return default

    return {
        "sink_path": data.get("sink_path", "state/audit/advisor-verdicts.jsonl"),
        "window_days": _num(data, "window_days", 7, int),
        "override_rate": _num(thresholds, "override_rate", 0.20, float),
        "malformed_rate": _num(thresholds, "malformed_rate", 0.05, float),
        "repeat_prompt": _num(thresholds, "repeat_prompt", 3, int),
        "sigma": _num(thresholds, "sigma", 3, float),
        "w_override": _num(weights, "override", 3, float),
        "w_flipped": _num(weights, "flipped", 5, float),
        "w_malformed": _num(weights, "malformed", 2, float),
        "w_repeat": _num(weights, "repeat", 1, float),
        # Which interval to report, and at what confidence. A non-dict block falls back
        # to the documented default like every other field here (R5: an advisory tool
        # never crashes on a bad shape) -- but an unknown METHOD NAME does raise, in
        # `_interval_cfg`, because answering with wilson under the name the operator
        # typed is a wrong answer, not a degraded one.
        "interval": interval if isinstance(interval, dict) else {},
    }


def _actor() -> str:
    try:
        hooks_dir = Path(__file__).resolve().parent.parent / "hooks"
        if str(hooks_dir) not in sys.path:
            sys.path.append(str(hooks_dir))
        import hook_runtime
        return hook_runtime.resolve_actor(session_id=os.environ.get("HARNESS_SESSION_ID") or None)
    except Exception:
        return "user:unknown"


def _resolve_path(path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (_REPO_ROOT / p)


def read_sink(sink_path) -> "tuple[list, bool]":
    """Read the JSONL sidecar. Returns (records, is_wired). is_wired is False when the
    file is absent or has no non-blank lines at all — that is "sink not wired", NOT a
    finding (R4: empty must never read as a false-positive anomaly). A malformed JSON
    line is skipped, never a crash (R1/T9) — one bad line must not blind the whole scan."""
    p = _resolve_path(sink_path)
    if not p.is_file():
        return [], False
    raw = p.read_text(encoding="utf-8")
    if not raw.strip():
        return [], False
    records = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue  # robust: skip the bad line, keep scanning
        if isinstance(rec, dict):
            records.append(rec)
    return records, True


def _within_window(ts_value, now, window_days) -> bool:
    """A record with no/garbage ts is kept (lenient — do not silently drop data the
    upstream writer didn't timestamp). Future timestamps (clock skew) are also kept."""
    if not ts_value:
        return True
    try:
        dt = datetime.fromisoformat(str(ts_value).replace("Z", "+00:00"))
    except ValueError:
        return True
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age = now - dt
    return age <= timedelta(days=window_days)


def _bucket_records(records) -> dict:
    """Group verdicts by call_site, tracking the counts + inputs_hash groups needed for
    every drift signal in one pass."""
    sites = {}
    for rec in records:
        call_site = str(rec.get("call_site", "unknown"))
        b = sites.setdefault(call_site, {
            "total": 0, "cached": 0, "escalate": 0, "proceed": 0, "revise": 0, "halt": 0,
            "malformed": 0, "overridden": 0, "hash_groups": {},
        })
        b["total"] += 1
        if rec.get("cached"):
            b["cached"] += 1
        recommendation = str(rec.get("recommendation", ""))
        if recommendation == "escalate-to-human":
            b["escalate"] += 1
        elif recommendation in ("proceed", "revise", "halt"):
            b[recommendation] += 1
        reasoning = str(rec.get("reasoning", ""))
        if reasoning.startswith(MALFORMED_PREFIXES):
            b["malformed"] += 1
        if rec.get("caller_action") in OVERRIDE_ACTIONS:
            b["overridden"] += 1
        inputs_hash = rec.get("inputs_hash")
        if inputs_hash:
            b["hash_groups"].setdefault(str(inputs_hash), []).append(recommendation)
    return sites


def _interval_cfg(cfg) -> tuple:
    """`(method, conf)` for the reported intervals, from config — never a constant.

    Which interval to use is the operator's call: `wilson` is the default and the
    primary number; `wilson-cc` reads conservatively at small n; `clopper-pearson`
    guarantees coverage at the cost of width; `jeffreys` is the Bayesian-flavoured
    middle. An unknown name is REFUSED rather than defaulted — silently answering with
    wilson under the name the operator typed is the failure mode this refusal exists
    for."""
    spec = cfg.get("interval") or {}
    method = str(spec.get("method", "wilson"))
    if method not in wilson.METHODS:
        raise ValueError(
            "advisor-audit interval.method %r is not one of %s"
            % (method, ", ".join(wilson.METHODS)))
    return method, float(spec.get("conf", 0.95))


def _rate_ci(k: int, n: int, method: str, conf: float) -> dict:
    """A reported rate, with the counts that produced it and its interval.

    `k`/`n` travel WITH the bounds on purpose: a bare pair of bounds cannot be
    re-derived, re-pooled, or argued with, and the counts are what a reader needs to
    judge whether to gather more. `n == 0` is a real state here (`repeat_rate` divides
    by the number of hash groups) and yields the whole unit interval — a true statement
    about no evidence, not an error."""
    if n <= 0:
        return {"k": 0, "n": 0, "lower": 0.0, "upper": 1.0,
                "method": method, "conf": conf}
    lower, upper = wilson.interval(k, n, conf, method)
    return {"k": int(k), "n": int(n), "lower": lower, "upper": upper,
            "method": method, "conf": conf}


def compute_metrics(sites, cfg) -> dict:
    """Per-call_site drift signals + drift_score. Weights/thresholds come ONLY from cfg
    (R7 — no hardcoded float here).

    Every reported rate carries `k`/`n` and an interval alongside it, and every
    threshold flag has a `_supported` twin saying whether the interval CLEARS the
    threshold. Measured before this existed: `override_high` fired on 1 override out of
    2 calls — a rate of 0.500 whose 95% interval is [0.095, 0.905] — in the same words
    and the same table cell as a 60-of-200 finding. The point-estimate flags are
    unchanged on purpose; quieting them would narrow what the audit reports, which is a
    different (and worse) change than saying how much the evidence weighs."""
    method, conf = _interval_cfg(cfg)
    metrics = {}
    for call_site, b in sites.items():
        total = b["total"]
        override_rate = b["overridden"] / total
        malformed_rate = b["malformed"] / total
        hash_groups = b["hash_groups"]
        repeat_hashes = [h for h, recs in hash_groups.items() if len(recs) >= cfg["repeat_prompt"]]
        repeat_rate = (len(repeat_hashes) / len(hash_groups)) if hash_groups else 0.0
        flipped_hashes = [h for h, recs in hash_groups.items() if len(set(recs)) > 1]
        flipped_records = sum(len(hash_groups[h]) for h in flipped_hashes)
        flipped_pct = flipped_records / total
        override_ci = _rate_ci(b["overridden"], total, method, conf)
        malformed_ci = _rate_ci(b["malformed"], total, method, conf)
        repeat_ci = _rate_ci(len(repeat_hashes), len(hash_groups), method, conf)
        flipped_ci = _rate_ci(flipped_records, total, method, conf)
        drift_score = (
            override_rate * cfg["w_override"]
            + flipped_pct * cfg["w_flipped"]
            + malformed_rate * cfg["w_malformed"]
            + repeat_rate * cfg["w_repeat"]
        )
        metrics[call_site] = {
            "total": total, "cached": b["cached"], "escalate": b["escalate"],
            "proceed": b["proceed"], "revise": b["revise"], "halt": b["halt"],
            "malformed": b["malformed"], "overridden": b["overridden"],
            "override_rate": override_rate, "malformed_rate": malformed_rate,
            "repeat_rate": repeat_rate, "flipped_pct": flipped_pct,
            "override_rate_ci": override_ci, "malformed_rate_ci": malformed_ci,
            "repeat_rate_ci": repeat_ci, "flipped_pct_ci": flipped_ci,
            "flipped_hashes": flipped_hashes, "drift_score": drift_score,
            "flags": {
                "override_high": override_rate > cfg["override_rate"],
                "malformed_high": malformed_rate > cfg["malformed_rate"],
                "repeat_prompt": len(repeat_hashes) > 0,
                "flipped_verdict": len(flipped_hashes) > 0,
                # The interval's LOWER bound clears the threshold — i.e. the evidence
                # rules out "at or below the threshold" at the configured confidence.
                # A flag whose twin here is False is a real observation on evidence too
                # thin to carry it; the report says so rather than leaving a reader to
                # weigh 1-of-2 the same as 60-of-200.
                "override_high_supported": override_ci["lower"] > cfg["override_rate"],
                "malformed_high_supported": malformed_ci["lower"] > cfg["malformed_rate"],
            },
        }
    return metrics


def compute_sigma_escalations(metrics, cfg) -> list:
    """A call_site's drift_score is compared against the MEAN + STDDEV of every
    call_site's drift_score in this same window (no persisted cross-run baseline exists
    yet — wiring that is a follow-up, see the phase's open question). With fewer than 2
    call_sites, or zero spread, sigma cannot be meaningfully computed -> no escalation
    (never fabricate a baseline)."""
    scores = [m["drift_score"] for m in metrics.values()]
    if len(scores) < 2:
        return []
    mu = mean(scores)
    sigma = pstdev(scores)
    if sigma == 0:
        return []
    escalations = []
    for call_site, m in metrics.items():
        z = (m["drift_score"] - mu) / sigma
        if z > cfg["sigma"]:
            escalations.append({
                "call_site": call_site, "drift_score": m["drift_score"],
                "z": z, "sigma_threshold": cfg["sigma"],
            })
    return sorted(escalations, key=lambda e: -e["z"])


def build_escalation_notes(sigma_escalations, actor, ts) -> list:
    """One combined escalation note per run when any call_site crosses 3 sigma — routed
    to the maintainer (human), never back to the Advisor (self-review anti-pattern)."""
    if not sigma_escalations:
        return []
    date = str(ts)[:10] or "unknown-date"
    lines = [
        "# Advisor Drift Escalation — %s" % date, "",
        "Escalate to the maintainer (human) -- do NOT route back to the Advisor.", "",
    ]
    for esc in sigma_escalations:
        lines.append("- **%s** -- drift_score=%.2f, z=%.2f (> %sσ baseline)" % (
            esc["call_site"], esc["drift_score"], esc["z"], esc["sigma_threshold"]))
    lines.extend(["", "actor: %s" % actor, "ts: %s" % ts])
    return [{"filename": "drift-%s.md" % date, "content": "\n".join(lines) + "\n"}]


def _fmt_rate(rate: float, ci: dict) -> str:
    """`k/n rate [lo, hi]` — the three things a rate claim owes a reader, in one cell.
    Bounds at 3 decimals because a 2-decimal interval on a small n collapses to
    [0.00, 1.00] and reads as a formatting bug rather than as the honest answer."""
    return "%d/%d %.2f [%.3f, %.3f]" % (ci["k"], ci["n"], rate, ci["lower"], ci["upper"])


def render_report(status, metrics, flipped_call_sites, sigma_escalations, cfg, actor, ts) -> str:
    if status == "sink-not-wired":
        return "sink not wired\n"
    has_anomaly = bool(flipped_call_sites or sigma_escalations or any(
        m["flags"]["override_high"] or m["flags"]["malformed_high"] or m["flags"]["repeat_prompt"]
        for m in metrics.values()))
    lines = ["# Advisor Audit Report"]
    lines.append("actor: %s | ts: %s" % (actor, ts))
    lines.append("")
    lines.append("no anomalies" if not has_anomaly else "anomalies detected")
    lines.append("")
    # Each rate is shown as `k/n rate [lo, hi]`. The counts are not decoration: they
    # are what lets a reader tell a finding worth acting on from one worth sampling
    # more of, and a bare rate cannot be re-pooled or argued with.
    lines.append("| call_site | total | override_rate | malformed_rate | repeat_rate | drift_score | flags |")
    lines.append("|---|---|---|---|---|---|---|")
    for call_site in sorted(metrics):
        m = metrics[call_site]
        flags = []
        if m["flags"]["override_high"]:
            flags.append("override-high" if m["flags"]["override_high_supported"]
                          else "override-high (UNSUPPORTED at n=%d)" % m["override_rate_ci"]["n"])
        if m["flags"]["malformed_high"]:
            flags.append("malformed-high" if m["flags"]["malformed_high_supported"]
                          else "malformed-high (UNSUPPORTED at n=%d)" % m["malformed_rate_ci"]["n"])
        if m["flags"]["repeat_prompt"]:
            flags.append("repeat-prompt")
        if m["flags"]["flipped_verdict"]:
            flags.append("flipped-verdict")
        lines.append("| %s | %d | %s | %s | %s | %.2f | %s |" % (
            call_site, m["total"],
            _fmt_rate(m["override_rate"], m["override_rate_ci"]),
            _fmt_rate(m["malformed_rate"], m["malformed_rate_ci"]),
            _fmt_rate(m["repeat_rate"], m["repeat_rate_ci"]),
            m["drift_score"], ", ".join(flags) or "-"))
    unsupported = sorted(
        cs for cs, m in metrics.items()
        if (m["flags"]["override_high"] and not m["flags"]["override_high_supported"])
        or (m["flags"]["malformed_high"] and not m["flags"]["malformed_high_supported"]))
    if unsupported:
        ci = metrics[unsupported[0]]["override_rate_ci"]
        lines.append("")
        lines.append("> **UNSUPPORTED** marks a flag its own evidence cannot carry: the "
                      "%s %g%% interval still includes the threshold, so the rate is not "
                      "distinguishable from an acceptable one. Gather more calls before "
                      "acting: %s." % (ci["method"], ci["conf"] * 100, ", ".join(unsupported)))
    if flipped_call_sites:
        lines.append("")
        lines.append("## Escalations -- flipped verdict (zero tolerance)")
        for call_site in flipped_call_sites:
            lines.append("- %s: flipped recommendation on an identical inputs_hash -- "
                          "escalate to the maintainer" % call_site)
    if sigma_escalations:
        lines.append("")
        lines.append("## Escalations -- drift > %sσ baseline" % cfg["sigma"])
        for esc in sigma_escalations:
            lines.append("- %s: z=%.2f -- escalate to the maintainer (see escalation note)"
                          % (esc["call_site"], esc["z"]))
    return "\n".join(lines) + "\n"


def run_audit(sink_path=None, config=None, *, actor=None, ts=None, now=None) -> dict:
    """Run one audit pass end-to-end. Never raises for a data-shape problem (bad sink
    content) -- only a caller error (bad config path type etc.) can. Returns a plain
    dict, JSON-serializable as-is."""
    cfg = config if isinstance(config, dict) else load_config(config)
    resolved_sink = sink_path if sink_path is not None else cfg["sink_path"]
    resolved_actor = actor or _actor()
    resolved_ts = ts or datetime.now(timezone.utc).isoformat()
    now_dt = now or datetime.now(timezone.utc)

    records, is_wired = read_sink(resolved_sink)
    if not is_wired:
        return {
            "actor": resolved_actor, "ts": resolved_ts, "sink_wired": False,
            "status": "sink-not-wired", "call_sites": {},
            "escalations": {"flipped": [], "sigma": []},
            "escalation_notes": [],
            "report": render_report("sink-not-wired", {}, [], [], cfg, resolved_actor, resolved_ts),
        }

    windowed = [r for r in records if _within_window(r.get("ts"), now_dt, cfg["window_days"])]
    sites = _bucket_records(windowed)
    metrics = compute_metrics(sites, cfg)
    flipped_call_sites = sorted(cs for cs, m in metrics.items() if m["flags"]["flipped_verdict"])
    sigma_escalations = compute_sigma_escalations(metrics, cfg)
    escalation_notes = build_escalation_notes(sigma_escalations, resolved_actor, resolved_ts)
    status = "anomalies" if (flipped_call_sites or sigma_escalations or any(
        m["flags"]["override_high"] or m["flags"]["malformed_high"] or m["flags"]["repeat_prompt"]
        for m in metrics.values())) else "no-anomalies"

    return {
        "actor": resolved_actor, "ts": resolved_ts, "sink_wired": True, "status": status,
        "call_sites": metrics,
        "escalations": {"flipped": flipped_call_sites, "sigma": sigma_escalations},
        "escalation_notes": escalation_notes,
        "report": render_report(status, metrics, flipped_call_sites, sigma_escalations,
                                 cfg, resolved_actor, resolved_ts),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Advisory drift review of Advisor verdicts.")
    ap.add_argument("--sink", default=None, help="path to the verdict JSONL sidecar (default: config sink_path)")
    ap.add_argument("--config", default=None, help="advisor-audit.yaml (default: harness/data/advisor-audit.yaml)")
    ap.add_argument("--out", default=None, help="optional path to also write the report to")
    ap.add_argument("--format", default="md", choices=["md", "json"], help="report format")
    ap.add_argument("--escalation-dir", default=None, help="optional dir to write escalation note file(s) to")
    args = ap.parse_args(argv)

    result = run_audit(sink_path=args.sink, config=args.config)

    if args.format == "json":
        serializable = dict(result)
        text = json.dumps(serializable, indent=2, ensure_ascii=False) + "\n"
    else:
        text = result["report"]
    sys.stdout.write(text)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")

    if args.escalation_dir and result["escalation_notes"]:
        out_dir = Path(args.escalation_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for note in result["escalation_notes"]:
            (out_dir / note["filename"]).write_text(note["content"], encoding="utf-8")

    return 0  # advisory / non-blocking: never a non-zero exit for audit findings (R5)


if __name__ == "__main__":
    sys.exit(main())
