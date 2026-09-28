#!/usr/bin/env python3
"""autonomy_policy.py — resolve HARNESS_AUTONOMY into a per-boundary pause decision.

hs:cook runs a plan phase by phase. WHERE it stops to wait for a human is the
HARNESS_AUTONOMY knob (default|ask_all|god) that README / docs / cook / showcase all
describe. This module is the single code source of truth for that knob, so cook
consults a deterministic answer instead of re-interpreting prose each run.

  - default : pause at plan-approval + ship (the everyday cadence)
  - ask_all : also pause after EVERY phase (cautious / review-heavy)
  - god     : no VOLUNTARY pause (maximum autonomy)

This governs only cook's voluntary stop-to-ask cadence. It does NOT lower a hard
stage gate: stage push|pr|ship|deploy still goes through gate_stage regardless of
level, so even `god` cannot self-ship past the artifact gate. Attribution, not
authorization — the knob is env-derived and spoofable; it tunes prompts, not gates.

Fail-safe: a missing OR unrecognized level resolves to `default`, and an unknown
boundary pauses — the resolver never silently drops a stop it cannot account for.

CLI:
  autonomy_policy.py --boundary <plan_approval|phase|ship>   # prints pause|continue
  autonomy_policy.py --show                                  # JSON {level, pauses}
"""
import argparse
import json
import os
import sys

DEFAULT_LEVEL = "default"

# level -> boundary -> pause?  The voluntary cadence cook adds on top of the hard
# gates. Matches cook/SKILL.md "Pause cadence" and harness-contract.md.
PAUSE_MATRIX = {
    "default": {"plan_approval": True,  "phase": False, "ship": True},
    "ask_all": {"plan_approval": True,  "phase": True,  "ship": True},
    "god":     {"plan_approval": False, "phase": False, "ship": False},
}

LEVELS = tuple(PAUSE_MATRIX)


def resolve_level(env=None) -> str:
    """The active autonomy level. Reads HARNESS_AUTONOMY; an absent or unrecognized
    value resolves to DEFAULT_LEVEL (fail-safe — never silently disable a pause)."""
    src = os.environ if env is None else env
    raw = (src.get("HARNESS_AUTONOMY") or "").strip()
    return raw if raw in PAUSE_MATRIX else DEFAULT_LEVEL


def should_pause(boundary: str, level=None) -> bool:
    """Should cook pause for a human at this boundary under `level`?

    boundary is one of plan_approval | phase | ship. An unknown boundary pauses
    (safe default). `level` defaults to the resolved env level when omitted.
    """
    lvl = resolve_level() if level is None else level
    if lvl not in PAUSE_MATRIX:
        lvl = DEFAULT_LEVEL
    return PAUSE_MATRIX[lvl].get(boundary, True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Resolve HARNESS_AUTONOMY pause policy.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--boundary", choices=("plan_approval", "phase", "ship"),
                   help="print 'pause' or 'continue' for this boundary")
    g.add_argument("--show", action="store_true",
                   help="emit the resolved level + full pause matrix as JSON")
    args = ap.parse_args(argv)

    level = resolve_level()
    if args.show:
        sys.stdout.write(json.dumps({"level": level, "pauses": PAUSE_MATRIX[level]}))
        sys.stdout.write("\n")
        return 0
    sys.stdout.write("pause\n" if should_pause(args.boundary, level) else "continue\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
