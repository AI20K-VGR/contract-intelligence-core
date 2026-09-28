#!/usr/bin/env python3
"""bisect_run.py — automate `git bisect run` to pin the commit that introduced a regression.

Manual bisection is O(log n) checkouts but tedious and easy to mis-mark. Given a KNOWN-good
ref, a KNOWN-bad ref (default HEAD), and a test command that exits 0 on good / non-zero on bad,
this drives `git bisect run` end-to-end and prints the first bad commit — then ALWAYS resets the
bisect state, even on error or interrupt, so the working tree is never left mid-bisect.

    bisect_run.py --good <ref> [--bad <ref=HEAD>] [--dry-run] [--force] -- <test command...>
    bisect_run.py --good v1.2.0 -- python -m pytest tests/test_api.py::test_create -q

The test command is run by git at each step (exit 0 = good, 1..127 except 125 = bad, 125 = skip).
PRECONDITION: confirm the failure is reproducible and NOT flaky first (see find_flaky.py) — a flaky
oracle makes the binary search lie. `--good` must be an ancestor of `--bad`. The test command MUST
NOT modify the working tree (git checks out each step; uncommitted changes block the checkout and the
final reset — the tool warns if it is left mid-bisect).

Exit: 0 = first bad commit found (printed); 1 = bisect ran but could not isolate; 2 = usage/precondition.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

# git quotes the term in its result line on newer versions (`is the first 'bad'
# commit`) and does not on older ones. Keyed on one spelling, a run that SUCCEEDED
# read as no result: the tool printed "could not isolate" and exited 1, blaming a
# flaky oracle for its own parse. Hosts run both, so both are accepted.
_FIRST_BAD_RE = re.compile(
    r"^([0-9a-f]{40}) is the first '?bad'? commit", re.MULTILINE)


class UsageError(Exception):
    """A precondition or argument problem — maps to exit 2."""


def parse_first_bad(text: str) -> str | None:
    """The 40-hex sha git prints as `<sha> is the first bad commit`, or None if absent.

    Matched at line start so a prose line that merely contains the phrase
    (e.g. a commit message) is not mistaken for the result line."""
    m = _FIRST_BAD_RE.search(text or "")
    return m.group(1) if m else None


def build_plan(good: str, bad: str, test_cmd) -> list:
    """The ordered git argv sequences a real run performs. Pure — drives --dry-run and tests.

    `git bisect start <bad> <good>` marks the endpoints, `git bisect run <cmd>` searches,
    `git bisect reset` restores the original HEAD."""
    return [
        ["git", "bisect", "start", bad, good],
        ["git", "bisect", "run", *test_cmd],
        ["git", "bisect", "reset"],
    ]


def parse_args(argv) -> dict:
    """Parse `--good/--bad/--dry-run/--force` then a `--`-separated test command.

    Raises UsageError on a missing required value, an unknown flag, or a missing command."""
    good = None
    bad = "HEAD"
    dry = False
    force = False
    cmd = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--":
            cmd = list(argv[i + 1:])
            break
        if a in ("--good", "--bad"):
            if i + 1 >= len(argv):
                raise UsageError("%s needs a ref" % a)
            if a == "--good":
                good = argv[i + 1]
            else:
                bad = argv[i + 1]
            i += 2
            continue
        if a == "--dry-run":
            dry = True
        elif a == "--force":
            force = True
        else:
            raise UsageError("unknown argument %r" % a)
        i += 1
    if good is None:
        raise UsageError("--good <ref> is required (a known-good ancestor of --bad)")
    if not cmd:
        raise UsageError("a test command is required after `--`")
    return {"good": good, "bad": bad, "dry": dry, "force": force, "cmd": cmd}


def _run_git(args, cwd):
    """Run a git argv, capturing text output (never raises on non-zero — caller inspects)."""
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _ref_resolves(ref, cwd) -> bool:
    return _run_git(["rev-parse", "--verify", "--quiet", ref + "^{commit}"], cwd).returncode == 0


def _is_ancestor(good, bad, cwd) -> bool:
    return _run_git(["merge-base", "--is-ancestor", good, bad], cwd).returncode == 0


def _reset_bisect(cwd):
    """Reset the bisect session; WARN loudly on failure so the caller knows the repo
    may be left mid-bisect. A test command that DIRTIES the working tree can block the
    checkout `git bisect reset` performs — hence the explicit return-code check."""
    res = _run_git(["bisect", "reset"], cwd)
    if res.returncode != 0:
        sys.stderr.write(res.stderr)
        print("warning: `git bisect reset` failed — the repo may be left mid-bisect. "
              "Run `git bisect reset` (and check out your branch) manually.",
              file=sys.stderr)
    return res


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        opts = parse_args(argv)
    except UsageError as e:
        print("usage: bisect_run.py --good <ref> [--bad <ref>] [--dry-run] [--force] "
              "-- <test command...>", file=sys.stderr)
        print("error: %s" % e, file=sys.stderr)
        return 2

    cwd = os.getcwd()
    good, bad, cmd = opts["good"], opts["bad"], opts["cmd"]
    plan = build_plan(good, bad, cmd)

    if opts["dry"]:
        print("plan (dry-run, nothing executed):")
        for step in plan:
            print("  " + " ".join(step))
        return 0

    # preconditions — fail loud BEFORE mutating any bisect state
    if _run_git(["rev-parse", "--is-inside-work-tree"], cwd).returncode != 0:
        print("error: not inside a git work tree", file=sys.stderr)
        return 2
    for label, ref in (("--good", good), ("--bad", bad)):
        if not _ref_resolves(ref, cwd):
            print("error: %s ref %r does not resolve to a commit" % (label, ref),
                  file=sys.stderr)
            return 2
    if not _is_ancestor(good, bad, cwd):
        print("error: --good (%s) must be an ancestor of --bad (%s); bisect searches the "
              "range between them" % (good, bad), file=sys.stderr)
        return 2
    bisect_log = os.path.join(cwd, ".git", "BISECT_LOG")
    # git bisect writes BISECT_LOG as its canonical in-progress marker (NOT a state
    # file we maintain — we only check for its existence to avoid concurrent bisects).
    if os.path.exists(bisect_log) and not opts["force"]:
        print("error: a bisect is already in progress (%s). Finish it or pass --force to "
              "reset and restart." % bisect_log, file=sys.stderr)
        return 2

    start, run, reset = plan
    try:
        if opts["force"] and _reset_bisect(cwd).returncode != 0:
            print("error: could not clear the existing bisect session to --force a "
                  "restart; resolve it manually first", file=sys.stderr)
            return 2
        st = _run_git(start[1:], cwd)
        if st.returncode != 0:
            sys.stderr.write(st.stderr)
            print("error: `git bisect start` failed", file=sys.stderr)
            return 2
        res = _run_git(run[1:], cwd)
        out = res.stdout + "\n" + res.stderr
        first_bad = parse_first_bad(out)
        if first_bad:
            subj = _run_git(["log", "-1", "--format=%h %s", first_bad], cwd).stdout.strip()
            print("FIRST BAD COMMIT: %s" % (subj or first_bad))
            print("  introduced the regression your test command detects.")
            return 0
        sys.stderr.write(out[-1200:])
        print("could not isolate a first bad commit — the oracle may be flaky, or the range "
              "contains a skip/build break. Confirm with find_flaky.py.", file=sys.stderr)
        return 1
    finally:
        _reset_bisect(cwd)  # ALWAYS restore HEAD, even on error/interrupt (warns if it can't)


if __name__ == "__main__":
    sys.exit(main())
