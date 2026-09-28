#!/usr/bin/env python3
"""finalize_plan.py — deterministically move a plan to `completed`, but ONLY on
derived evidence: all N phases carry a PASS snapshot AND the canonical
verification belongs to this plan.

This is the one primitive allowed to take a plan out of the pending/approved
"trap": close_plan deliberately finalizes only from in_progress (a misaimed
manual close must never mark unstarted work done), so an auto-opened plan that
was never hand-opened could otherwise never close. finalize_plan threads the
open->close itself, gated so it cannot fire early:

  1. containment — outside plans/ is an error (reuses plan_status discipline).
  2. evidence gate — derive_plan_completion.is_complete is the ONLY "done"
     signal. A single verification verdict is NOT trusted (the early-close
     trap): one PASS can never satisfy N distinct node-phases.
  3. cross-plan binding — a canonical verification whose `plan` names a DIFFERENT
     dir is a copied/forged artifact; no-op rather than close the wrong plan.
  4. status — completed/cancelled left alone; pending/approved opened first;
     in_progress closed directly.

Never raises: any unexpected error degrades to a benign no-op Result. A status
flip emits a trace event (plan_auto_finalize) and the caller surfaces one line.
"""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

import plan_status  # noqa: E402
import derive_plan_completion  # noqa: E402
import artifact_check  # noqa: E402
from plan_status import Result  # noqa: E402
from close_plan import close_plan  # noqa: E402

_TERMINAL = {"completed", "cancelled"}
# Compared against normalize_status output (which already folds the retired
# `draft`/`awaiting_human_approval` to `pending`), so the startable pre-cook
# states are simply pending + approved.
_STARTABLE = {"pending", "approved"}


def _trace(plan_dir: Path) -> None:
    """Best-effort audit event; fail-open (trace is telemetry, not a gate)."""
    try:
        hooks = _HERE.parent.parent / "hooks"
        if str(hooks) not in sys.path:
            sys.path.insert(0, str(hooks))
        import trace_log
        trace_log.append_event(
            "finalize_plan", "plan_auto_finalize",
            target=plan_dir.name, status="completed",
            note="derived N/N phases PASS")
    except Exception:
        pass


def _finalize(plan_dir, root) -> Result:
    plan_dir = Path(plan_dir)

    # (1) containment + read current status in one shot. A dir outside plans/, a
    # missing plan.md, or a missing status line returns ok=False here.
    spliced = plan_status._splice_status(plan_dir, root)
    if isinstance(spliced, Result):
        return spliced
    current = plan_status.normalize_status(spliced[3])

    # (2) evidence gate — the only "done" signal.
    state = derive_plan_completion.completion_state(plan_dir, root=root)
    if not state["complete"]:
        return Result(True, False, "not complete (%s)" % state["reason"])

    # (3) cross-plan binding — a confirmed mismatch is a no-op, not a close.
    rec, _problem = artifact_check._load_artifact(plan_dir, "verification")
    if isinstance(rec, dict):
        named = rec.get("plan")
        if isinstance(named, str) and named and named != plan_dir.name:
            return Result(True, False,
                          "canonical verification names %r, not %s — no-op"
                          % (named, plan_dir.name))

    # (4) status flip.
    if current in _TERMINAL:
        return Result(True, False, "no-op: already %s" % current)
    if current in _STARTABLE:
        # Write in_progress directly rather than delegating to open_plan: its
        # flip_status compares the RAW on-disk token (no legacy fold — see
        # open_plan.py) against a startable set that does not include every
        # _LEGACY_FOLD key (e.g. awaiting_human_approval). `current` here is
        # already the normalized, evidence-gated startable state, so an
        # unconditional overwrite is correct and covers every legacy label.
        opened = plan_status.set_status_value(plan_dir, "in_progress", root=root)
        if not opened.ok:
            return opened

    res = close_plan(plan_dir, root=root)
    if res.ok and res.changed:
        _trace(plan_dir)
    return res


def finalize_plan(plan_dir, root=None) -> Result:
    try:
        return _finalize(plan_dir, root)
    except Exception as e:  # noqa: BLE001 — finalize must never crash a hook
        return Result(True, False, "finalize skipped: %s" % e)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        sys.stderr.write("usage: finalize_plan.py <plan_dir>\n")
        return 2
    res = finalize_plan(argv[0])
    out = sys.stdout if res.ok else sys.stderr
    out.write(res.message + "\n")
    if res.changed:
        sys.stderr.write("[auto-finalize] closed %s (N/N phases PASS)\n"
                         % Path(argv[0]).name)
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
