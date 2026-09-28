#!/usr/bin/env python3
"""hs_run_security.py — the `security` domain's verb entry point for hs-run
(`mechanical-sweep`), promoted from an earlier draft.

Wrap, never rewrite (survival invariant #4, same discipline hs_run_cook.py
follows): REUSES `secret_scan_before_ship` for the secret half instead of a
second regex set — this is the THIRD consumer of that scanner (the pre-ship
compliance hook, `hs_run_git.py`'s not-yet-integrated `commit-plan`, and this
domain). `.env` exposure follows security-scan/SKILL.md:55's exact spec
("git ls-files .env* + .gitignore coverage"), verified against the live file
text before writing this, not guessed. Dep-audit command suggestion reuses
`detect_techstack.detect()` (the same function `hs_run_test.py`'s own draft
wraps).

sys.path precedent matched: guard_config.py:25-31 (two explicit inserts — this
module's own dir, then its `hooks/` sibling), not the draft's loop over a
tuple of paths — guard_config.py is the closer shape here because this module
needs exactly the same two directories (its own `harness/scripts/`, plus
`harness/hooks/` for `secret_scan_before_ship`), no more.

MECHANICAL ONLY — the boundary this module exists to keep sharp: this verb
reports what a deterministic sweep found (tracked `.env` files, secret
patterns in the working diff). It never renders a security VERDICT and never
assigns a severity; that judgment is STRIDE/OWASP reasoning, a model's job,
handed off to hs:security-scan. No `verdict`/`severity` key appears anywhere
in the returned envelope (pinned by
test_hs_run_security_domain.py::test_mechanical_sweep_never_emits_verdict_or_
severity_*).

Exit-tier choice (deviates from the draft, deliberately — see also
test_hs_run_security_domain.py's module docstring for the full argument):
`swept_clear`'s draft label was "Tier-11" while its OWN comment said the next
step is a model turn (STRIDE/OWASP reasoning) — a direct contradiction of
hs_run.py's documented ladder (10 = a model turn is required, 11 = one more
DETERMINISTIC step remains and `next_action` must be re-runnable verbatim;
enforced by hs_run.py's own `_looks_runnable`, which requires `next_action` to
contain `hs-run` or a backtick command). "run STRIDE/OWASP reasoning" is
neither, so at runtime the draft's own `exit_code: 11` would have been
silently forced to EXIT_BROKEN(2) by the dispatcher — the opposite of what a
clear sweep should report. `swept_clear` uses EXIT_NEEDS_MODEL(10) here
instead, matching the one already-integrated, already-tested precedent for
this exact shape: hs_run_cook.py's `needs_review` state (mechanical work
done, what remains is a reviewer's/model's judgment call) is EXIT_NEEDS_MODEL.
A hit found is `leak_found` on EXIT_BROKEN(2), mirroring `hs_run_git.py`'s own
fail-closed posture on a staged secret. (The single `swept_blocked` this line
once named is retired — see `_STATE_RUNGS` below for why one word could not
carry six unrelated next moves.)

Exit-code constants are IMPORTED from hs_run.py, which owns the ladder. The
per-module copies this line once described were retired after they drifted;
this module depends on hs_run.py at import time, deliberately.
"""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

import attrs as _attrs  # noqa: E402  (REQUIRED — see harness/requirements.txt)

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "hooks"))

import secret_scan_before_ship  # noqa: E402
import detect_techstack  # noqa: E402

# The four-tier ladder (D10), IMPORTED rather than re-declared.
# Ten modules used to hand-copy these four constants and had already drifted:
# rung 11 carried two different names across the tree and two modules declared
# the same constant twice. `hs_run` owns the ladder as a closed `Exit` IntEnum;
# both historical spellings of rung 11 are bound to the same member there, so
# this import changes no name any caller in this file uses.
import hs_run  # noqa: E402 — the shared verb-argv parser lives here
from hs_run import EXIT_BROKEN, EXIT_DONE, EXIT_NEEDS_MODEL, EXIT_STEP_REMAINING  # noqa: E402

# Keyed on the languages `detect_techstack.detect()` actually returns as
# `primary` — NOT on stack names a reader might assume. The table used to carry
# `"node"`, which that detector never emits (it returns `javascript`, or
# `typescript` when a tsconfig.json is present), so every Node project silently
# resolved to no suggestion at all while the row read as Node support.
# test_hs_run_security_dep_audit_vocabulary.py derives the reachable set from the
# detector itself and fails on any key that cannot be produced.
# Stacks intentionally absent (go/rust/java) have no ubiquitous audit command to
# name; they resolve to None and the sweep simply omits the dependency clause,
# which is the honest report rather than a guess.
_DEP_AUDIT_CMD = {
    "python": "pip-audit",
    "javascript": "npm audit",
    "typescript": "npm audit",
}

# EVERY git call below runs against a repository this verb does not control, and
# git reads that repository's own config — several keys of which name a program
# git then EXECUTES. Reused from `secret_scan_before_ship` rather than redefined:
# the two modules must harden identically or the weaker one becomes the way in,
# and this is a security posture, not a domain decision (the module's no-load-time-
# dependency-on-a-sibling-VERB discipline is about `hs_run_*.py` peers; this module
# already imports the scanner outright).
_GIT_SAFE = secret_scan_before_ship._GIT_SAFE_CONFIG
_git_env = secret_scan_before_ship._git_safe_env

def _no_repo_at_all(root: Path) -> bool:
    """True iff there is no git repository here to speak of — the ONE case a
    failed git call is universally safe to read as "legitimately nothing to
    scan" (nothing has ever been tracked, by definition).

    Checked directly against the FILESYSTEM (a `.git` entry — a directory
    for an ordinary repo, a file for a worktree/submodule pointer) rather
    than by parsing any single command's stderr text. That was the first
    approach here and it is UNRELIABLE: `git diff HEAD` on a repo with an
    unsupported `core.repositoryformatversion` ALSO prints a misleading
    "Not a git repository. Use --no-index..." line as a side effect of its
    own internal --no-index fallback attempt — even though a real (just
    broken-beyond-that-version) repository sits right there. A stderr
    substring match on "not a git repository" was fooled by this and read a
    genuinely broken repo as "nothing to scan", which is exactly the P1
    defect shape this whole module exists to close. Filesystem presence has
    no such ambiguity — verified against all 3 repro modes (healthy repo,
    corrupt index, bad repo version) plus the true no-repo-at-all case.

    WALKS THE FULL PARENT CHAIN up to the filesystem root — a plain
    `not (root / ".git").exists()` only checked ONE level, and `root` is
    routinely a SUBDIRECTORY of the real repo: `hs_run.py`'s own root
    resolution (`harness_root.resolve_project_root`) walks UP from CWD
    looking for a `plans/` dir OR a `.git` entry, and a subdirectory that
    itself carries a `plans/` child qualifies as the resolved root on ITS
    OWN, stopping short of the ancestor that actually holds `.git`. A
    one-level check then read that subdirectory as "no repo at all" and
    failed open — a broken PARENT repo (corrupt index, bad
    `core.repositoryformatversion`, ...) sitting one level up, holding a
    live secret, reported `swept_clear`.

    Deliberately mirrors `hs_run_git._git_dir_present` (harness/scripts/
    hs_run_git.py) — same parent-chain walk, same `.git`-as-FILE (worktree/
    submodule gitlink) handling, same "unreadable entry along the way keeps
    walking up" posture. NOT imported from there: `hs_run_git.py` is a
    different domain owner and this module's own discipline (see module
    docstring) is to carry no load-time dependency on a sibling verb
    module. A documented duplicate, not an oversight — if the two drift,
    grep both names together."""
    cur = root.resolve()
    while True:
        try:
            if (cur / ".git").exists():
                return False
        except OSError:
            pass  # unreadable entry — treat as "not found here", keep walking up
        parent = cur.parent
        if parent == cur:
            return True
        cur = parent


def _head_exists(root: Path) -> bool:
    """True iff `HEAD` resolves to a real commit, checked via `git rev-parse
    --verify HEAD`'s EXIT CODE only — never its stderr text.

    Replaces the prior `_is_unborn_head_stderr`, which matched the English
    prose `"ambiguous argument 'head'"`. That single message is git's
    fatal text for THREE genuinely different situations: a zero-commit
    repo (benign — nothing has ever been committed), an ORPHAN BRANCH
    (`git checkout --orphan`, a normal, supported state with a real,
    non-empty INDEX), and `HEAD` pointing at a dead/missing ref. In the
    last two, a STAGED secret is invisible to the rest of the sweep:
    `git add` already moved it out of the untracked listing
    (`_secret_grep_worktree`'s other half), so only a read of the staged
    surface could have seen it — and the stderr-text match sent both
    straight into the "nothing to see, skip" branch alongside the truly
    benign zero-commit case, silently reporting `swept_clear` over a live
    staged secret (verified: `hs-run git next` on the SAME tree
    correctly returns `secret_found` — two gates disagreeing on one tree).

    Exit code is locale-stable where prose is not: `git rev-parse --verify
    HEAD` returns non-zero exactly when HEAD cannot be resolved to a single
    revision, regardless of the running system's language.

    KNOWN WEAK SPOT, verified by hand (see
    `test_head_exists_true_even_though_corrupt_index_breaks_diff`): a
    corrupt `.git/index` does NOT stop ref resolution — this returns True
    even though `git diff HEAD` / `git diff --cached` both fail on the
    same repo. That is by design, not a gap: it is what routes the
    corrupt-index break mode to the genuine-git-error branch in
    `_secret_grep_worktree` (fail closed with `git_errors`) instead of the
    "HEAD does not exist yet, fall back to the staged diff" branch, where
    the fallback would ALSO fail — for the wrong reason."""
    r = subprocess.run(["git", *_GIT_SAFE, "-C", str(root), "rev-parse",
                        "--verify", "HEAD"],
                        capture_output=True, text=True, errors="replace", timeout=15, env=_git_env())
    return r.returncode == 0


def _gitignore_covers_env(root: Path) -> bool:
    """Does this repo's ignore configuration cover `.env`? Asked of GIT, which is the
    thing that decides.

    This was a substring test (`any(".env" in line ...)` over `.gitignore`) and it was
    wrong on six of nine measured shapes — three of them in the reassuring direction. A
    `!.env.example` negation line contains the substring and was read as coverage; so
    was an unrelated `docs/.env-notes.md`; a bare `*` (ignore everything) was read as
    NO coverage.

    `pathspec`, which this repo declares and uses for gitignore semantics elsewhere,
    scores 8/9 on the same cases and is blind to exactly one thing: a rule living in
    `.git/info/exclude` rather than `.gitignore` (global `core.excludesFile` is the same
    blind spot). This module already shells out to git for `git ls-files` and already
    fails closed on a git that will not answer, so the authority costs no new mechanism
    here — which is the one situation where reaching past a declared library is right.

    `--no-index`: the question is whether the PATTERN covers `.env`, not whether the
    file is untracked at this instant. A `.env` that is already tracked is the separate,
    louder finding `tracked_env_files` carries.

    Fail-closed. An unanswerable git returns False (no coverage claimed), never True —
    a reassuring answer from a broken probe is the same lie by a different road.

    Carries `_GIT_SAFE`/`_git_env()` like every other git call here: this runs against a
    repository the verb does not control, whose own config can name programs git then
    executes. A hardening prefix that most calls carry is not a hardening prefix."""
    try:
        r = subprocess.run(
            ["git", *_GIT_SAFE, "-C", str(root), "check-ignore", "-q",
             "--no-index", ".env"],
            capture_output=True, text=True, errors="replace", timeout=15, env=_git_env())
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


# Suffixes that mark a committed `.env*` as a TEMPLATE rather than a leak. Matched on
# the whole filename's ending, never as a substring: `.env.example.real` contains the
# word `example` and is a real env file — its suffix is `.real`. A `"example" in name`
# carve-out would wave that through while reading, to a later maintainer, exactly like
# a correct check.
#
# `.dist` is deliberately absent even though `secret_scan_before_ship._EXCLUDE_RE`
# carries it: that regex governs a CONTENT scan, where the cost of a false negative is
# one unread file among thousands. Here the whole finding is "this path is tracked",
# and `.env.dist` is not an established convention the way the three below are. A
# suffix added here must be a convention a project follows on purpose, not merely a
# name that looks harmless.
_ENV_TEMPLATE_SUFFIXES = (".example", ".sample", ".template")


def _is_env_template(rel: str) -> bool:
    """True for the `.env.example` family — committed on purpose, placeholders only."""
    name = rel.rsplit("/", 1)[-1]
    return name.endswith(_ENV_TEMPLATE_SUFFIXES)


def _env_exposure(root: Path) -> dict:
    """Tracked `.env` files (a real leak, not merely a risk) plus whether
    `.gitignore` covers the `.env` pattern (defense-in-depth).

    THE PATHSPEC RECURSES, and the plain `".env*"` it replaces did not. A
    pathspec anchors at its base, so `git ls-files ".env*"` matched only the
    repository root. Measured on git 2.43.0, one repo, all three force-added:

        git ls-files ".env*"            -> .env, .env.example
        git ls-files ':(glob)**/.env*'  -> .env, .env.example, svc/.env

    One function, wrong in both directions at once. A tracked `svc/.env` — a
    committed secret file, the exact finding this check exists for — returned
    clean; a tracked `.env.example` — a template every project commits on
    purpose — blocked the sweep. The template family is filtered by
    `_is_env_template` rather than by the pathspec, so the pathspec stays the
    simple "every `.env*` at any depth" claim and the judgment about which of
    them is benign lives in one readable place.

    `.env/README.md` is NOT matched, and that is the pathspec's own semantics
    rather than an accident this code arranges: glob `*` does not cross `/`, so
    a file inside a directory NAMED `.env` never reads as a `.env` file
    (verified — the widened pathspec returns it in neither form).

    `-z`, for the same reason `_secret_grep_worktree`'s untracked listing uses
    it: with `core.quotePath` on (the default) git prints a non-plain-ASCII
    name QUOTED AND C-ESCAPED, so `.env.café` arrives as the literal
    `".env.caf\\303\\251"`. Under `str.splitlines()` that becomes a tracked-file
    entry naming a path that does not exist, reported to a human as the leak's
    location. Measured both ways on the same repo.

    FAIL-CLOSED ON A BROKEN GIT, fail-open only on the one genuinely safe
    case: `git ls-files` failing is NOT read as "no tracked files" across the
    board — only when `_no_repo_at_all` confirms there is no repository at
    all (nothing has ever been tracked, by definition). Any OTHER git failure
    (a corrupt index, a bad `core.repositoryformatversion`, dubious
    ownership, ...) sets `error` in the returned dict instead of silently
    reporting an empty `tracked_env_files` — the caller
    (`cmd_mechanical_sweep`) treats a set `error` as a blocker. This
    replaces the prior `r.stdout.splitlines() if r.returncode == 0 else []`
    shape, which read EVERY git failure — including a broken repo sitting on
    top of a real tracked secret — as "nothing tracked" (P1).

    DELIBERATELY TRACKED-ONLY, by spec, not an oversight: `git ls-files` is
    inherently a tracked-file listing, and the two-part check (tracked
    exposure + gitignore coverage) is a repo-HYGIENE lint, not a
    content scan — `gitignore_covers_env: False` is exactly the signal that
    an untracked `.env` sitting in the tree today is one careless `git add .`
    away from becoming tracked. An untracked `.env` that already matches a
    real secret PATTERN is still caught separately, by `_secret_grep_
    worktree`'s untracked-content read below (unless it also happens to be
    gitignored — see that function's own docstring for why that exclusion is
    deliberate too). The two checks are complementary, not redundant: this
    one is about hygiene, that one is about content."""
    r = subprocess.run(["git", *_GIT_SAFE, "-C", str(root), "ls-files", "-z",
                        ":(glob)**/.env*"],
                        capture_output=True, text=True, errors="replace", timeout=15, env=_git_env())
    error = None
    if r.returncode == 0:
        tracked = [f for f in r.stdout.split("\x00")
                   if f.strip() and not _is_env_template(f)]
    elif _no_repo_at_all(root):
        tracked = []  # no repository at all — nothing has ever been tracked
    else:
        tracked = []
        error = r.stderr.strip() or "git ls-files exited %d" % r.returncode
    result = {"tracked_env_files": tracked,
              "gitignore_covers_env": _gitignore_covers_env(root)}
    if error is not None:
        result["error"] = error
    return result


_UNTRACKED_READ_CAP = 1_000_000  # bytes; matches secret_scan_before_ship.gather_pack_surface's
# own cap verbatim (harness/hooks/secret_scan_before_ship.py:239) — a secret sits near the
# top of a config file, so bounding read size keeps a huge generated/vendored untracked
# artifact from hanging the sweep, without a second, independently-chosen constant.


def _secret_grep_worktree(root: Path) -> tuple:
    """Scans the CURRENT working-tree surface for secret patterns: tracked
    changes vs HEAD (staged + unstaged) PLUS untracked file CONTENT — a
    fixed regression (the original promotion only read the HEAD diff, which
    is blind to a brand-new file nobody has `git add`-ed yet; a freshly
    created file is exactly where a leaked credential is most likely to
    sit). Reuses `secret_scan_before_ship.scannable_added_lines`/`scan_text`/
    `_excluded` directly — no second pattern table, no second exclusion
    regex.

    Returns `(hits, unreadable, git_errors)`: `hits` unchanged (matched
    pattern names); `unreadable` is the repo-relative paths listed by `git
    ls-files --others` whose CONTENT could not be determined (see the
    open()-failure split below); `git_errors` is non-empty when either git
    read itself (the `diff HEAD`/its `diff --cached` fallback, or the
    `ls-files --others` call) failed for a reason that is NOT one of the
    known-safe cases (see `_no_repo_at_all`/`_head_exists` and their
    callers below) — a corrupt index, a bad `core.repositoryformatversion`,
    dubious ownership, or any other broken-git state. The caller
    (`cmd_mechanical_sweep`) fails the sweep CLOSED whenever either list is
    non-empty. This replaces the prior `if returncode == 0: ... # else:
    vacuously fine to skip` / `if returncode == 0: ...` (no else at all)
    shape, which read EVERY git failure on either call — including a broken
    repo sitting on top of a real secret — as "nothing to report" (P1).

    Untracked listing uses `-z` (NUL-delimited, never `str.splitlines()` on
    the default quoted/escaped form) — `git ls-files --others` prints a
    filename holding a non-plain-ASCII byte (or a `"`/`\\`) QUOTED AND
    C-ESCAPED when `core.quotePath` is on (the default): the on-disk name
    `config"prod.env.txt` comes back as the literal 9-char-longer string
    `"config\\"prod.env.txt"`. `open()`-ing THAT string raises
    FileNotFoundError, not the real file — so a naive `splitlines()` parse
    silently walks straight past the leak. `-z` also survives a filename
    holding a space or a literal newline, which the quoted form only escapes.

    A file the listing names but `open()` cannot then read splits into THREE
    genuinely different cases, not two — `OSError` is the shared parent of the
    last two and must not be caught as a single class, and the first case is
    checked BEFORE `open()` is even attempted (matched with
    `secret_scan_before_ship.gather_pack_surface`: same split, same order, and
    the two sites reach the same VERDICT for each case. They deliberately do
    NOT report the same list of NAMES — `gather_pack_surface` returns at the
    FIRST offending entry, so its `unreadable` names one path, while this loop
    continues and collects every one. Same decision, different reporting
    granularity; a raising classifier is likewise routed to `unreadable` at
    BOTH sites rather than escaping one of them):
      - a listed entry ending in "/" — `git ls-files --others` collapses an
        untracked NESTED GIT REPOSITORY it refuses to descend into to ONE
        entry with a trailing slash (no per-file listing), e.g. `vendor-lib/`.
        This is content the scan NEVER SAW, not "nothing to scan": `open()`
        on it raises `IsADirectoryError`, the same exception a directory
        symlink raises, so before this check it fell straight into the
        carve-out below and vanished silently — the exact regression a
        `git clone`-ed dependency reproduces. An ordinary directory never
        appears in this listing at all (git tracks no empty directories, and
        a non-nested one is listed file-by-file), so a trailing "/" is
        unambiguous.

        Checked BEFORE `secret_scan_before_ship._excluded(rel)` below, not
        after: a name matching the test/fixture/example exclusion regex
        (`examples/`, `tests/`, `fixtures/`, ...) must not `continue` straight
        past this boundary check — the exclusion exists to skip noisy FAKE
        credentials in files actually scanned, never to wave an entire
        unscanned nested repository through by name alone (the P1 defect this
        ordering fixes: only `vendor-lib/`, the one name the exclusion regex
        happens not to match, was ever caught by the prior order).

        `secret_scan_before_ship._classify_nested_boundary` then narrows this
        to the genuine leak-risk shape: a linked WORKTREE or a genuinely EMPTY
        nested repo is skipped (`continue`, not a leak, and blocking either
        wedges an ordinary workflow — see that function's own docstring,
        `harness/plugins/hs/skills/worktree/scripts/worktree.cjs:372` places
        worktrees INSIDE the repo in monorepo mode); everything else — real
        content, or the classification itself failing — is appended to
        `unreadable` and the loop moves on (matching this function's own
        already-established continue-and-collect convention below, unlike
        `gather_pack_surface`'s early-return convention) — deliberately NOT
        descended into and scanned: see the module docstring /
        `secret_scan_before_ship.gather_pack_surface`'s own docstring for the
        option A vs B trade-off this repeats verbatim.
      - `FileNotFoundError` / `IsADirectoryError` (after the "/" check above
        has already ruled out the nested-repo shape) — a file that vanished
        between listing and open (a broken symlink, or a plain TOCTOU race —
        this is also the fix for the list-then-open race a concurrent build
        can trigger: the file existed when `git ls-files` ran and is gone by
        `open()` time), or a directory symlink (the shape `node_modules`/
        vendored trees produce constantly). Both are FACTS, not unknowns:
        there is no scannable text behind either — skipped, not blocked.
      - any other `OSError` (permission denied, etc.) — genuinely UNKNOWN
        content: appended to `unreadable`, and the caller fails CLOSED on
        it, the same posture `secret_scan_before_ship.gather_pack_surface`
        takes on its own unreadable-file case. A secret gate that silently
        counts an unread file as clean is the exact defect this fixes;
        warn-only would repeat it under a different name.

    This is deliberately NOT a call to `secret_scan_before_ship.gather_pack_
    surface` (the module's own existing tracked+untracked combiner): that
    function's tracked-diff read and untracked-file read are coupled — a
    missing HEAD (a genuinely brand-new repo, zero commits) makes its FIRST
    `git diff HEAD` call fail and it returns None outright, silently
    skipping the untracked half too, even though `git ls-files --others`
    needs no HEAD at all and would have worked fine. Decoupled here so a
    zero-commit repo's untracked content still gets scanned — "no commits
    yet" and "has untracked work" are genuinely different states (only the
    first is safe to call clear on its own; the second never is, regardless
    of whether HEAD exists).

    Untracked listing uses `--exclude-standard` (skips gitignored paths),
    matching `gather_pack_surface`'s own already-established choice and
    agreeing with `git status --porcelain`'s default behavior
    (decision_capture.py/check_fence.py's own precedent — ignored paths
    never surface without an explicit `--ignored`): a vendored/build/
    node_modules-style dir a project has already chosen to gitignore is
    exactly the large-and-likely-binary hazard this bound exists to skip,
    not a place a maintainer is about to commit a secret from. Binary
    detection (a NUL byte in the first 4KB) and the size cap mirror
    `gather_pack_surface` exactly, matching its already-tested constants
    rather than inventing new ones."""
    parts = []
    git_errors = []

    diffed = subprocess.run(["git", *_GIT_SAFE, "-C", str(root), "diff", "HEAD",
                             "--no-color"],
                             capture_output=True, text=True, errors="replace", timeout=30, env=_git_env())
    if diffed.returncode == 0:
        parts.append(secret_scan_before_ship.scannable_added_lines(diffed.stdout))
    elif _no_repo_at_all(root):
        pass  # not a git repo at all — nothing tracked to diff against; genuinely
        # fine to skip, the untracked read below still runs independently.
        # Filesystem check, never a stderr-text match — `git diff HEAD` prints a
        # misleading "Not a git repository" line of its own on a REAL but broken
        # repo too (see `_no_repo_at_all`'s docstring).
    elif not _head_exists(root):
        # HEAD does not resolve — a zero-commit repo, an ORPHAN BRANCH, or HEAD
        # pointing at a dead ref all land here (checked by `git rev-parse
        # --verify HEAD`'s EXIT CODE, see `_head_exists`, never by matching
        # git's own prose). None of the three is safe to wave through unread:
        # `git add` already moved any staged content out of the untracked
        # listing below, so a STAGED secret is invisible unless read here.
        # `git diff --cached` works with no HEAD at all (git diffs the index
        # against the implicit empty tree) — empty when nothing is staged
        # (the benign case), the real staged content otherwise.
        cached = subprocess.run(
            ["git", *_GIT_SAFE, "-C", str(root), "diff", "--cached", "--no-color"],
            capture_output=True, text=True, errors="replace", timeout=30, env=_git_env())
        if cached.returncode == 0:
            parts.append(secret_scan_before_ship.scannable_added_lines(cached.stdout))
        else:
            # HEAD genuinely does not exist AND the staged-diff fallback also
            # failed — git itself is broken in a way ref-resolution alone
            # didn't catch (e.g. a bad repositoryformatversion also blocks
            # this). Must not be silently read as "nothing staged".
            git_errors.append("git diff --cached failed: %s" % (
                cached.stderr.strip() or "exit %d" % cached.returncode))
    else:
        # HEAD resolves fine but `git diff HEAD` still failed — git is broken
        # in a way that doesn't touch ref resolution (corrupt index, dubious
        # ownership, ...) — must NOT be silently read as "nothing tracked".
        git_errors.append("git diff HEAD failed: %s" % (
            diffed.stderr.strip() or "exit %d" % diffed.returncode))

    unreadable = []
    others = subprocess.run(
        ["git", *_GIT_SAFE, "-c", "core.excludesFile=" + os.devnull,
         "-C", str(root), "ls-files", "--others", "--exclude-standard", "-z"],
        capture_output=True, text=True, errors="replace", timeout=30, env=_git_env())
    if others.returncode == 0:
        for rel in others.stdout.split("\x00"):
            if not rel:
                continue
            if rel.endswith("/"):
                # boundary check runs BEFORE _excluded() below — see this
                # function's own docstring for why (P1: an excluded name must
                # not wave an entire unscanned nested repo through unread)
                #
                # Wrapped: the classifier reads an untrusted directory, and the
                # pre-ship hook's own call site has always been inside a
                # try/except that fails CLOSED. Here the exception used to
                # escape the verb entirely; the dispatcher caught it and still
                # produced valid JSON + exit 2, so nothing leaked, but the two
                # sites reached that verdict by different routes. Now both make
                # the same decision in the same place.
                try:
                    shape = secret_scan_before_ship._classify_nested_boundary(
                        root / rel, root)
                    if shape == "worktree":
                        # a VERIFIED own worktree is scanned, not skipped — see
                        # `scan_worktree_content`. Undeterminable content is an
                        # unknown, routed to `unreadable` like any other.
                        wt = secret_scan_before_ship.scan_worktree_content(root / rel)
                        if wt is None:
                            unreadable.append(rel)
                        else:
                            parts.append(wt)
                        continue
                except Exception:
                    shape = "content"  # unknown — never "nothing to scan"
                if shape == "empty":
                    continue  # nothing this scan needs to see, not a leak risk
                # "content" (or the classification itself failed) — fail
                # closed; content never scanned, not verified clean
                unreadable.append(rel)
                continue
            if secret_scan_before_ship._excluded(rel):
                continue
            try:
                with open(root / rel, encoding="utf-8", errors="replace") as fh:
                    chunk = fh.read(_UNTRACKED_READ_CAP)
            except (FileNotFoundError, IsADirectoryError):
                continue  # ordinary: no scannable text behind it — not an unknown
            except OSError:
                unreadable.append(rel)  # genuinely unreadable — unknown, not
                continue                # clean; caller fails closed on this
            if "\x00" in chunk[:4096]:
                continue  # binary (keystore/image/archive) — no text secret to scan
            parts.append(chunk)
    elif _no_repo_at_all(root):
        pass  # not a git repo at all — no tracked/untracked distinction to
        # read; the tracked-diff half above already degraded the same way.
    else:
        # git itself is broken — same posture as the diff branch above: an
        # untracked secret could be sitting there unread, must not pass silently.
        git_errors.append("git ls-files --others failed: %s" % (
            others.stderr.strip() or "exit %d" % others.returncode))

    text = "\n".join(parts)
    hits = secret_scan_before_ship.scan_text(text)
    if not hits:
        # secret_scan_before_ship.gate_reason's own cross-line collapse pass — catches a
        # token split across two adjacent added lines.
        hits = secret_scan_before_ship.scan_text(text.replace("\n", ""))
    return hits, unreadable, git_errors


def _untracked_env_files(root: Path) -> list:
    """Untracked `.env*` files sitting on disk right now, template family excluded.

    The third input `env_unprotected` needs, and the reason it is a separate read:
    `_env_exposure` asks what is TRACKED (already a leak) and `_gitignore_covers_env`
    asks whether the ignore rules would catch one. Neither answers "is there actually
    an `.env` here to protect" — and firing a rung-11 fix-it step at a project that
    has never had an `.env` is noise a user learns to skip past.

    `--exclude-standard` is doing real work here rather than riding along: it is what
    makes this read AGREE with the gitignore question instead of contradicting it. A
    `.env` the rules already cover does not appear in this listing at all, so the
    state cannot fire on a tree that is already protected. Measured: three untracked
    `.env*` before adding the rule, one after (the template, which is filtered here).

    Fail-quiet by design, and it is safe here only because of where the result is
    consumed: an empty list can never turn a finding INTO a clear sweep — it can only
    fail to raise `env_unprotected`, which is the weakest of the seven states and the
    only one that reports no danger. Every read whose emptiness could be mistaken for
    safety (`git_errors`, `unreadable`, `env["error"]`) fails CLOSED instead, in the
    functions above."""
    try:
        r = subprocess.run(
            ["git", *_GIT_SAFE, "-C", str(root), "ls-files", "--others",
             "--exclude-standard", "-z", ":(glob)**/.env*"],
            capture_output=True, text=True, errors="replace", timeout=15, env=_git_env())
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    return [f for f in r.stdout.split("\x00")
            if f.strip() and not _is_env_template(f)]


# Each state's rung, declared as data next to the classifier that assigns it.
#
# A table rather than a literal at each `return`, because the pairing IS the
# contract: rung 10 says a model turn is required, 11 says one deterministic step
# remains, 2 says broken. `leak_found` on rung 10 would let a driver loop treat a
# committed credential as ordinary work, and that mistake is invisible at the return
# site and obvious here.
#
# `swept_blocked` is deliberately absent. It carried six reasons across three groups
# whose next moves are unrelated, which is the collapse this vocabulary replaces.
_STATE_RUNGS = {
    "leak_found": EXIT_BROKEN,
    "repo_unreadable": EXIT_BROKEN,
    "scan_incomplete": EXIT_NEEDS_MODEL,
    "no_repo": EXIT_NEEDS_MODEL,
    "env_unprotected": EXIT_STEP_REMAINING,
    "swept_clear": EXIT_NEEDS_MODEL,
    "swept_clear_no_dep_tool": EXIT_NEEDS_MODEL,
}


def _gitignore_append_command(root: Path) -> str:
    """The one deterministic step `env_unprotected` promises, as a string a driver
    runs VERBATIM.

    Not `echo .env >> .gitignore`. A `.gitignore` whose last line has no trailing
    newline is ordinary, and the naive append WELDS the new rule onto it —
    `node_modules` + `.env` becomes the single line `node_modules.env`, which
    destroys a working ignore rule and creates nothing. So the command checks for the
    missing newline first. Verified by running it against all four shapes (trailing
    newline, no trailing newline, empty file, absent file) and reading the bytes
    back; the test executes it rather than matching its text.

    `shlex.quote` on the path: a project directory holding a space is common enough
    (`~/My Documents/...`), and this string is handed to a shell."""
    gi = shlex.quote(str(root / ".gitignore"))
    return ("sh -c 'f=$1; if [ -s \"$f\" ] && [ -n \"$(tail -c1 \"$f\")\" ]; "
            "then echo >> \"$f\"; fi; echo .env >> \"$f\"' _ %s" % gi)


def _classify(*, tracked_env_files, env_error, secret_hits, unreadable, git_errors,
              no_repo, gitignore_covers_env, untracked_env_files, dep_audit_cmd,
              root, artifacts=()):
    """Findings -> one named state. The ORDER of these branches is the contract.

    `repo_unreadable` FIRST, ahead of `leak_found`. When git will not answer,
    `secret_hits` is an empty list nothing measured, and an unmeasured empty list is
    indistinguishable from a clean one at the point of use. Reporting any finding
    derived from that read — including the reassuring absence of one — states more
    than this sweep knows. Put the leak check first and a broken repository sitting
    on a live secret gets a confident, wrong diagnosis.

    Then `leak_found` (a confirmed leak outranks an incomplete read: it has a
    rotation deadline), then `scan_incomplete` (the scan ran and hit a wall — more
    specific than `no_repo`, which says the git half never ran), then `no_repo`, then
    `env_unprotected`, then the two clear answers.

    Returns `hs_run.StepResult`, the SHARED value object, with the state name spelled
    as a LITERAL at each return. Neither half of that is stylistic, and both were
    learned by breaking them:

      * A private result class here made the state map empty. `render_state_map.
        emitted_states` reads this module's AST for a literal `state=` on a
        `StepResult(...)`/`Envelope(...)` call; a different class is invisible to it,
        and the renderer emitted a map with two blank tables and exit 0 — which reads
        as "this domain has no states" rather than as a failure.
      * Routing every branch through a local `_v(state, ...)` helper failed the same
        reader for the same reason one layer in: the literal then sits at the CALL
        site and the `StepResult` sees only a parameter name. Measured — the reader
        reported `[]` for this module with the helper in place.

    The same reader backs `test_hs_run_step_routing.py`'s reachability gate, so in
    both shapes the registry's seven rows would have been reported as routing dead
    vocabulary while the CLI printed those states on every run.

    So the repetition below is load-bearing: a state name a static reader cannot see
    is a state that is not documented and not checked. Each rung still comes from
    `_STATE_RUNGS` rather than a hand-typed int, and a name typo raises `KeyError`
    at the branch instead of inventing a state."""
    if git_errors or env_error:
        reasons = list(git_errors)
        if env_error:
            reasons.append("could not verify .env exposure: %s" % env_error)
        return hs_run.StepResult(
            state="repo_unreadable", exit_code=_STATE_RUNGS["repo_unreadable"],
            next_action="STOP — git itself could not answer, so nothing here was "
                        "measured. Repair the repository first; a clear result from a "
                        "broken probe is worth nothing: " + "; ".join(reasons),
            artifacts=list(artifacts), warnings=reasons)

    if tracked_env_files or secret_hits:
        reasons = []
        if tracked_env_files:
            reasons.append("tracked .env file(s): %s" % ", ".join(tracked_env_files))
        if secret_hits:
            reasons.append("secret pattern(s) in working tree: %s"
                           % ", ".join(secret_hits))
        return hs_run.StepResult(
            state="leak_found", exit_code=_STATE_RUNGS["leak_found"],
            next_action="STOP — a secret is exposed in this tree. Remove it from the "
                        "commit and ROTATE the credential before anything else: "
                        + "; ".join(reasons),
            artifacts=list(artifacts), warnings=reasons)

    if unreadable:
        # Split by shape for the WORDING only. Both mean the same next move — go read
        # that path — which is why they are one state; the difference is reported
        # rather than made structural.
        nested = [u for u in unreadable if u.endswith("/")]
        files = [u for u in unreadable if not u.endswith("/")]
        reasons = []
        if nested:
            reasons.append("untracked nested git repo(s) this scan cannot descend into "
                           "— content never scanned, not verified clean: %s"
                           % ", ".join(nested))
        if files:
            reasons.append("could not read %s (permission denied or similarly "
                           "unreadable)" % ", ".join(files))
        return hs_run.StepResult(
            state="scan_incomplete", exit_code=_STATE_RUNGS["scan_incomplete"],
            next_action="part of this tree was never read — check the listed paths "
                        "yourself before drawing any conclusion from the rest: "
                        + "; ".join(reasons),
            artifacts=list(artifacts), warnings=reasons)

    if no_repo:
        return hs_run.StepResult(
            state="no_repo", exit_code=_STATE_RUNGS["no_repo"],
            next_action="there is no git repository here, so every git-based read was "
                        "SKIPPED — this is not a clean result. Scan the whole tree by "
                        "hand, or run this from inside the repository that owns these "
                        "files.",
            artifacts=list(artifacts),
            warnings=["no git repository — the git-based reads did not run"])

    if not gitignore_covers_env and untracked_env_files:
        return hs_run.StepResult(
            state="env_unprotected", exit_code=_STATE_RUNGS["env_unprotected"],
            next_action="no leak yet, but %s is untracked AND the ignore rules do not "
                        "cover `.env` — one careless `git add .` makes it a leak. Run "
                        "the command in `next_command` to close it."
                        % ", ".join(untracked_env_files),
            # `root` is REQUIRED rather than defaulted, and this line is why. It was
            # `root=None` with a `... if root is not None else None` guard here, which
            # made the one rung-11 state constructible with no command — and rung 11
            # promises exactly that command. `StepResult.__attrs_post_init__` refuses
            # it, so the guard did not degrade the envelope, it raised from inside the
            # verb. A caller that cannot supply a root cannot answer this state at all,
            # so the signature says so instead of failing later.
            next_command=_gitignore_append_command(root),
            artifacts=list(artifacts),
            warnings=["untracked and unignored: %s" % ", ".join(untracked_env_files)])

    if dep_audit_cmd:
        return hs_run.StepResult(
            state="swept_clear", exit_code=_STATE_RUNGS["swept_clear"],
            next_action="mechanical sweep clear — spawn STRIDE/OWASP reasoning via "
                        "hs:security-scan (dep audit: %s)" % dep_audit_cmd,
            artifacts=list(artifacts), warnings=[])

    return hs_run.StepResult(
        state="swept_clear_no_dep_tool",
        exit_code=_STATE_RUNGS["swept_clear_no_dep_tool"],
        next_action="mechanical sweep clear — spawn STRIDE/OWASP reasoning via "
                    "hs:security-scan. This stack declares NO dependency-audit "
                    "command; say so rather than inventing one.",
        artifacts=list(artifacts), warnings=[])


@_attrs.define(frozen=True, kw_only=True)
class SweepArtifact:
    """What the mechanical sweep actually read, declared once.

    Each field is a SEPARATE read that either completed or did not. Keeping them
    as distinct declared fields is what lets `summary_numbers` say "scanned,
    found nothing" rather than "could not scan" — a `0` meaning both is exactly
    the ambiguity this artifact exists to remove.

    `env` is a dict, not a list like its three neighbours: it carries the tracked
    file list AND whether the read itself failed (`error`), which is the very
    distinction above and cannot be expressed by an empty list."""

    env: dict = _attrs.field(factory=dict)
    secrets: list = _attrs.field(factory=list)
    unreadable: list = _attrs.field(factory=list)
    git_errors: list = _attrs.field(factory=list)
    dep_audit_cmd = _attrs.field(default=None)

    def as_dict(self) -> dict:
        return _attrs.asdict(self)


def cmd_mechanical_sweep(argv: list, root: Path) -> dict:
    """`hs-run security next` — the mechanical half of a security pass: secret
    grep + `.env` exposure, with a dep-audit command surfaced (never run — no
    dependency installs, no network).

    READS the tree, then hands every finding to `_classify`, which owns the
    state vocabulary and the priority order. The two are split because the
    order is the part with a cost attached and the part that needs testing
    without a disk: `repo_unreadable` outranks `leak_found` because a broken
    git yields an empty hit list nothing measured, and staging "git is broken
    AND there is a tracked secret" as a real fixture is not something a test
    can do unambiguously.

    Seven states, not two. The rungs are declared in `_STATE_RUNGS`; the
    narrow, filesystem/exit-code-checked exceptions that keep a failed git
    read fail-OPEN live in `_env_exposure` and `_secret_grep_worktree`."""
    # The sweep takes no flags of its own, and `argv` is parsed against an empty
    # declaration rather than ignored. A dropped token here is the worst shape of
    # all: this verb can answer with a clean bill of health, and it must not
    # answer that to a call whose operator typed something it never understood.
    hs_run.parse_verb_argv("hs-run security next", argv)
    env = _env_exposure(root)
    secret_hits, unreadable, git_errors = _secret_grep_worktree(root)
    stack = detect_techstack.detect(root)
    # `detect` returns primary=None for a repo it recognises no stack in, and a dict
    # lookup on None is a lookup nobody meant to make. "" reaches the same "no audit
    # command for this stack" branch by a key that actually is one.
    primary = stack.get("primary") or ""
    dep_cmd = _DEP_AUDIT_CMD.get(primary)
    no_repo = _no_repo_at_all(root)

    artifacts = [SweepArtifact(env=env, secrets=secret_hits, unreadable=unreadable,
                               git_errors=git_errors, dep_audit_cmd=dep_cmd).as_dict()]

    verdict = _classify(
        tracked_env_files=env["tracked_env_files"],
        env_error=env.get("error"),
        secret_hits=secret_hits,
        unreadable=unreadable,
        git_errors=git_errors,
        no_repo=no_repo,
        gitignore_covers_env=env["gitignore_covers_env"],
        # Read ONLY when the cheap conditions for `env_unprotected` already hold.
        # Every earlier branch outranks it, so on a tree with a real finding this
        # git call cannot change the answer — and running it anyway would spend a
        # subprocess on every clean sweep to inform a state that cannot fire.
        untracked_env_files=(_untracked_env_files(root)
                             if not env["gitignore_covers_env"] and not no_repo
                             else []),
        dep_audit_cmd=dep_cmd,
        root=root,
        artifacts=artifacts,
    )

    # `summary_numbers` renders each count from ITS OWN read having actually
    # completed, not from which state the classifier landed on — a `0` here must
    # mean "scanned, found nothing", never "could not scan". `env.get("error")`
    # means `_env_exposure`'s tracked-file read never produced a real list (P1
    # shape: a literal "0 tracked .env, 0 secret pattern hit(s)" printed whenever
    # git itself failed, identical text to a genuinely clear scan).
    # `git_errors` covers BOTH halves of `_secret_grep_worktree` (the tracked
    # diff and the untracked read), so a failure on either side marks the
    # secret count "n/a" too — a partial read is not a verified zero.
    #
    # The rule stated above has four cases and only two were implemented. The
    # other two are the states where the scan never STARTED rather than failing
    # partway: no repository at all, and a tree the sweep could not fully
    # descend. Both printed real counts. Measured on a directory holding an AWS
    # key with no `.git`: `summary_numbers = "0 tracked .env, 0 secret pattern
    # hit(s)"` shipped in the SAME envelope as the advisory "Do not report this
    # as clean. Every number in this envelope is zero because nothing ran."
    #
    # The advisory does not cover for it. That is prose a caller may summarise
    # away; `summary_numbers` is the field a caller pastes verbatim, so the two
    # must not be able to disagree. A rule half-applied is worse than unapplied
    # here — the two cases it does cover make the other two look deliberate.
    unmeasured = ("n/a (no repository)" if no_repo
                  else "n/a (tree not fully read)" if unreadable else None)
    env_count = (unmeasured or ("n/a (git failed)" if env.get("error")
                                else str(len(env["tracked_env_files"]))))
    secret_count = (unmeasured or ("n/a (git failed)" if git_errors
                                   else str(len(secret_hits))))
    summary_numbers = "%s tracked .env, %s secret pattern hit(s)" % (env_count, secret_count)

    blob = verdict.as_dict()
    blob["summary_numbers"] = summary_numbers
    return blob


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
        % (Path(__file__).name, 'security'))
    raise SystemExit(EXIT_BROKEN)
