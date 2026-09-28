#!/usr/bin/env python3
"""auto_finalize_ship.py — PreToolUse(Skill) hook: ship-belt backstop that
finalizes the single active plan when N/N phases have a PASS snapshot.

Layer 2 to phase_progress_writer's Layer 1. The writer closes a plan at the
moment its FINAL phase verification is written. But a run can reach hs:ship by a
path where that last write never fired the hook (an out-of-band edit, a hook miss,
a resumed session). This belt re-checks at the publish boundary: resolve the ONE
active plan (resolve_active_plan — never a corpus scan) and finalize it, gated on
the same derived N/N evidence. Complete -> close; incomplete -> benign no-op.

Scoped to hs:ship / ship only — NOT hs:git, whose mid-cook commits would
otherwise trigger an early close. Shares the HARNESS_AUTO_FINALIZE kill-switch
with the writer (one knob, both seams). Telemetry-class: fail-open, never blocks.

Hook stdin protocol: { tool_name: "Skill", tool_input: { skill }, ... }.
"""

import os
import sys
from pathlib import Path

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_LIB_DIR = os.path.join(_HOOKS_DIR, "..", "scripts")
sys.path.insert(0, _LIB_DIR)
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import hook_runtime  # noqa: E402
import harness_paths  # noqa: E402
import artifact_check  # noqa: E402
import phase_progress_writer  # noqa: E402  (shared kill-switch)

HOOK_CLASS = "telemetry"

_STEM = Path(__file__).stem

# The publish skills this belt fires on. hs:git is deliberately EXCLUDED: cook
# commits each phase via hs:git, and closing there would be an early close.
_SHIP_SKILLS = {"hs:ship", "ship"}


def _incoming_skill(data: dict) -> str:
    if (data or {}).get("tool_name") != "Skill":
        return ""
    inp = data.get("tool_input") or {}
    return str(inp.get("skill") or inp.get("name") or "")


def core(data: dict) -> None:
    if _incoming_skill(data) not in _SHIP_SKILLS:
        return
    if not phase_progress_writer.auto_finalize_enabled():
        return
    # The active plan lives in the PROJECT's plans/, not the shared bin's:
    # under a global install root() found nothing, so the ship backstop was a
    # silent no-op and the plan stayed open. Last unmigrated site of that
    # class (gate_stage and both plan nudges already resolve project-aware).
    root = harness_paths.project_root()
    plan_dir = artifact_check.resolve_active_plan(root)
    if plan_dir is None:
        return  # no single active plan (none, or ambiguous) -> no-op, no sweep
    from finalize_plan import finalize_plan
    res = finalize_plan(plan_dir, root=root)
    if res.changed:
        sys.stderr.write("[auto-finalize] closed %s at ship (N/N phases PASS)\n"
                         % Path(plan_dir).name)


def main(raw=None) -> None:
    hook_runtime.run_telemetry_hook(_STEM, core, raw=raw)


if __name__ == "__main__":
    main()
