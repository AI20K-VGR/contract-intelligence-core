#!/usr/bin/env python3
"""hs_run_git.py — the `git` domain's verb set for hs-run.

Promoted from an earlier draft.
That draft's "no precedent for importing harness/hooks/ from harness/scripts/"
claim was wrong — `guard_config.py` (same directory, same shape: a CLI script
that needs a hooks-module for its own logic) already does exactly this:

    _HERE = Path(__file__).resolve().parent
    sys.path.insert(0, str(_HERE))
    sys.path.insert(0, str(_HERE.parent / "hooks"))

Matched verbatim below (not `lens_gate.py`'s narrower hooks-only variant,
because this module — like guard_config.py — is also runnable standalone via
`__main__`, so the belt-and-suspenders self-path insert earns its keep here).

`commit-plan` REUSES `secret_scan_before_ship.scan_diff_text` — the same
scanner the pre-ship hook and push_gate's transport backstop already run —
rather than a second regex set. The only new code is `_staged_diff`: the
existing scanner reads unpushed COMMITS or the working-tree pack surface;
commit-plan needs the STAGED diff (`git diff --cached`), a third, distinct
diff this repo had no reader for yet.

Exit-tier deviation from the draft (bug found while wiring this in): the
draft returned EXIT_STEP_REMAINING(11) for "diff is clean, here's the split
plan" — but hs_run.py's dispatcher enforces that an 11 promises a runnable
`hs-run ...` command in `next_action` (`_looks_runnable`), and the split-plan
sentence is prose, not a command. Left as 11 it would have been silently
forced to EXIT_BROKEN(2) by the dispatcher on every clean run, which is a
worse contract than what the draft intended. `ready` is EXIT_NEEDS_MODEL(10)
instead: deciding how to actually stage/commit per the plan is exactly a
"spawn something, it can't run deterministically here" step, which is what
10 means. `commit-plan` never calls `git commit`/`git push`/anything that
mutates the index or HEAD — it only reads `git diff --cached`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import attrs as _attrs  # noqa: E402  (REQUIRED — see harness/requirements.txt)

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "hooks"))

import hs_run_next_command  # noqa: E402
import secret_scan_before_ship as secret_scan  # noqa: E402

# Hardening for every git call below, IMPORTED from the scanner this module already
# depends on rather than restated. git reads the inspected repository's own config,
# and keys such as `core.fsmonitor` name a program git then EXECUTES; this module
# runs git against a repo it does not own, on the path that decides whether a staged
# secret ships. Two modules hardening differently means the weaker one is the way in.
_GIT_SAFE = secret_scan._GIT_SAFE_CONFIG
_git_env = secret_scan._git_safe_env

# The four-tier ladder (D10), IMPORTED rather than re-declared.
# Ten modules used to hand-copy these four constants and had already drifted:
# rung 11 carried two different names across the tree and two modules declared
# the same constant twice. `hs_run` owns the ladder as a closed `Exit` IntEnum;
# both historical spellings of rung 11 are bound to the same member there, so
# this import changes no name any caller in this file uses.
import hs_run  # noqa: E402 — the shared verb-argv parser lives here
from hs_run import EXIT_BROKEN, EXIT_DONE, EXIT_NEEDS_MODEL, EXIT_STEP_REMAINING  # noqa: E402

# Arbitrary, documented thresholds for the split-plan advisory (not a second
# scanner, not domain logic — just formatting `git diff --cached --numstat`'s
# own numbers into a human-actionable split recommendation).
_SPLIT_FILE_CEILING = 3
_SPLIT_LINE_CEILING = 50

_USAGE = "usage: hs-run git next"


def _git_dir_present(root: Path) -> bool:
    """True iff a `.git` entry (a directory for a normal repo, OR a FILE for
    a worktree/submodule gitlink) exists anywhere from `root` up to the
    filesystem root. This walks the same parent chain `git rev-parse` itself
    walks to locate a repository, but reads the filesystem directly instead
    of trusting git's own verdict — the discriminator DEFECT 3 needs, because
    git's stderr text is NOT reliable here: a corrupt `.git/HEAD` makes
    `git rev-parse --is-inside-work-tree` print the exact same
    `fatal: not a git repository (or any of the parent directories): .git`
    message a directory with no `.git` at all produces (confirmed by hand,
    see the phase report) — so the message can't tell "absent" from "broken"
    apart, only presence-on-disk can."""
    cur = root.resolve()
    while True:
        try:
            if (cur / ".git").exists():
                return True
        except OSError:
            pass  # unreadable entry — treat as "not found here", keep walking up
        parent = cur.parent
        if parent == cur:
            return False
        cur = parent


def _git_repo_status(root: Path):
    """Distinguishes the THREE outcomes `_in_git_repo` used to collapse into
    two. Returns `(status, stderr)`:

    - `"repo"`   — git confirms `root` is inside a work tree; proceed.
    - `"absent"` — no `.git` anywhere up the tree; genuinely never a repo
      (fresh checkout target, plain scratch dir) — the existing benign
      fail-open path, unchanged.
    - `"broken"` — `git rev-parse` failed to answer AND a `.git` entry
      exists somewhere in the chain: git is PRESENT but its plumbing is
      refusing to work (corrupt HEAD, bad repositoryformatversion, an
      unparseable `.git/config`, ...). This is DEFECT 3 — it used to read
      identically to `"absent"` and reported `nothing_staged` EXIT 0 while a
      staged secret sat in the index.

    Discriminator: on-disk presence of `.git`, not `rev-parse`'s exit code
    or stderr text (both are unreliable for telling "absent" from "broken" —
    see `_git_dir_present`). Known weak spot: an orphaned `.git` entry that
    was never actually initialized by git (e.g. a stray empty directory or
    file someone manually named `.git`) reads as `"broken"` here instead of
    `"absent"`, over-blocking a directory that was never really a repo. That
    false-positive is judged the safer failure mode for a secret-scan gate —
    a spurious STOP costs a manual check, a spurious PASS costs a leaked
    credential.
    """
    r = subprocess.run(
        ["git", *_GIT_SAFE, "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True, timeout=30, env=_git_env())
    if r.returncode == 0 and r.stdout.strip() == "true":
        return "repo", ""
    if _git_dir_present(root):
        return "broken", (r.stderr.strip()
                           or "git rev-parse --is-inside-work-tree exited %d" % r.returncode)
    return "absent", ""


def _staged_diff(root: Path):
    """`git diff --cached` — the patch about to become a commit RIGHT NOW.
    Distinct from secret_scan_before_ship's own two diff-gatherers (unpushed
    COMMITS, or the working-tree pack surface): this is a third shape, staged
    but not yet committed.

    Returns `(diff_text, error)`. `error` is `None` on a clean git run
    (`diff_text` may legitimately be "" — nothing staged). `error` is git's
    own stderr when git itself failed on a REAL repo (corrupted object
    store, detached plumbing, etc.) — that case must never be silently
    read as "" by the caller (that was the bug: an empty string meant BOTH
    "nothing staged" and "git broke", so a broken repo skipped the secret
    gate and reported EXIT_DONE). Callers must check `_git_repo_status` first
    — this function only distinguishes success/failure of the diff itself,
    not "no repo at all" (which fails open by design, see
    `_git_repo_status`)."""
    r = subprocess.run(
        ["git", *_GIT_SAFE, "-C", str(root), "diff", "--cached", "--no-color"],
        capture_output=True, text=True, timeout=30, env=_git_env())
    if r.returncode == 0:
        return r.stdout, None
    return "", (r.stderr.strip() or "git diff --cached exited %d" % r.returncode)


def _sequencer_in_progress(root: Path) -> str:
    """`"rebase"`, `"merge"`, `"cherry-pick"`, `"revert"`, or `""` when git is
    not mid-operation.

    The paths are asked of GIT (`rev-parse --git-path`) rather than joined onto
    a guessed `.git/` — a worktree, a submodule and a `--separate-git-dir` clone
    each put them somewhere else, and a check that silently finds nothing in
    those layouts reports a clean tree for the one case it exists to catch.

    Returns the name in the spelling the reader will type: the message built
    from it says `git <name> --continue`, which is a real command for all four.
    """
    def has(rel) -> bool:
        try:
            r = subprocess.run(
                ["git", *_GIT_SAFE, "-C", str(root), "rev-parse", "--git-path", rel],
                capture_output=True, text=True, timeout=15, env=_git_env())
        except (OSError, subprocess.SubprocessError):
            return False
        if r.returncode != 0:
            return False
        p = (r.stdout or "").strip()
        if not p:
            return False
        q = Path(p)
        if not q.is_absolute():
            q = Path(root) / q
        return q.exists()

    # rebase first: a conflicted rebase ALSO leaves MERGE_MSG and an unmerged
    # index, so checking merge first would name the wrong command.
    for rel, name in (("rebase-merge", "rebase"), ("rebase-apply", "rebase"),
                      ("CHERRY_PICK_HEAD", "cherry-pick"),
                      ("REVERT_HEAD", "revert"), ("MERGE_HEAD", "merge")):
        if has(rel):
            return name
    return ""


# What `git commit` actually DOES mid-operation, measured on real repos rather
# than reasoned about — the first version of this message reasoned, and was
# wrong about three of the four:
#
#   merge / cherry-pick / revert   HEAD stays on the branch. `git commit`
#       CONCLUDES the operation: it exits 0, the operation state is gone, and
#       `git <op> --abort` afterwards fails with `fatal: There is no <op> to
#       abort` (rc 128) with the commit intact. So committing here is the
#       CORRECT move, and a verb that says STOP is refusing at the moment the
#       user is right.
#
#   rebase   HEAD is detached, and a commit finishes only the CURRENT step —
#       measured on a 3-commit rebase, `rebase-merge/` is still present after
#       the commit. `git rebase --abort` from there really does discard it.
#
# One sentence covering both would have to be true of neither, so this splits.
_SEQUENCER_CONCLUDED_BY_COMMIT = ("merge", "cherry-pick", "revert")


def _sequencer_next_action(op: str) -> str:
    if op in _SEQUENCER_CONCLUDED_BY_COMMIT:
        return ("a %s is in progress. Committing the staged resolution is what "
                "CONCLUDES it — `git %s --continue` is the same move under "
                "another name, and `git %s --abort` throws the resolution away. "
                "Check the staged diff is the resolution you meant, then commit."
                % (op, op, op))
    return ("STOP — a rebase is in progress and HEAD is detached. A commit here "
            "finishes only the CURRENT step, not the rebase, and `git rebase "
            "--abort` then discards it along with the rest. Run `git rebase "
            "--continue` until the rebase reports it is done.")


def _conflicted_paths(root: Path):
    """Unresolved paths via `git diff --cached --name-only --diff-filter=U`
    — catches an unmerged index left by a merge, rebase, OR cherry-pick
    without guessing at `.git/MERGE_HEAD` vs `REBASE_HEAD` vs
    `CHERRY_PICK_HEAD` (three paths for the same underlying git state; the
    diff-filter reads the index directly and needs none of them). On an
    unmerged path `git diff --cached` itself still exits 0 and prints only a
    "* Unmerged path <file>" marker line — no real diff content — which is
    exactly why DEFECT 2 slipped past the secret scanner and reported
    `ready`.

    Returns `(paths, error)`, same shape as `_staged_diff`: `error` is
    `None` on a clean git run (`paths` may legitimately be `[]` — no
    conflicts). `error` is git's own stderr when the invocation itself
    failed — a residue of the DEFECT-1/3 class this function used to
    collapse a subprocess failure into an empty list, indistinguishable
    from "no conflicts detected". Callers must check `error`, not just
    truthiness of `paths`."""
    r = subprocess.run(
        ["git", *_GIT_SAFE, "-C", str(root), "diff", "--cached", "--name-only", "--diff-filter=U"],
        capture_output=True, text=True, timeout=30, env=_git_env())
    if r.returncode != 0:
        return [], (r.stderr.strip()
                     or "git diff --cached --diff-filter=U exited %d" % r.returncode)
    return [p for p in r.stdout.splitlines() if p.strip()], None


def _staged_stats(root: Path):
    """(file_count, total_added_lines, error) from `git diff --cached
    --numstat`. `error` is `None` on a clean git run (an all-zero count may
    legitimately mean nothing staged — callers only reach this after
    confirming a non-empty diff, though). `error` is git's own stderr when
    the invocation itself failed — this function used to collapse that into
    a silent `(0, 0)`, the same indistinguishable-from-empty bug DEFECT 1
    fixed for `_staged_diff`, just deferred to the split-plan step."""
    r = subprocess.run(
        ["git", *_GIT_SAFE, "-C", str(root), "diff", "--cached", "--numstat"],
        capture_output=True, text=True, timeout=30, env=_git_env())
    if r.returncode != 0:
        return 0, 0, (r.stderr.strip()
                       or "git diff --cached --numstat exited %d" % r.returncode)
    files, added = 0, 0
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        files += 1
        try:
            added += int(parts[0])
        except ValueError:
            pass  # binary file ("-" column in numstat) — counts toward files, not lines
    return files, added, None


def cmd_commit_plan(argv: list, root: Path) -> dict:
    return hs_run_next_command.finalize(_cmd_commit_plan_impl(argv, root))


@_attrs.define(frozen=True, kw_only=True)
class CommitSummary:
    """The one artifact `commit-plan` hands a driver: what it is about to commit.

    Declared rather than typed inline so `files`/`added_lines` are ints by
    construction — a count that arrives as a string renders fine and compares
    wrong."""

    plan = _attrs.field()
    files: int = _attrs.field(converter=int)
    added_lines: int = _attrs.field(converter=int)

    def as_dict(self) -> dict:
        return _attrs.asdict(self)


@_attrs.define(frozen=True, kw_only=True)
class PushSummary:
    """The artifact every push-question state hands a driver.

    All four push states describe the same subject — this branch against its
    upstream — and were four inline dicts carrying between one and three keys.
    Declared once, a reader can ask for `commits` at any of them and get a list
    rather than a KeyError at three of the four."""

    upstream = _attrs.field(default=None)
    commits: list = _attrs.field(factory=list)
    gate_reason = _attrs.field(default=None)

    def as_dict(self) -> dict:
        return _attrs.asdict(self)


def _cmd_commit_plan_impl(argv: list, root: Path) -> dict:
    """`hs-run git next` — reports whether the staged diff is safe to
    commit and how to split it. Never runs `git commit`/`git push`, never
    touches the index: this verb PLANS a commit, the caller performs it.

    States: `nothing_staged` (EXIT_DONE — genuinely no repo, or a repo with
    nothing staged), `git_diff_failed` (EXIT_BROKEN — reused for every git
    invocation this verb makes that can fail on a REAL repo: DEFECT 1
    (`_staged_diff`'s `git diff --cached` itself failed, e.g. a corrupted
    object store), DEFECT 3 (`_git_repo_status` reports `"broken"` before a
    diff is ever attempted, e.g. a bad `repositoryformatversion` or a
    corrupt `.git/HEAD`/`.git/config`), and the same residue class in
    `_conflicted_paths` (`git diff --cached --diff-filter=U`) and
    `_staged_stats` (`git diff --cached --numstat`) — all are the same
    "git is present but its plumbing refuses to answer, fail CLOSED"
    situation, reusing the state means no new consumer wiring is needed in
    the state-vocabulary owner), `unresolved_conflict` (EXIT_BROKEN
    — DEFECT 2: an unmerged path is staged, so `git diff --cached` yields
    only a "* Unmerged path" marker with no real content for the secret
    scanner to see, and `git commit` itself refuses to run in this state),
    `secret_found` (EXIT_BROKEN — a high-confidence secret pattern hit the
    staged diff, mirrors the pre-ship hook's fail-closed posture, just moved
    earlier to commit time), `ready` (EXIT_NEEDS_MODEL — clear to commit; a
    model decides how to act on the split plan).

    `next_command` is `null` on EVERY path — an explicit
    claim, never an absent key. This verb reaches exit 0/2/10 only (measured:
    zero exit-11 assignment sites), and none of those tiers names a step a
    driver may run unattended: `ready` is exit 10 precisely because choosing
    HOW to stage and word the commit is the model's judgment, and every
    EXIT_BROKEN path here says stop (a corrupt repo, an unmerged index, a
    staged secret). Emitting a `git commit` string on any of them would invite
    a driver to run exactly the command the state exists to prevent."""
    if any(a in ("-h", "--help") for a in (argv or [])):
        return hs_run.StepResult(
            state="help",
            next_action=_USAGE + "\n\nwraps: hs_run_git.cmd_commit_plan\n\n"
                            "reports whether the staged diff (`git diff --cached`) is "
                            "safe to commit and how to split it. Never mutates the "
                            "index or HEAD.",
            artifacts=[],
            warnings=[],
            exit_code=EXIT_DONE,
        ).as_dict()

    # Help is answered above, then argv is parsed against an empty declaration --
    # this verb has no flags of its own. Measured before this line existed: a
    # mistyped flag was dropped without a word and the verb went on to report
    # `ready` with a 65-file commit plan. Of every verb in the family this is the
    # one where an affirmative answer to an unasked question costs the most, so it
    # refuses rather than guesses.
    #
    # `prog` names THIS internal step, not the public verb, on purpose. The one-
    # door fold removed `commit-plan` and `push-plan` from the registry (git.yaml
    # answers only to `next` now) and mechanically rewrote every literal
    # "hs-run git commit-plan"/"push-plan" string to "hs-run git next" — including
    # the three separate `parse_verb_argv` calls in this module, so a bad-argv
    # error raised from THIS function, from `cmd_push_plan`, and from `cmd_next`
    # itself all claimed the identical name. `cmd_next` always calls this function
    # with `argv=[]`, so this parse never actually fires through the real CLI —
    # but the function stays directly callable from Python (tests do exactly
    # that), and an error surfacing from it must say which internal step raised
    # it, not impersonate the one public command that no longer routes here.
    hs_run.parse_verb_argv("hs-run git next (commit-plan step)", argv)

    repo_status, repo_err = _git_repo_status(root)
    if repo_status == "broken":
        return hs_run.StepResult(
            state="git_diff_failed",
            next_action="STOP — git could not confirm %s is a repo (%s) — "
                            "the repo may be corrupted, fix git itself before "
                            "committing" % (root, repo_err),
            artifacts=[],
            warnings=[repo_err],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    if repo_status == "absent":
        return hs_run.StepResult(
            state="nothing_staged",
            next_action="nothing staged — `git add` first",
            artifacts=[],
            warnings=[],
            exit_code=EXIT_DONE,
        ).as_dict()

    diff, err = _staged_diff(root)
    if err is not None:
        return hs_run.StepResult(
            state="git_diff_failed",
            next_action="STOP — `git diff --cached` failed (%s) — the repo may "
                            "be corrupted, fix git itself before committing" % err,
            artifacts=[],
            warnings=[err],
            exit_code=EXIT_BROKEN,
        ).as_dict()

    conflicted, conflict_err = _conflicted_paths(root)
    if conflict_err is not None:
        return hs_run.StepResult(
            state="git_diff_failed",
            next_action="STOP — `git diff --cached --diff-filter=U` failed (%s) — "
                            "the repo may be corrupted, fix git itself before "
                            "committing" % conflict_err,
            artifacts=[],
            warnings=[conflict_err],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    if conflicted:
        return hs_run.StepResult(
            state="unresolved_conflict",
            next_action="STOP — unresolved merge conflict(s) in %s — resolve and "
                            "re-stage before committing" % ", ".join(conflicted),
            artifacts=[],
            warnings=conflicted,
            exit_code=EXIT_BROKEN,
        ).as_dict()

    # A resolved conflict is not a finished operation. `--diff-filter=U` reports
    # only UNRESOLVED paths, so the moment the reader runs `git add` the check
    # above goes quiet — while git is still mid-sequencer. Measured on that exact
    # tree: this verb answered `ready` and offered commit advice that named
    # neither the operation nor what committing would do to it.
    #
    # Read through git's own sequencer question rather than by guessing at
    # `.git/rebase-merge` vs `rebase-apply` vs `MERGE_HEAD` vs `CHERRY_PICK_HEAD`
    # — the same reasoning `_conflicted_paths` gives for using a diff-filter
    # instead of those four paths.
    #
    # The RUNG is not the same for all four (see `_sequencer_next_action` for the
    # measurements). Mid-merge/cherry-pick/revert, committing is the correct next
    # move — so this is rung 10, a step the model performs, and rung 2 would be
    # the verb calling the user's own repair "broken". Mid-rebase it really is
    # rung 2: HEAD is detached, the commit finishes one step of several, and the
    # `--abort` the reader reaches for next discards it.
    in_progress = _sequencer_in_progress(root)
    if in_progress:
        return hs_run.StepResult(
            state="sequencer_in_progress",
            next_action=_sequencer_next_action(in_progress),
            artifacts=[],
            warnings=["%s in progress" % in_progress],
            exit_code=(EXIT_NEEDS_MODEL
                       if in_progress in _SEQUENCER_CONCLUDED_BY_COMMIT
                       else EXIT_BROKEN),
        ).as_dict()

    if not diff.strip():
        return hs_run.StepResult(
            state="nothing_staged",
            next_action="nothing staged — `git add` first",
            artifacts=[],
            warnings=[],
            exit_code=EXIT_DONE,
        ).as_dict()

    hits = secret_scan.scan_diff_text(diff)
    if hits:
        return hs_run.StepResult(
            state="secret_found",
            next_action="STOP — staged diff matches secret pattern(s): %s — "
                            "unstage and rotate before committing" % ", ".join(hits),
            artifacts=[],
            warnings=hits,
            exit_code=EXIT_BROKEN,
        ).as_dict()

    files, added, stats_err = _staged_stats(root)
    if stats_err is not None:
        return hs_run.StepResult(
            state="git_diff_failed",
            next_action="STOP — `git diff --cached --numstat` failed (%s) — the "
                            "repo may be corrupted, fix git itself before "
                            "committing" % stats_err,
            artifacts=[],
            warnings=[stats_err],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    plan = "single" if (files <= _SPLIT_FILE_CEILING and added <= _SPLIT_LINE_CEILING) else "grouped"
    return hs_run.StepResult(
        state="ready",
        next_action="commit as a %s change (%d file(s), %d added line(s))"
                        % (plan, files, added),
        artifacts=[CommitSummary(plan=plan, files=files,
                                    added_lines=added).as_dict()],
        warnings=[],
        exit_code=EXIT_NEEDS_MODEL,
    ).as_dict()


def _git_read(root: Path, args: list):
    """(stdout, error) for a read-only git call, hardened the same way every other
    call in this module is. `error` is git's own stderr on a non-zero exit — never
    collapsed into an empty stdout, which is the ambiguity `_staged_diff`'s docstring
    records as a real bug: "" meant both "nothing there" and "git broke"."""
    r = subprocess.run(["git", *_GIT_SAFE, "-C", str(root), *args],
                       capture_output=True, text=True, timeout=30, env=_git_env())
    if r.returncode != 0:
        return "", (r.stderr.strip() or "git %s exited %d" % (args[0], r.returncode))
    return r.stdout.strip(), None


def cmd_push_plan(argv: list, root: Path) -> dict:
    """What a push from here would do, read before it is attempted.

    `commit-plan` stops at the commit. The step after it — is there an upstream, is
    anything ahead of it, would the pre-push gate refuse — was three git questions the
    push drawer described in prose and an agent had to remember to ask. Each is one
    read, and each names a different next move, so each is a state.

    Read-only, exactly like `commit-plan`: it never runs `git push`. The gate answer
    comes from `artifact_check.check_stage("push", root)`, the same function the
    pre-push hook calls, so this reports the hook's own verdict rather than a second
    opinion that could disagree with it.
    """
    # See `_cmd_commit_plan_impl`'s matching comment: `prog` names this internal
    # step, not the public `next` verb, so a bad-argv error raised here (only
    # reachable via a direct Python call — `cmd_next` always passes `argv=[]`)
    # does not impersonate the command that actually routes here.
    hs_run.parse_verb_argv("hs-run git next (push-plan step)", argv)
    status, detail = _git_repo_status(root)
    if status == "broken":
        return hs_run_next_command.finalize(hs_run.StepResult(
            state="git_diff_failed", exit_code=EXIT_BROKEN,
            next_action="STOP — git could not confirm %s is a repo (%s) — "
                        "the repo may be corrupted, fix git itself before "
                        "pushing" % (root, detail),
            warnings=[detail] if detail else [],
        ).as_dict())
    if status == "absent":
        # Mirrors `commit-plan`'s own fail-open contract for a directory that was
        # never a git repo at all. `_git_repo_status` already tells `absent` (no
        # `.git` anywhere up the tree) apart from `broken` (a `.git` present but
        # git's plumbing refuses to answer) — before this branch existed, both
        # collapsed into the same `status != "repo"` arm below, so a plain scratch
        # directory (never a repo) answered `git_diff_failed`/EXIT_BROKEN through
        # `cmd_next`'s fallthrough, while `commit-plan` alone answers the benign
        # `nothing_staged`/EXIT_DONE for the EXACT same tree. Measured directly
        # against a directory with no `.git` at all before this fix landed.
        return hs_run_next_command.finalize(hs_run.StepResult(
            state="nothing_staged", exit_code=EXIT_DONE,
            next_action="nothing staged — `git add` first",
        ).as_dict())

    upstream, err = _git_read(root, ["rev-parse", "--abbrev-ref", "@{u}"])
    if err or not upstream:
        # Not a failure: a branch nobody has pushed yet is the normal first push, and
        # the flag that fixes it is different from the flag a normal push uses.
        return hs_run_next_command.finalize(hs_run.StepResult(
            state="no_upstream", exit_code=EXIT_NEEDS_MODEL,
            next_action="this branch tracks nothing — the first push needs "
                        "`git push -u origin HEAD`, not a plain push",
            artifacts=[PushSummary().as_dict()],
        ).as_dict())

    ahead, err = _git_read(root, ["log", "@{u}..HEAD", "--oneline"])
    if err:
        return hs_run_next_command.finalize(hs_run.StepResult(
            state="git_diff_failed", exit_code=EXIT_BROKEN,
            next_action="git could not compare HEAD against %s — %s" % (upstream, err),
        ).as_dict())
    commits = [c for c in ahead.splitlines() if c.strip()]
    if not commits:
        return hs_run_next_command.finalize(hs_run.StepResult(
            state="nothing_to_push", exit_code=EXIT_DONE,
            next_action="HEAD is not ahead of %s — nothing to push" % upstream,
            artifacts=[PushSummary(upstream=upstream).as_dict()],
        ).as_dict())

    import artifact_check
    # The stage is MEASURED, not assumed. On a protected branch the pre-push gate
    # runs `merge`, which requires review-decision and plan-approval on top of
    # verification — so a hard-coded "push" reports a clear gate for a tree whose
    # real gate is about to refuse over two receipts it never read.
    import push_gate
    stage = push_gate.stage_for_checkout(root)
    blocked = artifact_check.check_stage(stage, root)
    if blocked:
        # A receipt gap the LOCAL hook only warns about. `push_gate.py` calls this same
        # check and then writes "[pre-push warn] … remote receipts-gate will enforce"
        # before returning None — measured on one tree, the push this state described as
        # refused went through with rc=0. So it is a model decision (rung 10), not a
        # broken repo (rung 2), and the sentence says what will actually happen.
        #
        # One exception, and it is not a receipt gap at all: with no plan resolved
        # there is nowhere for a receipt to live, so nothing the reader writes into
        # `plans/` clears this until a plan exists. `ship` and `fix` both call that
        # condition rung 2 for exactly that reason. Measured on one tree, this verb
        # answered rung 10 while `ship` answered rung 2 on the same repo — a driver's
        # next move then depended on which verb it happened to ask.
        #
        # The split is re-derived from disk — the same `resolve_active_plan` call
        # `ship` makes at its own fork — rather than by matching the reason's
        # wording: a reason string is written for a human and gets reworded, and two
        # domains keyed on its prose would drift apart the day someone improves a
        # sentence.
        #
        # `allow_completed` is READ from the same stage policy `check_stage` reads,
        # never defaulted. A stage that sets `allow_completed_plan: true` resolves a
        # `completed` plan where a bare call resolves None — and this branch would
        # then answer "no plan resolved" in an envelope whose next_action prints the
        # plan's own path. The first draft of this branch did exactly that: it
        # created the divergence it was written to close, and the domain's 31 tests
        # stayed green because no fixture uses a completed plan.
        #
        # Keyed on the MEASURED stage, not the literal "push". Two lines above,
        # `check_stage` is asked about `stage`, which is `merge` on a protected
        # branch — so reading `push`'s policy here asked one question of the gate
        # and a different one of the resolver. The two stages agree on
        # `allow_completed_plan` today (both true, measured), which is why nothing
        # had gone wrong; that is a coincidence of the config, not a guarantee, and
        # the day they diverge this branch would refuse a tree the gate accepted.
        _policy = artifact_check.load_policy()["stages"].get(stage) or {}
        plan_dir = artifact_check.resolve_active_plan(
            str(root),
            allow_completed=bool(_policy.get("allow_completed_plan", False)))
        if plan_dir is None:
            return hs_run_next_command.finalize(hs_run.StepResult(
                state="no_plan_resolved", exit_code=EXIT_BROKEN,
                next_action=blocked,
                artifacts=[PushSummary(upstream=upstream, commits=commits,
                                       gate_reason=blocked).as_dict()],
            ).as_dict())
        return hs_run_next_command.finalize(hs_run.StepResult(
            state="push_gate_blocked", exit_code=EXIT_NEEDS_MODEL,
            next_action="the push would go through locally, but CI's receipts-gate "
                        "will refuse it — %s" % blocked,
            artifacts=[PushSummary(upstream=upstream, commits=commits,
                                   gate_reason=blocked).as_dict()],
        ).as_dict())

    return hs_run_next_command.finalize(hs_run.StepResult(
        state="ready_to_push", exit_code=EXIT_NEEDS_MODEL,
        next_action="%d commit(s) ahead of %s and the push gate passes"
                    % (len(commits), upstream),
        artifacts=[PushSummary(upstream=upstream, commits=commits).as_dict()],
    ).as_dict())


def cmd_next(argv: list, root: Path) -> dict:
    """The one door. Which step applies is a disk question, not a choice.

    Anything staged means the commit question is still open; nothing staged means the
    commit already happened (or has not been prepared) and the push question is what
    is left. Answering that by hand puts a decision table back in the skill body,
    which is exactly what routing replaced.

    Order is the projection: the commit comes before the push, so `commit-plan` is
    asked first and only a `nothing_staged` answer falls through.
    """
    # This IS the public verb (the only row `git.yaml` registers), so `prog`
    # names the real command a bad-argv error here is about — unlike the two
    # internal steps below, whose OWN `parse_verb_argv` calls now say "(commit-
    # plan step)"/"(push-plan step)" precisely so a message from one of them is
    # never confused for coming from this one.
    hs_run.parse_verb_argv("hs-run git next", argv)
    staged = cmd_commit_plan([], root)
    if staged.get("state") != "nothing_staged":
        return _rerun_hint(staged)
    return _rerun_hint(cmd_push_plan([], root))


def _rerun_hint(out: dict) -> dict:
    """Point the reader back at `next`, never at whichever verb answered.

    An envelope naming the inner verb teaches the reader to pick verbs by hand again.
    Rungs 0 and 2 are left alone — nothing follows a finished or a broken step, and a
    re-run line there reads as "try again", which is not the next move. On rung 11 the
    hint goes in the SENTENCE only: `next_command` stays the bare runnable string.
    """
    if out.get("exit_code") in (EXIT_NEEDS_MODEL, EXIT_STEP_REMAINING):
        out["next_action"] = "%s — then: hs-run git next" % out.get("next_action")
    return out


if __name__ == "__main__":  # pragma: no cover - refusal path, asserted by subprocess
    # Not a command. On this ladder `0` is a CLAIM — "nothing left to do" — so a
    # module that runs here, does nothing and exits 0 tells an automated caller
    # the work is finished. Refuse loudly on the broken rung instead.
    import sys as _sys
    _sys.stderr.write(
        "%s is a hs-run domain module, not a command.\n"
        "Verbs are dispatched through the CLI, which resolves the project root, "
        "loads the registry and owns the exit ladder — none of which happens when "
        "this file is run on its own.\n"
        "Run it through the dispatcher instead:  hs-run %s <verb>\n"
        % (Path(__file__).name, 'git'))
    raise SystemExit(EXIT_BROKEN)
