#!/usr/bin/env python3
"""bakeoff_rank.py — mechanical verdict for an empirical bake-off.

Given per-candidate trial scores, decide a winner OR refuse to. The refusal is the
whole point: an LLM reading a scoreboard will always tell a story for why the top
number wins; this code stays silent when the gap between the top two candidates sits
inside the measured noise band. Three verdicts only:

  winner            — the best candidate beats the runner-up by more than the noise band.
  tie_within_noise  — the gap is inside the band; hand to a human, do not invent a winner.
  insufficient_trials — too few trials for the declared noise level to claim anything.

Noise vocabulary is reused from hs:loop (Direction/Noise) so the two skills share one
ruler. No t-tests or p-values: at n<=5 they are pseudo-science. The honesty mechanism is
`band = max(relative_band, observed_spread)` — if every candidate already swings wildly
between trials, a small gap between candidates cannot be a real win.

Layout: pure verdict logic first (no I/O), then the ledger / preflight / CLI layer.
"""
import argparse
import json
import os
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import harness_paths  # noqa: E402

_HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.append(str(_HOOKS_DIR))
import hook_runtime  # noqa: E402

_DIRECTIONS = ("lower", "higher")
_MIN_TRIALS = {"low": 1, "medium": 2, "high": 3}


# ==================================================== pure verdict logic ======

def min_trials(noise: str) -> int:
    """Minimum trials per candidate before a winner may be claimed at this noise."""
    try:
        return _MIN_TRIALS[noise]
    except KeyError:
        raise ValueError("noise must be one of %s, got %r" % (list(_MIN_TRIALS), noise))


def representative(trials, noise: str, direction: str) -> float:
    """Collapse a candidate's trials to one comparable number.

    medium -> the WORSE of the trials (conservative): lower-is-better keeps the max,
    higher-is-better keeps the min. low/high -> the median (robust to one outlier).
    """
    vals = [float(t) for t in trials]
    if not vals:
        raise ValueError("representative() needs at least one trial")
    if direction not in _DIRECTIONS:
        raise ValueError("direction must be one of %s, got %r" % (list(_DIRECTIONS), direction))
    if noise == "medium":
        return max(vals) if direction == "lower" else min(vals)
    min_trials(noise)  # validate noise even on the median path
    return float(statistics.median(vals))


def spread(trials) -> float:
    """Observed run-to-run noise for one candidate: max - min across its trials."""
    vals = [float(t) for t in trials]
    return max(vals) - min(vals)


def compute_verdict(scores: dict, *, direction: str = "lower",
                    noise: str = "medium", rel_band: float = 0.05) -> dict:
    """Decide winner / tie_within_noise / insufficient_trials from raw scores.

    scores: {candidate_name: [trial_value, ...]} with 2..4 candidates.
    Returns a verdict dict (no actor/ts — the I/O layer stamps those).
    """
    if direction not in _DIRECTIONS:
        raise ValueError("direction must be one of %s, got %r" % (list(_DIRECTIONS), direction))
    need = min_trials(noise)  # validates noise
    names = list(scores)
    if not 2 <= len(names) <= 4:
        raise ValueError("bake-off needs 2..4 candidates, got %d" % len(names))

    rep, spr, ntrials = {}, {}, {}
    for name in names:
        trials = scores[name]
        if not trials:
            raise ValueError("candidate %r has no trials" % name)
        rep[name] = representative(trials, noise, direction)
        spr[name] = spread(trials)
        ntrials[name] = len(trials)

    # best-first: ascending rep for lower-is-better, descending for higher-is-better.
    ranking = sorted(names, key=lambda c: rep[c])
    if direction == "higher":
        ranking = ranking[::-1]
    best, second = ranking[0], ranking[1]

    observed_spread_floor = max(spr.values())
    band = max(rel_band * abs(rep[best]), observed_spread_floor)
    gap = (rep[second] - rep[best]) if direction == "lower" else (rep[best] - rep[second])

    insufficient = any(ntrials[c] < need for c in names)
    if insufficient:
        verdict, winner = "insufficient_trials", None
        rationale = ("need >= %d trials/candidate at noise=%s; some candidate has fewer "
                     "-> hand to human" % (need, noise))
    elif gap > band:
        verdict, winner = "winner", best
        rationale = "gap %.4g > band %.4g -> %s wins" % (gap, band, best)
    else:
        verdict, winner = "tie_within_noise", None
        rationale = ("gap %.4g <= band %.4g (max of %.0f%% relative and observed spread "
                     "%.4g) -> tie within noise" % (gap, band, rel_band * 100,
                                                     observed_spread_floor))

    candidates = [{
        "candidate": c,
        "trials": [float(t) for t in scores[c]],
        "rep": rep[c],
        "spread": spr[c],
        "n": ntrials[c],
    } for c in ranking]

    return {
        "direction": direction,
        "noise": noise,
        "rel_band": rel_band,
        "candidates": candidates,
        "ranking": ranking,
        "observed_spread_floor": observed_spread_floor,
        "band": band,
        "gap": gap,
        "verdict": verdict,
        "winner": winner,
        "rationale": rationale,
    }


# ==================================================== ledger (append-only) ====
# Per-run JSONL under state_dir()/bakeoff/. Append only, never read-modify-write —
# every record carries actor + aware-UTC ts, matching the harness store contract.

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _validate_run_id(run_id: str) -> str:
    if (not isinstance(run_id, str) or run_id in (".", "..")
            or not _RUN_ID_RE.match(run_id)):
        raise ValueError("invalid run id %r (allowed: letters, digits, . _ -)" % (run_id,))
    return run_id


def ledger_path(run_id: str) -> Path:
    _validate_run_id(run_id)  # reject before any fs touch
    return harness_paths.state_dir() / "bakeoff" / (run_id + ".jsonl")


def record_score(run_id, candidate, trial, value, *, elapsed_s=None, tokens=None,
                 actor=None, ts=None) -> dict:
    """Append one trial score to the run ledger. elapsed_s = wall-time (always
    mechanical); tokens = real subagent_tokens or None for an inline probe (never faked)."""
    path = ledger_path(run_id)  # validates run_id first
    rec = {
        "run": run_id,
        "candidate": str(candidate),
        "trial": int(trial),
        "value": float(value),
        "elapsed_s": float(elapsed_s) if elapsed_s is not None else None,
        "tokens": int(tokens) if tokens is not None else None,
        "actor": actor or hook_runtime.resolve_actor(),
        "ts": ts or datetime.now(timezone.utc).isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def read_records(run_id: str) -> list:
    """All well-formed score records for a run; malformed lines skipped (fail-soft)."""
    path = ledger_path(run_id)
    out = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and "candidate" in rec and "value" in rec:
            out.append(rec)
    return out


def read_scores(run_id: str) -> dict:
    """{candidate: [value, ...]} grouped, each candidate's values in trial order.

    A record whose `trial` is NOT a valid int is untrustworthy and is SKIPPED — never
    coerced to a default sort position (which let a malformed-trial record corrupt the
    ordering AND inject its value into the representative, producing false winners)."""
    rows = []
    for rec in read_records(run_id):
        try:
            trial = int(rec.get("trial"))
            value = float(rec["value"])
        except (TypeError, ValueError, KeyError):
            continue
        rows.append((str(rec.get("candidate", "")), trial, value))
    scores = {}
    for cand, _trial, value in sorted(rows, key=lambda r: (r[0], r[1])):
        scores.setdefault(cand, []).append(value)
    return scores


# ==================================================== budget (time+tokens) ====

def over_budget(records, *, budget_seconds=None, budget_tokens=None) -> list:
    """Candidates that breached EITHER ceiling. A trial with tokens=None is skipped on
    the token axis (unknown != over) so an inline probe is never falsely flagged."""
    flagged = []
    for rec in records:
        cand = rec.get("candidate")
        if cand in flagged:
            continue
        es, tk = rec.get("elapsed_s"), rec.get("tokens")
        breach = (budget_seconds is not None and es is not None and float(es) > budget_seconds) \
            or (budget_tokens is not None and tk is not None and float(tk) > budget_tokens)
        if breach:
            flagged.append(cand)
    return flagged


# ==================================================== preflight (gate) =========
# The machine-checkable half of the gate-first preconditions. Judgment calls
# (is this a stub? is the decision load-bearing?) stay in the skill checklist.

_UNSAFE = [
    re.compile(r"\brm\s+-[a-zA-Z]*\s+(?:/|\$HOME|~)(?:\s|/|\*|$)"),   # rm -rf / | $HOME | ~
    re.compile(r"(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:ba)?sh\b"),  # curl|sh, wget|bash
    re.compile(r":\(\)\s*\{.*\|.*&\s*\};"),                            # fork bomb
]


def _unsafe(cmd: str) -> bool:
    return any(p.search(cmd) for p in _UNSAFE)


def preflight(candidates, metric_cmd, *, budget_seconds=None, budget_tokens=None,
              ceiling_seconds=600.0, ceiling_tokens=2_000_000) -> dict:
    """Refuse to start a bake-off unless the static preconditions hold. Collects ALL
    failure reasons so the user fixes everything in one pass. Does NOT run metric_cmd —
    the skill dry-runs it once (exit 0 + one number, same contract as hs:loop)."""
    reasons = []
    uniq = list(dict.fromkeys(candidates or []))
    if not 2 <= len(uniq) <= 4:
        reasons.append("need 2..4 distinct candidates, got %d" % len(uniq))
    if not metric_cmd or not str(metric_cmd).strip():
        reasons.append("metric command is empty")
    elif _unsafe(str(metric_cmd)):
        reasons.append("metric command matches an unsafe pattern (rm -rf /, curl|sh, ...)")
    if budget_seconds is None and budget_tokens is None:
        reasons.append("at least one of budget_seconds / budget_tokens is required")
    if budget_seconds is not None and not (0 < budget_seconds <= ceiling_seconds):
        reasons.append("budget_seconds must be in (0, %g]" % ceiling_seconds)
    if budget_tokens is not None and not (0 < budget_tokens <= ceiling_tokens):
        reasons.append("budget_tokens must be in (0, %d]" % ceiling_tokens)
    return {"ok": not reasons, "reasons": reasons}


# ==================================================== verdict artifact =========

_REQUIRED = ("schema", "run", "direction", "noise", "verdict", "candidates",
             "ranking", "band", "gap", "actor", "ts")


def build_verdict(run_id, *, direction="lower", noise="medium", rel_band=0.05,
                  budget_seconds=None, budget_tokens=None, actor=None, ts=None) -> dict:
    """Read the run ledger, compute the verdict, stamp schema/run/actor/ts + over-budget,
    and self-check required fields are present (mirrors artifact_check's minimal validation)."""
    records = read_records(run_id)
    v = compute_verdict(read_scores(run_id), direction=direction, noise=noise, rel_band=rel_band)
    v["schema"] = "artifact-bakeoff-verdict"
    v["run"] = run_id
    v["actor"] = actor or hook_runtime.resolve_actor()
    v["ts"] = ts or datetime.now(timezone.utc).isoformat()
    v["over_budget"] = over_budget(records, budget_seconds=budget_seconds,
                                   budget_tokens=budget_tokens)
    missing = [k for k in _REQUIRED if k not in v]
    if missing:
        raise ValueError("verdict missing required fields: %s" % ", ".join(missing))
    return v


def write_verdict(plan_dir, verdict: dict) -> Path:
    path = Path(plan_dir) / "bakeoff-verdict.json"
    path.write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


# ==================================================== CLI ======================
# Exit codes let the skill branch without parsing prose:
#   preflight: 0 ok / 2 refuse        rank: 0 winner / 3 tie / 4 insufficient / 5 malformed

_EXIT = {"winner": 0, "tie_within_noise": 3, "insufficient_trials": 4}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="bakeoff_rank.py",
        description="Mechanical empirical bake-off: record per-candidate scores, then "
                    "rank — declaring a winner only when it beats the runner-up beyond "
                    "the measured noise band.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pf = sub.add_parser("preflight", help="check preconditions before burning tokens")
    pf.add_argument("--candidate", action="append", default=[])
    pf.add_argument("--metric-cmd", required=True)
    pf.add_argument("--budget-seconds", type=float)
    pf.add_argument("--budget-tokens", type=int)
    pf.add_argument("--ceiling-seconds", type=float, default=600.0)
    pf.add_argument("--ceiling-tokens", type=int, default=2_000_000)

    rc = sub.add_parser("record", help="append one trial score to the run ledger")
    rc.add_argument("--run", required=True)
    rc.add_argument("--candidate", required=True)
    rc.add_argument("--trial", type=int, required=True)
    rc.add_argument("--value", type=float, required=True)
    rc.add_argument("--elapsed-s", type=float)
    rc.add_argument("--tokens", type=int)

    rk = sub.add_parser("rank", help="compute the verdict from the run ledger")
    rk.add_argument("--run", required=True)
    rk.add_argument("--direction", default="lower", choices=["lower", "higher"])
    rk.add_argument("--noise", default="medium", choices=["low", "medium", "high"])
    rk.add_argument("--rel-band", type=float, default=0.05)
    rk.add_argument("--plan-dir")
    rk.add_argument("--budget-seconds", type=float)
    rk.add_argument("--budget-tokens", type=int)

    args = parser.parse_args(argv)

    if args.cmd == "preflight":
        res = preflight(args.candidate, args.metric_cmd,
                        budget_seconds=args.budget_seconds, budget_tokens=args.budget_tokens,
                        ceiling_seconds=args.ceiling_seconds, ceiling_tokens=args.ceiling_tokens)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res["ok"] else 2

    if args.cmd == "record":
        rec = record_score(args.run, args.candidate, args.trial, args.value,
                           elapsed_s=args.elapsed_s, tokens=args.tokens)
        print(json.dumps(rec, ensure_ascii=False))
        return 0

    if args.cmd == "rank":
        try:
            v = build_verdict(args.run, direction=args.direction, noise=args.noise,
                              rel_band=args.rel_band, budget_seconds=args.budget_seconds,
                              budget_tokens=args.budget_tokens)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
            return 5
        if args.plan_dir:
            write_verdict(args.plan_dir, v)
        print(json.dumps(v, ensure_ascii=False, indent=2))
        return _EXIT.get(v["verdict"], 1)

    return 1


if __name__ == "__main__":
    sys.exit(main())
