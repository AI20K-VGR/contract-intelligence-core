#!/usr/bin/env python3
"""grid_flag_carry.py — carry `--grid` plan -> cook, deterministic + 0 model.

Mirrors the existing `--tdd` carry pattern (`harness/plugins/hs/skills/cook/SKILL.md`
Flags-carried block): `hs:plan --grid` stamps `grid: true` into `plan.md`
frontmatter; cook reads that marker here so it can auto-inherit micro-grid
review WITHOUT the user retyping `--grid`. The carry is always SURFACED to the
user — this module returns a one-line surface string on carry and `None` when
absent, never a silent flip.

THIRD door on the activation decision (the other two: grid_emit_guard's CLI
--require, and plan_approval.write_approval). All three now read
grid_emit_guard.resolve_grid_mode — the single source of truth — so a plan
whose evidence on disk implies grid mode (no working `grid:` declaration, but
engine-emitted artifacts present) carries here too, closing the hole where
cook/SKILL.md's Step 0.5 preflight (its old wording gated the presence check
on a literal `grid: true` declaration) never even invoked the presence gate
for exactly the case that gate exists to catch. SKILL.md's wording has since
been fixed to fire on this module's own carry decision (declared OR
evidence-inferred), not a literal `grid: true` line.

Life-critical constraint (R3): carrying `grid: true` enables ONLY the 0-token
micro-grid review. This module has NO code path that sets, reads, or pulls the
fill-loop auto flag — grid carry and that flag are unrelated concerns, and the
drift test (`harness/tests/test_grid_flag_carry.py`) asserts that fact directly
against this file's source (the literal flag spelling is absent), not
just its behavior.

Usage:
    python3 harness/scripts/grid_flag_carry.py --plan <plan_dir>

Exit 0 always — this is an advisory/informational resolver, not a gate.
"""
import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import grid_emit_guard  # noqa: E402

SURFACE_LINE = "grid carried from plan"


def resolve_grid_carry(plan_dir) -> dict:
    """Read the activation decision via `grid_emit_guard.resolve_grid_mode` —
    the shared ground truth all three doors now read.

    Returns a dict:
        {
          "carried": bool,      # resolve_grid_mode's `enabled`
          "surface": str|None,  # the mandatory surface line, or None when absent
          "reason": str,        # human-readable explanation (debugging/CLI)
        }
    """
    enabled, reason, _evidence = grid_emit_guard.resolve_grid_mode(plan_dir)
    if enabled:
        return {
            "carried": True,
            "surface": SURFACE_LINE,
            "reason": reason,
        }
    return {
        "carried": False,
        "surface": None,
        "reason": reason,
    }


def format_result(result: dict) -> str:
    """Render the resolver result as the CLI's human-readable stdout. Carried
    output prints the mandatory surface line; absent/false stays silent about
    grid (no surface line) — the carry rule is "surfaced when true, silent
    when false", never the reverse."""
    lines = ["carried: %s" % ("true" if result["carried"] else "false")]
    if result["carried"]:
        lines.append(result["surface"])
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Resolve whether --grid carries from a plan's frontmatter "
                    "into cook (deterministic, 0 model; never sets the auto-fill flag).")
    parser.add_argument("--plan", required=True, help="plan directory (contains plan.md)")
    args = parser.parse_args(argv)

    result = resolve_grid_carry(args.plan)
    print(format_result(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
