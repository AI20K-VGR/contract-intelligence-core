#!/usr/bin/env python3
"""defer_suite_carry.py — carry `defer_suite` plan -> cook, deterministic + 0 model.

Mirrors `grid_flag_carry.py` in shape: `hs:plan --defer-suite` stamps
`defer_suite: true` into `plan.md` frontmatter; cook reads that marker here so
it can auto-inherit the deferred-suite behavior WITHOUT the user retyping the
flag. The carry is always SURFACED to the user on carry, and silent when
absent — never a silent flip.

DELIBERATELY UNLIKE `grid_flag_carry`: no disk-evidence inference path. `grid`
infers activation from engine-emitted artifacts on disk when the frontmatter
key is silent (see `grid_emit_guard.py`'s own activation resolver);
`defer_suite` never does — deferring the suite is a consent decision, and no
artifact on disk can imply a user consented to skip verification. This module
reads ONLY the plan's own frontmatter declaration. Three states:
    `defer_suite: true`  -> carried
    `defer_suite: false` or absent -> not carried
    frontmatter unparseable -> not carried, fail closed, reason names the
        parse error (no readable consent means no consent)

Usage:
    python3 harness/scripts/defer_suite_carry.py --plan <plan_dir>

Exit 0 always — this is an advisory/informational resolver, not a gate. Never
raises.
"""
import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import frontmatter_parser  # noqa: E402

SURFACE_LINE = "defer_suite carried from plan"


def resolve_defer_suite_carry(plan_dir) -> dict:
    """Read `plan.md`'s own frontmatter — the ONLY source of truth for this
    flag, by design (no evidence-inference door, unlike `grid_flag_carry`).

    Returns a dict:
        {
          "carried": bool,      # frontmatter defer_suite is True (strict)
          "surface": str|None,  # the mandatory surface line, or None when absent
          "reason": str,        # human-readable explanation (debugging/CLI)
        }
    Never raises: an unreadable plan dir, a missing plan.md, or unparseable
    frontmatter all degrade to carried=False with a reason naming why.
    """
    plan_md = Path(plan_dir) / "plan.md"
    parsed = frontmatter_parser.parse_file(plan_md)
    if not parsed.get("ok"):
        return {
            "carried": False,
            "surface": None,
            "reason": "plan.md frontmatter did not parse: %s"
                      % (parsed.get("error") or "unknown error"),
        }
    fm = parsed.get("frontmatter") or {}
    value = fm.get("defer_suite")
    if value is True:
        return {
            "carried": True,
            "surface": SURFACE_LINE,
            "reason": "plan.md frontmatter declares defer_suite: true",
        }
    if value is False:
        return {
            "carried": False,
            "surface": None,
            "reason": "plan.md frontmatter declares defer_suite: false (explicit opt-out)",
        }
    return {
        "carried": False,
        "surface": None,
        "reason": "plan.md frontmatter does not declare defer_suite",
    }


def format_result(result: dict) -> str:
    """Render the resolver result as the CLI's human-readable stdout. Carried
    output prints the mandatory surface line; absent/false stays silent about
    defer_suite (no surface line) — surfaced when true, silent when false,
    never the reverse."""
    lines = ["carried: %s" % ("true" if result["carried"] else "false")]
    if result["carried"]:
        lines.append(result["surface"])
    else:
        # `carried: false` alone is three situations in one word: the plan opted
        # out, the plan never mentioned the flag, or the plan could not be READ.
        # The third is a fail-closed default that reads exactly like consent to
        # run the full suite. The distinguishing sentence was already computed
        # and then dropped on the floor.
        lines.append("reason: %s" % result["reason"])
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Resolve whether defer_suite carries from a plan's frontmatter "
                    "into cook (deterministic, 0 model; declared consent only, "
                    "never inferred from disk evidence).")
    parser.add_argument("--plan", required=True, help="plan directory (contains plan.md)")
    args = parser.parse_args(argv)

    result = resolve_defer_suite_carry(args.plan)
    print(format_result(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
