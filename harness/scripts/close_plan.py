#!/usr/bin/env python3
"""close_plan.py — finalize a plan by flipping its frontmatter status from
in_progress to completed.

Why this exists: cook's finalize step closes a plan by hand-editing plan.md.
When an autonomous run skips that edit, the plan stays in_progress forever, and
the gate's active-plan resolver (artifact_check.resolve_active_plan) only ever
returns an in_progress plan — so a forgotten close pins the gate to a stale
plan and blocks unrelated shipping. Cook calls this instead of editing by hand:
a deterministic, idempotent, surgical status flip.

Surgical: only the status value inside the frontmatter block is rewritten; the
body (which may quote `status: in_progress` in prose/examples) is preserved
byte-for-byte. Idempotent: an already-completed plan is a successful no-op. A
pending plan is left alone — close only finalizes work that actually started.

Usage:
    python3 harness/scripts/close_plan.py <plan_dir>

Exit 0 on success (changed or already-completed no-op); exit 1 on error
(plan.md missing, no frontmatter status line, plan_dir outside plans/).
"""
import sys

from plan_status import Result, flip_status  # noqa: F401  (Result re-exported)

# Only a plan that actually ran is finalized; a pending plan (never started) is
# left alone as a benign no-op, so a misaimed close cannot mark unstarted work
# done. (open_plan owns the other direction.)
_FINALIZABLE = {"in_progress"}


def close_plan(plan_dir, root=None) -> Result:
    """Flip plan_dir/plan.md frontmatter status in_progress -> completed.

    Returns Result(ok, changed, message). ok=False on any structural error; the
    file is never partially written. An off-source status (e.g. pending) is a
    benign no-op, not an error.
    """
    return flip_status(plan_dir, allowed_from=_FINALIZABLE, to="completed",
                       error_on_other=False, root=root)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        sys.stderr.write("usage: close_plan.py <plan_dir>\n")
        return 2
    res = close_plan(argv[0])
    (sys.stdout if res.ok else sys.stderr).write(res.message + "\n")
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
