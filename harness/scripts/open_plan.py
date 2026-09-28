#!/usr/bin/env python3
"""open_plan.py — start a plan by flipping its frontmatter status to in_progress.

The mirror of close_plan, and cook's FIRST deterministic step. The gate's
active-plan resolver (artifact_check.resolve_active_plan) returns ONLY a plan
whose status is in_progress. A freshly created plan is pending (or approved once
reviewed), and nothing else moves it forward — so without this step the cooked
plan is
invisible to the gate: its verification/review gates are silently skipped, or
the resolver latches onto a stale in_progress plan left over from another
session. Cook calls this instead of hand-editing plan.md.

Surgical + idempotent, same discipline as close_plan. Unlike close, an
off-source status fails LOUD: a completed/cancelled (or otherwise non-startable)
plan returns an error so cook halts rather than cooking a plan the resolver will
never see as active. An already-in_progress plan is a successful no-op.

Usage:
    python3 harness/scripts/open_plan.py <plan_dir>

Exit 0 on success (changed or already-in_progress no-op); exit 1 on error
(plan.md missing, no status line, plan_dir outside plans/, or a non-startable
status such as completed/cancelled).
"""
import sys

from plan_status import Result, flip_status  # noqa: F401  (Result re-exported)

# Cook starts a plan from its pre-cook state; the gate only cares that it reaches
# in_progress. `approved` is the post-approval ready-to-cook state; `pending` is
# the not-yet-approved state still startable for back-compat/solo. `draft` is the
# retired legacy spelling of `pending` — tolerated here because flip_status
# compares the raw on-disk token (no legacy fold), so a not-yet-migrated `draft`
# plan stays openable until reconcile rewrites it.
_STARTABLE = {"pending", "approved", "draft"}


def open_plan(plan_dir, root=None) -> Result:
    """Flip plan_dir/plan.md frontmatter status pending|approved -> in_progress."""
    return flip_status(plan_dir, allowed_from=_STARTABLE, to="in_progress",
                       error_on_other=True, root=root)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        sys.stderr.write("usage: open_plan.py <plan_dir>\n")
        return 2
    res = open_plan(argv[0])
    (sys.stdout if res.ok else sys.stderr).write(res.message + "\n")
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
