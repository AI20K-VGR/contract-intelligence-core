#!/usr/bin/env python3
"""find_polluter.py — find which earlier test pollutes a target test.

A test that PASSES in isolation but FAILS inside the full suite is being polluted
by an earlier test: leaked global/module state, a monkeypatch never undone, a file
written and not cleaned, an env var set, a singleton mutated. Eyeballing the order
is slow; this bisects it.

It confirms the target passes ALONE, reproduces the failure with the full set of
earlier tests, then binary-searches that prefix to the single earlier test whose
presence flips the target to failing — O(log n) suite runs, not O(n).

    find_polluter.py <target_node_id> [-- <extra pytest args>]
    find_polluter.py tests/test_api.py::test_create -- -p no:randomly

Assumes a SINGLE polluter (the common case). With multiple interacting polluters it
reports the one the bisection isolates; re-run after fixing it to find the next.

Artifact mode finds a different pollution class: the test that dirties the working
tree by CREATING an unwanted file or dir (which the target-flip mode is blind to
unless the stray file also fails some later test). Same O(log n) bisection.

    find_polluter.py --artifact <path> [-- <extra pytest args>]
    find_polluter.py --artifact .pytest_cache/stray -- -k integration
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def bisect_polluter(before_ids, run_passes) -> str | None:
    """Binary-search ordered earlier test ids for the polluter.

    `run_passes(prefix_ids)` runs the target AFTER `prefix_ids` and returns True iff
    the target still PASSES. Precondition: run_passes([]) is True (passes alone) and
    run_passes(before_ids) is False (the full prefix reproduces the failure). Returns
    the earlier test whose inclusion flips the target to failing, or None if the
    preconditions do not hold (no reproducible single-test pollution)."""
    before_ids = list(before_ids)
    if not before_ids:
        return None
    if not run_passes([]):
        return None  # target does not even pass alone — not a pollution case
    if run_passes(before_ids):
        return None  # full prefix still passes — no pollution to bisect
    lo, hi = 0, len(before_ids)  # passes at :lo, fails at :hi
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if run_passes(before_ids[:mid]):
            lo = mid
        else:
            hi = mid
    return before_ids[lo]  # before[:lo] passes, before[:lo+1] fails -> before[lo]


def _collect_ids(extra):
    """(all_test_ids, collect_ok, proc) in the real failing-suite order. collect_ok is
    False on a pytest collection/usage error (exit not in {0,5}) -- an empty list then
    means the suite is BROKEN, not 'no tests'. `-p no:randomly` matches the run oracle so
    the collected order is the real failing-suite order (else pytest-randomly reshuffles
    --collect-only and the prefix order diverges)."""
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-p", "no:randomly", *extra],
        capture_output=True, text=True)
    ids = [l.strip() for l in out.stdout.splitlines()
           if "::" in l and not l.startswith(" ")]
    return ids, out.returncode in (0, 5), out


def _collect_before(target: str, extra):
    """(ids_before_target, collect_ok, proc): the collected ids truncated at `target`."""
    ids, ok, out = _collect_ids(extra)
    before = ids[: ids.index(target)] if target in ids else ids
    return before, ok, out


def _passed_from_output(output: str, target: str) -> bool:
    """True iff pytest's -rA output reports `target` as PASSED.

    The node-id is matched EXACTLY: a superstring sibling's FAILED line (e.g.
    `test_foobar` when the target is `test_foo`) must not be read as the target
    failing. And a target that never appears — a prefix that broke COLLECTION, so
    the target never ran — is NOT a pass: it must not read as 'this prefix is safe'
    (that false-positive silently corrupts the bisection). The node-id may itself contain
    spaces AND ` - ` (a parametrized id like `test_foo[user - admin]`), so the match anchors
    on the KNOWN target (`<STATUS> <target>` exactly, or `<STATUS> <target> - <reason>` for a
    trailing reason) rather than parsing the id out of the line -- splitting the id out would
    truncate it and misread the result, and a superstring sibling (`test_foobar`) is rejected
    because the target must be followed by end-of-line or a space."""
    # Anchors depend only on the invariant `target`, not the line — build them once
    # instead of re-concatenating per output line.
    anchors = [(s, s + " " + target) for s in ("PASSED", "FAILED", "ERROR")]
    for raw in output.splitlines():
        line = raw.strip()
        for status, anchor in anchors:
            if line == anchor or line.startswith(anchor + " "):
                return status == "PASSED"
    return False


def _target_passes(prefix, target, extra) -> bool:
    """Run `prefix + target`; True ONLY if the target is explicitly reported PASSED. Raises
    _PrefixCollectionError when the run exits outside {0 pass, 1 fail, 5 no-tests} -- a
    collection/usage error means the target never ran, so reading the missing PASSED line as
    a target FAILURE would misread a broken prefix as pollution and corrupt the search (the
    same guard artifact-mode uses; kept symmetric between the two modes)."""
    args = [sys.executable, "-m", "pytest", "-q", "-p", "no:randomly",
            "--tb=no", "-rA", *extra, *prefix, target]
    res = subprocess.run(args, capture_output=True, text=True)
    if res.returncode not in (0, 1, 5):
        raise _PrefixCollectionError((res.stdout + res.stderr)[-800:])
    return _passed_from_output(res.stdout + "\n" + res.stderr, target)


def _reset_safe(path, root=None):
    """(ok, reason): may the bisection DELETE `path` between probes?

    A reset must only ever remove genuine test pollution, never a real repo
    file. It refuses a symlink (could resolve outside the tree), `.git` or
    anything inside it, the tree root itself, a path resolving outside the
    working tree, and any git-tracked path."""
    root = Path(root).resolve() if root is not None else Path.cwd().resolve()
    p = (root / path) if not Path(path).is_absolute() else Path(path)
    if p.is_symlink():
        return False, "is a symlink"
    resolved = p.resolve()
    if resolved == root:
        return False, "is the working tree root"
    if root not in resolved.parents:
        return False, "resolves outside the working tree"
    git_dir = root / ".git"
    if resolved == git_dir or git_dir in resolved.parents:
        return False, "is the .git directory"
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(path)],
        cwd=str(root), capture_output=True, text=True)
    if tracked.returncode == 0:
        return False, "is tracked by git (a real repo file, not test pollution)"
    return True, ""


def _remove_artifact(path):
    """Delete `path` (file or dir). Caller MUST have cleared _reset_safe first."""
    p = Path(path)
    if p.is_dir() and not p.is_symlink():
        shutil.rmtree(p, ignore_errors=True)
    elif p.exists() or p.is_symlink():
        try:
            p.unlink()
        except OSError:
            pass


class _PrefixCollectionError(Exception):
    """A prefix pytest run broke COLLECTION (not pass/fail): with no tests actually run the
    artifact is trivially absent, which would falsely read as 'clean' and corrupt the
    search -- so the ambiguity is surfaced and the bisection aborts, never silently trusted."""


def _artifact_clean_after(prefix, artifact, extra) -> bool:
    """Reset `artifact`, run `prefix`, return True iff `artifact` stays ABSENT. Raises
    _PrefixCollectionError when the prefix run exits outside {0 pass, 1 fail, 5 no-tests}
    (a collection/usage error) -- absence is then meaningless."""
    _remove_artifact(artifact)
    if prefix:
        res = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:randomly",
             "--tb=no", *extra, *prefix],
            capture_output=True, text=True)
        if res.returncode not in (0, 1, 5):
            raise _PrefixCollectionError((res.stdout + res.stderr)[-800:])
    return not Path(artifact).exists()


def _run_artifact_mode(artifact, extra) -> int:
    """Bisect the suite for the first test that CREATES `artifact`."""
    safe, reason = _reset_safe(artifact)
    if not safe:
        print("refusing to reset %r: it %s -- pick a genuine test-created path"
              % (artifact, reason), file=sys.stderr)
        return 2
    if Path(artifact).exists():
        # The bisection RESETS (deletes) the artifact between probes. A path that already
        # exists is not test-created pollution -- deleting it would destroy real (possibly
        # untracked) user data. Refuse; never delete something we did not watch a test make.
        print("refusing: %r already exists before the bisection -- this mode only bisects a "
              "stray artifact a TEST creates (and resets it between probes), so a "
              "pre-existing path would be DELETED. Remove it yourself first if it is real "
              "test pollution, or target a path that does not yet exist." % artifact,
              file=sys.stderr)
        return 2
    ids, collect_ok, cout = _collect_ids(extra)
    if not collect_ok:
        sys.stderr.write((cout.stdout + cout.stderr)[-800:] + "\n")
        print("pytest could not collect the suite (exit %d) -- fix collection "
              "before bisecting" % cout.returncode, file=sys.stderr)
        return 2
    if not ids:
        print("no tests collected -- nothing to bisect")
        return 0
    try:
        polluter = bisect_polluter(
            ids, lambda prefix: _artifact_clean_after(prefix, artifact, extra))
    except _PrefixCollectionError as exc:
        sys.stderr.write(str(exc) + "\n")
        print("a prefix broke pytest collection mid-bisection -- fix collection "
              "before bisecting", file=sys.stderr)
        _remove_artifact(artifact)
        return 2
    _remove_artifact(artifact)  # leave the tree as we found it
    if polluter is None:
        print("no test creates %r after the full suite -- nothing to bisect"
              % artifact)
        return 0
    print("POLLUTER: %s" % polluter)
    print("  -> running `%s` creates the artifact `%s`." % (polluter, artifact))
    return 1


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: find_polluter.py <target_node_id> [-- <pytest args>]\n"
              "       find_polluter.py --artifact <path> [-- <pytest args>]",
              file=sys.stderr)
        return 2
    if argv[0] == "--artifact":
        if len(argv) < 2:
            print("usage: find_polluter.py --artifact <path> [-- <pytest args>]",
                  file=sys.stderr)
            return 2
        artifact = argv[1]
        rest = argv[2:]
        extra = rest[1:] if rest and rest[0] == "--" else rest
        return _run_artifact_mode(artifact, extra)
    target = argv[0]
    extra = argv[2:] if len(argv) > 1 and argv[1] == "--" else argv[1:]
    before, collect_ok, cout = _collect_before(target, extra)
    if not collect_ok:
        sys.stderr.write((cout.stdout + cout.stderr)[-800:] + "\n")
        print("pytest could not collect the suite (exit %d) -- fix collection "
              "before bisecting" % cout.returncode, file=sys.stderr)
        return 2
    if not before:
        print("no earlier tests collected before %r -- nothing to bisect" % target)
        return 0
    try:
        if not _target_passes([], target, extra):
            # bisect_polluter also returns None when the target FAILS in isolation, which
            # would print the misleading "passes ... no pollution" line below. Distinguish
            # it here: a test failing on its own is not a pollution case at all.
            print("%r does not pass in isolation -- it fails on its own, so there is no "
                  "pollution to bisect (fix the test itself first)" % target,
                  file=sys.stderr)
            return 2
        polluter = bisect_polluter(
            before, lambda prefix: _target_passes(prefix, target, extra))
    except _PrefixCollectionError as exc:
        sys.stderr.write(str(exc) + "\n")
        print("a prefix broke pytest collection mid-bisection -- fix collection "
              "before bisecting", file=sys.stderr)
        return 2
    if polluter is None:
        print("%r still passes after the full earlier set — no reproducible pollution"
              % target)
        return 0
    print("POLLUTER: %s" % polluter)
    print("  -> running `%s` before `%s` flips it to failing." % (polluter, target))
    return 1


if __name__ == "__main__":
    sys.exit(main())
