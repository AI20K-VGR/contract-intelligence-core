#!/usr/bin/env python3
"""pr_changed_plans.py — the plan dirs a diff touches, filtered for the receipts-gate.

`git diff --name-status <base>..<head>` → the set of `plans/<dir>/` a PR/push touches
(dir-level dedup; `plans/reports/` excluded — scratch). Each dir is kept only if the PR
is genuinely the SUBJECT of work on it:

  - SKIP if `plans/<dir>/plan.md` is ABSENT in the head tree (plan deleted/moved), or the
    diff under the dir is ALL deletions (every status `D`, no `A`/`M`) — a PR that prunes a
    completed plan's artifacts must not be self-blocked for the receipts it just removed.
  - read the head plan.md frontmatter `status:` — `pending` → SKIP + note (a plan not yet
    cooked has no receipts to demand); `in_progress` / `completed` → judge.

Emits a JSON list of judge-worthy dir names on stdout. Split out from the workflow YAML so
it is unit-testable (a workflow step is not)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import plan_status  # noqa: E402


class GitError(RuntimeError):
    """A git command the gate depends on failed — the gate must FAIL-CLOSED rather
    than silently resolve an empty plan set (a bad base sha must not turn the gate
    green)."""


def _git(root, *args) -> str:
    try:
        r = subprocess.run(["git", "-C", root, *args], capture_output=True,
                           text=True, timeout=60)
    except subprocess.TimeoutExpired as e:
        raise GitError("git %s timed out after 60s" % " ".join(args)) from e
    if r.returncode != 0:
        raise GitError("git %s failed (rc=%d): %s"
                       % (" ".join(args), r.returncode, (r.stderr or "").strip()[:200]))
    return r.stdout


def _head_status(root, dir_name, head) -> "str | None":
    """The plan.md `status:` in the `head` tree, or None if plan.md is absent there.
    A git error here is NOT fail-closed — an absent plan.md legitimately errors, so we
    read it as 'absent' (the caller skips the dir); the load-bearing fail-closed is the
    diff in _git."""
    try:
        show = subprocess.run(
            ["git", "-C", root, "show", "%s:plans/%s/plan.md" % (head, dir_name)],
            capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired as e:
        raise GitError("git show %s:plans/%s/plan.md timed out after 30s"
                       % (head, dir_name)) from e
    if show.returncode != 0 or not show.stdout:
        return None
    m = plan_status._FRONTMATTER_RE.match(show.stdout)
    if not m:
        return None
    s = plan_status._STATUS_RE.search(m.group(1))
    return s.group(1).strip() if s else None


def changed_plans(root, base, head):
    """(judge, skipped) — judge is the list of dir names to gate; skipped is a list of
    {dir, reason} for visibility. Raises GitError (fail-closed) on a diff failure."""
    out = _git(root, "diff", "--name-status", "%s..%s" % (base, head))
    by_dir = {}  # dir -> set of statuses (A/M/D/...)
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        st, path = parts[0], parts[-1]
        if not path.startswith("plans/"):
            continue
        seg = path.split("/")
        if len(seg) < 3 or seg[1] == "reports":
            continue
        by_dir.setdefault(seg[1], set()).add(st[0])

    judge, skipped = [], []
    for d in sorted(by_dir):
        statuses = by_dir[d]
        # Read status FIRST — the deletion-only skip must NOT swallow a live plan.
        status = _head_status(root, d, head)
        if status is None:
            skipped.append({"dir": d, "reason": "plan.md absent in head (deleted/moved)"})
            continue
        if statuses <= {"D"} and status == "completed":
            # A prune of a COMPLETED plan's own artifacts — the PR is not the subject
            # of the plan, it is cleaning up. An in_progress plan losing a
            # receipt is NOT skipped here → it is judged → it blocks (correct).
            skipped.append({"dir": d, "reason": "deletion-only prune of a completed plan"})
            continue
        if status == "pending":
            skipped.append({"dir": d, "reason": "plan.md status: pending (not cooked)"})
            continue
        judge.append(d)
    return judge, skipped


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Plan dirs a diff touches (gate-filtered)")
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--root", default=os.getcwd())
    a = ap.parse_args(argv)
    try:
        judge, skipped = changed_plans(a.root, a.base, a.head)
    except GitError as e:
        # Fail-closed: a broken diff (bad base sha, force-push, orphaned commit) must
        # NOT resolve an empty plan set and turn the gate green. Exit 2 fails the job.
        sys.stderr.write("receipts-gate: %s\n" % e)
        return 2
    print(json.dumps({"judge": judge, "skipped": skipped}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
