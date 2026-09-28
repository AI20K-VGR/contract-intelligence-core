#!/usr/bin/env python3
"""phase_progress_writer.py — PostToolUse hook: per-phase evidence snapshot +
plan lifecycle (auto-open, auto-close).

A plan's canonical verification.{json,yaml} is OVERWRITTEN every phase (it is the
current-phase verdict the gate reads O(1)). That makes it useless for "are all N
phases done?" — by the time you ask, only the last phase's verdict survives. This
hook keeps a per-phase copy so completion can be DERIVED, not asserted: when a
verification carrying verdict PASS + a phase id is written, copy it once to
verification-<phase>.json (first-wins, never overwriting an existing snapshot).

Enforced, not advised: the agent keeps writing ONE verification.json per phase as
it already does (per-phase-tdd.md); the hook owns the per-phase naming. So the
completion count cannot be gamed by a forgotten/duplicated suffix.

The snapshot + lifecycle logic lives in verification_snapshot.py (a shared
module) so this hook and write_verification.py drive the exact same code path —
a Bash-written verification (which never trips PostToolUse) gets an identical
snapshot through the script. This hook is the fallback for the Write-tool path.

After the snapshot — and gated by HARNESS_AUTO_FINALIZE (kill-switch leaves the
snapshot, drops the flips) — the hook drives the plan it JUST wrote to through its
lifecycle: auto-open (pending|approved -> in_progress) and finalize (close ONLY at
N/N phases). It only ever touches the plan whose verification was written.

The snapshot/flip writes are plain file I/O (not the Write tool), so they neither
re-trigger PostToolUse nor trip write_guard. The matcher excludes
verification-*.json so a direct write of a snapshot never self-triggers either.

Telemetry-class: fail-open, scoped to plans/<p>/artifacts/verification.{json,yaml}.
Hook stdin protocol: { tool_name, tool_input: { file_path }, ... }.
"""

import os
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_LIB_DIR = os.path.join(_HOOKS_DIR, "..", "scripts")
sys.path.insert(0, _LIB_DIR)
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import hook_runtime  # noqa: E402
import harness_paths  # noqa: E402
import verification_snapshot as vsnap  # noqa: E402
# Re-export so existing callers (auto_finalize_ship.py) keep importing the knob
# from this hook; the single source of truth is verification_snapshot.
from verification_snapshot import auto_finalize_enabled  # noqa: E402,F401

HOOK_CLASS = "telemetry"

_STEM = "phase_progress_writer"


def core(data: dict) -> None:
    inp = (data or {}).get("tool_input") or {}
    # plans/ is a PROJECT tree, not a bin tree. Under a global install
    # harness_paths.root() is the shared bin, so verification_plan_dir()
    # could not place any real plan and returned None for every write — the
    # per-phase snapshot silently never happened, derive_plan_completion then
    # counted 0/N, and the ship gate blocked on evidence that was written but
    # never copied. project_root() is bin==project under self-host, so the
    # self-hosted path is unchanged.
    root = harness_paths.project_root()
    plan_dir = vsnap.verification_plan_dir(inp.get("file_path"), root)
    if plan_dir is None:
        return
    vsnap.snapshot(plan_dir)
    if vsnap.auto_finalize_enabled():
        vsnap.drive_lifecycle(plan_dir)


def main(raw=None) -> None:
    hook_runtime.run_telemetry_hook(_STEM, core, raw=raw)


if __name__ == "__main__":
    main()
