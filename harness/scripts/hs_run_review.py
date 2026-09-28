#!/usr/bin/env python3
"""hs_run_review.py — the `review` domain's verb entry points for hs-run.

Promoted from an earlier draft — the last of 6 domains sketched there,
alongside git/review-pr/test/ship/security. Wraps 3 already-existing public functions
(signatures verified against the real source, not guessed):

  - review_recall.resolve_effort(flag=None, env=None, config=None) -> str
  - review_recall.assess_scope(changed_files, root=".", config=None) -> dict
  - rule_view.load_rules_dual(root, changed_files) -> (dict, str)
  - risk_rubric.derive_risk(root, changed_files, *, policy=None) -> Risk (namedtuple)

`_changed_files()` (`git status --porcelain -z -uall` — every staged,
unstaged, AND untracked path, matching the repo's own convention in
check_fence.py/decision_capture.py — a review runs on what's about to be
committed, not on history, and a brand-new file nobody `git add`-ed yet is
exactly what review matters most for) is the only new glue; everything else
is a call-through.

Judgment boundary (why this module stays this thin): `cmd_next` gathers
scope/rules/risk and reports readiness, it never renders a verdict. The
judgment half of code review — is this diff actually OK — belongs to a
spawned reviewer (hs:code-review), not to a CLI verb; that is exactly why
`cmd_next` returns EXIT_NEEDS_MODEL rather than trying to decide anything
itself.

Fail-open-class fix (round 3 of the same shape hs_run_git.py's `_staged_diff`
and hs_run_security.py's `_env_exposure`/`_secret_grep_worktree` already
closed): `_changed_files` used to read `git status --porcelain -z -uall`'s
non-zero exit exactly like a clean tree — both fell through to `return []`,
which `cmd_next` read as `nothing_changed` / EXIT_DONE, "done, proceed",
on a repo git cannot even answer. `_changed_files` now returns
`(paths, error)`; `error` is git's own stderr on a REAL repo whose plumbing
refuses to answer (corrupt index, bad `core.repositoryformatversion`,
corrupt `.git/HEAD`, ...) and must never be silently folded into "nothing
changed". `_git_dir_present` is copied verbatim from hs_run_git.py's own
function of the same name (matched, not reinvented) — it walks the parent
chain and treats `.git` as either a directory or a worktree/submodule
`gitdir:` pointer FILE, because this CLI's resolved root is routinely a
SUBdirectory of the actual repo (`harness_root.resolve_project_root` stops
at the nearest ancestor carrying a `plans/` dir OR a `.git` entry — a
`plans/` marker one level down from the real `.git` is enough to land root
there), and a one-level `(root / ".git").exists()` check reads that
subdirectory as "never a repo" instead of walking up to the real one.

State-name decision: REUSES `git_diff_failed` rather than minting a new
name. hs_run_git.py's own docstring for that state already generalizes it
past its literal name — "reused for BOTH DEFECT 1 ... AND DEFECT 3 ...
[both] the same 'git is present but its plumbing refuses to answer, fail
CLOSED' situation" — so the name already means "git itself is broken", not
narrowly "the diff call failed". This module's failure is the exact same
underlying condition (git present, plumbing refusing to answer) surfacing
through a different command (`git status` here vs `git diff --cached`
there); reusing the name continues that established generalization instead
of fragmenting one semantic into a second, domain-local synonym, and it
needs zero new wiring in test_hs_run_contract_conformance.py's
KNOWN_STATES/_NEVER_DONE (the name is already in both, already paired with
EXIT_BROKEN(2) everywhere it appears).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import attrs as _attrs  # noqa: E402  (REQUIRED — see harness/requirements.txt)

import artifact_check
import hs_run_next_command
import review_recall
import scope_match
import risk_rubric
import mechanical_runner
import rule_view

# Hardening for the git call below, IMPORTED from its definition site. git reads the
# inspected repository's own config, and keys such as `core.fsmonitor` name a program
# git then EXECUTES; this verb runs git against a repo it does not own. `harness/hooks`
# joins sys.path for this the same way hs_run_git.py/hs_run_security.py already do it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
import secret_scan_before_ship as _secret_scan  # noqa: E402

_GIT_SAFE = _secret_scan._GIT_SAFE_CONFIG
_git_env = _secret_scan._git_safe_env

# The four-tier ladder (D10), IMPORTED rather than re-declared.
# Ten modules used to hand-copy these four constants and had already drifted:
# rung 11 carried two different names across the tree and two modules declared
# the same constant twice. `hs_run` owns the ladder as a closed `Exit` IntEnum;
# both historical spellings of rung 11 are bound to the same member there, so
# this import changes no name any caller in this file uses.
import hs_run  # noqa: E402
from hs_run import EXIT_BROKEN, EXIT_DONE, EXIT_NEEDS_MODEL, EXIT_NEEDS_STEP  # noqa: E402


def _git_dir_present(root: Path) -> bool:
    """True iff a `.git` entry (a directory for a normal repo, OR a FILE for
    a worktree/submodule gitlink) exists anywhere from `root` up to the
    filesystem root. Copied verbatim from hs_run_git.py's function of the
    same name (see that module for the full rationale) rather than imported
    across domains — matches this repo's existing per-domain-module
    convention (hs_run_security.py's own `_no_repo_at_all` duplicates the
    same on-disk-presence idea locally instead of importing hs_run_git.py
    too)."""
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


def _changed_files(root: Path):
    """Every changed path under `root`: staged, unstaged, AND untracked.
    Returns `(paths, error)`.

    `git diff --name-only HEAD` (the first cut of this glue) only sees
    TRACKED files — blind to a brand-new file nobody has `git add`-ed yet,
    which is exactly the shape review matters most for. Matches the repo's
    own convention for "what changed" (`check_fence.py:_porcelain_paths`,
    `decision_capture.py:_porcelain_changes`): `git status --porcelain -z
    -uall`, NUL-delimited so a path containing a space or newline still
    parses unambiguously, `-uall` so a new file is listed individually
    rather than collapsed into its untracked parent directory. Gitignored
    files are excluded — that's plain `git status`'s own default (no
    `--ignored`), and it's the right default for review too: build output,
    caches, and lockfiles nobody asked to review would otherwise flood the
    scope on every run.

    `error` is `None` on a clean git run (`paths` may legitimately be empty —
    genuinely nothing changed, OR genuinely never a repo at all: both are the
    same honest "nothing to review" floor, `_git_dir_present` is what tells
    the two apart when `git status` itself failed, not when it succeeded).
    `error` is git's own stderr when git IS present (`_git_dir_present`
    confirms a `.git` entry exists somewhere up the parent chain) but its
    plumbing refuses to answer (corrupt index, bad
    `core.repositoryformatversion`, corrupt `.git/HEAD`, ...) — that case
    must never be silently folded into `paths == []` by the caller (that was
    the defect: an empty list meant BOTH "nothing changed" and "git broke",
    so a broken repo reported EXIT_DONE `nothing_changed` while real,
    unreviewed, untracked work sat on disk). A `.git` entry that exists but
    was never actually initialized by git (a stray empty dir/file someone
    manually named `.git`) reads as "broken" here instead of "absent",
    over-blocking a directory that was never really a repo — the same
    accepted trade-off `hs_run_git.py:_git_repo_status` documents: a spurious
    STOP costs a manual check, a spurious PASS costs an unreviewed diff."""
    r = subprocess.run(
        ["git", *_GIT_SAFE, "status", "--porcelain", "-z", "-uall"],
        cwd=str(root), capture_output=True, text=True, timeout=30, env=_git_env())
    if r.returncode != 0:
        if _git_dir_present(root):
            return [], (r.stderr.strip()
                        or "git status --porcelain exited %d" % r.returncode)
        return [], None  # genuinely never a repo — the existing benign path
    paths = []
    fields = r.stdout.split("\x00")
    i = 0
    while i < len(fields):
        rec = fields[i]
        if not rec:
            i += 1
            continue
        xy, path = rec[:2], rec[3:]
        if path:
            paths.append(path)
        # A rename/copy record's original path follows as its own NUL field
        # (`R  dest\x00orig`) — skip it, it is not itself a "changed" path
        # distinct from the rename entry already recorded.
        if xy and xy[0] in ("R", "C"):
            i += 1
        i += 1
    return paths, None


# ------------------------------------------------------- standards emission

@_attrs.define(frozen=True, kw_only=True)
class ReviewSummary:
    """What one review pass found. `applied`/`scanned_files` are counts by
    construction, so a length that arrives as the list itself is a TypeError at
    the call site rather than a number that renders as `[...]`."""

    critical = _attrs.field()
    findings: list = _attrs.field(factory=list)
    applied = _attrs.field(default=0, converter=int)
    scanned_files = _attrs.field(default=0, converter=int)

    def as_dict(self) -> dict:
        return _attrs.asdict(self)


@_attrs.define(frozen=True, kw_only=True)
class ReviewBundle:
    """The scope/rules/risk bundle this verb prepares for a code-reviewer.

    Seven fields assembled inline, one of which (`rule_count`) is a derived
    number whose comment already warns it must not be confused with the wrapper
    dict's own key count. A derived value inside an anonymous literal is exactly
    where that confusion happens."""

    effort = _attrs.field()
    changed_files: list = _attrs.field(factory=list)
    scope = _attrs.field(default=None)
    rules_source = _attrs.field(default=None)
    rule_count = _attrs.field(default=0, converter=int)
    standards = _attrs.field(default=None)
    risk = _attrs.field(default=None)

    def as_dict(self) -> dict:
        return _attrs.asdict(self)


def _standards_bundle(rules, changed, root):
    """`(bundle, warnings)` — WHICH operational rules govern this diff, and which of
    them actually FIRED on it.

    This verb already loaded the scope-matched rule set and then emitted a NUMBER:
    `rule_count: 50`, with no rule id anywhere in the envelope. A reviewer was told how
    many rules applied and had to go find them, which is the manual step this exists to
    remove. Seven of those fifty were `severity: critical`.

    Findings come from `mechanical_runner.run_grep_detectors`, never a local scan: that
    module owns the scope matching, the line scan, the file-size cap and the ReDoS
    budget, and a second implementation is a second thing to keep correct.

    Fail-soft, matching `load_rules_dual`'s own posture — a defect in the layer that
    DESCRIBES the rules must never block the review it describes."""
    # `rules` carries the rule OBJECTS; `rules_applied` is a list of id STRINGS. Reading
    # the latter for severity/detector returns a clean, confident, empty answer — the
    # loader raises nothing and the bundle just says "no critical rules", which is
    # indistinguishable from a genuinely unregulated diff.
    applied = [r for r in ((rules or {}).get("rules") or []) if isinstance(r, dict)]
    critical = sorted({str(r.get("id")) for r in applied
                       if isinstance(r, dict) and r.get("severity") == "critical"
                       and r.get("id")})
    findings, warnings = [], []
    grep_rules = [r for r in applied
                  if isinstance(r, dict) and isinstance(r.get("detector"), dict)
                  and r["detector"].get("type") == "grep"]
    if grep_rules and changed:
        try:
            findings = list(mechanical_runner.run_grep_detectors(
                grep_rules, list(changed), root=str(root)) or [])
        except Exception as exc:  # noqa: BLE001 — see the docstring: never block a review
            warnings.append("standards detectors did not run (%s) — rule ids below are "
                            "still authoritative, but nothing was scanned" % exc)
            findings = []
    for f in findings:
        warnings.append("%s %s:%s %s" % (
            f.get("rule_id", "?"), f.get("file", "?"), f.get("line", "?"),
            str(f.get("text", "")).strip()[:160]))
    return (ReviewSummary(critical=critical, findings=findings,
                          applied=len(applied),
                          scanned_files=len(changed or [])).as_dict(), warnings)


def _history_mode_token(bare: list):
    """The first positional naming a HISTORY mode, or None.

    Three shapes, taken from `code-review/SKILL.md`'s own mode list: the literal
    word `codebase`, a `#`-prefixed PR number, and a commit-ish (a bare hex run
    long enough to be an abbreviated SHA — git's own floor is 4, and 7 is what it
    prints, so 7 is the floor used here rather than a number invented for this
    check).

    Deliberately narrow. Anything it does not recognise falls through to the
    worktree answer, which is the documented default and what `parse_known_args`
    above exists to preserve — a token this cannot classify must not become a
    refusal. Levels are excluded first: they are positionals too, and `low` is
    four hex-ish characters away from looking like a mistake.
    """
    import re as _re
    for tok in list(bare or []):
        t = str(tok).strip()
        if not t or review_recall._norm_level(t) is not None:
            continue
        if t == "codebase":
            return t
        if t.startswith("#") and t[1:].isdigit():
            return t
        if len(t) >= 7 and _re.fullmatch(r"[0-9a-fA-F]+", t):
            return t
        # The first positional that is not a level decides. A later token is a
        # path or a passthrough argument, matching `_effort_shorthand`'s own
        # "only the FIRST positional" reading of the same argv.
        return None
    return None


def _effort_shorthand(argv: list):
    """The two abbreviated spellings code-review/SKILL.md documents alongside
    `--effort <level>`: the `--<level>` shorthand, and a bare leading token kept
    for back-compat.

    Validated against `review_recall`'s own level vocabulary rather than a list
    repeated here — a second copy would drift the moment a level is added, and
    validating is what keeps `--pending` or a stray word from being read as a
    level. Only the FIRST positional token is considered, matching the documented
    "bare leading token" wording: a later positional is a path or a mode
    argument, not an effort."""
    argv = list(argv or [])
    for a in argv:
        if a.startswith("--") and review_recall._norm_level(a[2:]) is not None:
            return a[2:]
    for a in argv:
        if a.startswith("-"):
            continue
        return a if review_recall._norm_level(a) is not None else None
    return None


def cmd_next(argv: list, root: Path) -> dict:
    """Gather scope/rules/risk for a pending review — fully mechanical, never
    a verdict. Exit 0 ("nothing_changed") when the working tree has nothing
    changed at all (staged, unstaged, or untracked) to review. Otherwise exit
    10: everything this verb
    CAN compute deterministically is already in `artifacts[0]`, but the next
    real step (spawn a reviewer to judge the diff) is a model turn this
    process cannot perform itself.

    `next_command` is `null` on every path — explicitly, never
    absent. This verb has no exit-11 state (measured: zero exit-11 assignment
    sites), and its `ready` tier is exit 10 for the reason above: the next step
    is a reviewer's judgment, which is precisely what no command can run."""
    return hs_run_next_command.finalize(_cmd_next_impl(argv, root))


def _structural_globs_hit(root: Path, changed: list) -> list:
    """Which structural globs this diff touches, or [] for none.

    Wraps the pair `artifact_check._architecture_review_reason` already uses —
    `_load_structural_globs` for the set and `scope_match.scope_matches` for the
    match — rather than re-deciding what counts as structural. Two opinions on
    that question would drift, and the drift would show up as this verb briefing
    a reviewer the later gate then contradicts.

    Returns the matching globs rather than a bool, because "your diff is
    structural" without naming WHICH pattern caught it leaves the reader to
    re-derive a per-project set they could not guess in the first place.

    A standards file that cannot be read yields [] — the later gate is the one
    that blocks, and a briefing verb guessing at a config it could not load
    would be inventing the answer rather than reading it.
    """
    try:
        globs = artifact_check._load_structural_globs(str(root))
    except Exception:  # noqa: BLE001 — an unreadable standards file is "no claim"
        return []
    return [g for g in (globs or [])
            if scope_match.scope_matches([g], changed)]


def _cmd_next_impl(argv: list, root: Path) -> dict:
    # ARGUMENT questions are answered before TREE questions, and the order is the
    # whole point rather than a style choice. `wrong_door` is a fact about what
    # was ASKED; `nothing_changed` and `git_diff_failed` are facts about the tree.
    # With the tree read first, `hs-run review next '#123'` on a clean tree
    # returned `nothing_changed` exit 0 — "done, proceed" — which is exactly the
    # confident wrong answer the refusal exists to prevent, delivered to the one
    # caller who is not asking about this tree at all. Measured on a fresh repo
    # with `git status` empty: state `nothing_changed`, exit 0.
    #
    # All four rungs code-review/SKILL.md publishes: explicit arg > env >
    # config > default. `resolve_effort` has always implemented them; this call
    # used to pass only the first, so an operator's HARNESS_REVIEW_EFFORT had no
    # effect and no warning said so. `config=None` keeps resolve_effort's own
    # file lookup in charge of the third rung rather than second-guessing it here.
    # Flag set DERIVED from review_recall.LEVELS, never restated: this verb
    # accepts `--effort <level>` and the `--<level>` shorthand alike, so a hand
    # copy would reject the next level the moment one is added there.
    p = hs_run.VerbParser(prog="hs-run review next")
    p.add_argument("--effort")
    for _lvl in review_recall.LEVELS:
        p.add_argument("--%s" % _lvl, action="store_true")
    p.add_argument("bare", nargs="*")
    # parse_KNOWN_args, deliberately — unlike cook's verbs this one's argv is
    # NOT a closed set. `code-review/SKILL.md` documents a bare leading token as
    # a level, and callers pass through arguments this verb has no opinion on
    # (`--pending` among them). `test_an_unknown_token_does_not_masquerade_as_a
    # _level` pins both halves: an unrecognised token must neither be read as a
    # level NOR break the call — it falls through to the default.
    # So the typo-catching that closed cook's holes is knowingly NOT applied
    # here; the vocabulary check that matters (is this token a real level?)
    # lives in `_effort_shorthand`, validated against review_recall's own list.
    ns, _unknown = p.parse_known_args(list(argv or []))

    # A PR number, a commit-ish, or the word `codebase` asks about HISTORY. This
    # verb reads the worktree, so it has no answer for any of the three, and
    # `code-review/SKILL.md:69-71` already says so in prose: "PR / commit /
    # codebase modes read history, not the worktree, so the verb does not apply
    # there". The verb did not enforce it — measured, `#123`, `abc1234def` and
    # `codebase` all returned the SAME worktree verdict with the same
    # `changed_files`, so a caller asking about a PR was handed a confident answer
    # about a different tree, with nothing in the envelope to tell them apart.
    #
    # A REFUSAL, not a new state. Naming the mode would turn a silent wrong answer
    # into a labelled wrong answer; the honest move is to say this door does not
    # open onto that question and name the one that does. Rung 2: the verb's job
    # could not run, and no model turn on this tree changes that.
    mode = _history_mode_token(ns.bare)
    if mode:
        return hs_run.StepResult(
            state="wrong_door", exit_code=EXIT_BROKEN,
            next_action=(
                "`%s` asks about history (a PR, a commit, or the whole codebase); "
                "this verb reads the WORKING TREE and would answer about a "
                "different diff entirely. Use `review_recall.py --effort <level>` "
                "for those modes." % mode),
            warnings=["argument %r names a history mode this verb does not "
                      "serve" % mode],
        ).as_dict()

    # Tree questions, now that the argument is known to be one this verb serves.
    changed, err = _changed_files(root)
    if err is not None:
        return hs_run.StepResult(
            state="git_diff_failed", exit_code=EXIT_BROKEN,
            next_action="STOP — `git status` could not read %s (%s) — the "
                        "repo may be corrupted, fix git itself before "
                        "reviewing" % (root, err),
            artifacts=[], warnings=[err],
        ).as_dict()
    if not changed:
        return hs_run.StepResult(
            state="nothing_changed", exit_code=EXIT_DONE,
            next_action="no working-tree changes under %s" % root,
        ).as_dict()

    effort = review_recall.resolve_effort(
        ns.effort or _effort_shorthand(argv),
        os.environ.get("HARNESS_REVIEW_EFFORT"),
    )
    scope = review_recall.assess_scope(changed, root=str(root))
    rules, rules_source = rule_view.load_rules_dual(str(root), changed)
    risk = risk_rubric.derive_risk(str(root), changed)

    standards, std_warnings = _standards_bundle(rules, changed, root)

    warnings = list(std_warnings)
    suggested = scope.get("suggested_effort")
    if suggested and effort and suggested != effort:
        warnings.append(
            "requested --effort=%s differs from scope-suggested %s" % (effort, suggested))

    # The fan-out fork, read off the effort that was already resolved above. `low` is
    # one pass by one reviewer; medium and up spawn, which means routing through
    # orchestration first and running the recall ladder. Two steps, so two states —
    # otherwise the single-pass reviewer is handed paperwork for a fan-out it is not
    # doing, and the budget the state must fit is the union of both.
    # The threshold is derived from review_recall.LEVELS, not a list spelled here, so a
    # new rung lands on the right side of the fork the day it is added. The two state
    # names are bare literals in one same-function assignment on purpose: the state-map
    # renderer and the routed-state gate both resolve a local only when it is assigned
    # a literal here, so `State.READY_RECALL` written out would make this emit
    # invisible to them and the map would under-report the vocabulary.
    single_pass = effort == review_recall.LEVELS[0]
    state = "ready" if single_pass else "ready_recall"

    # The structural fork, read from the SAME pair the pr/ship gate reads
    # (`artifact_check._architecture_review_reason`). Told here rather than at
    # that gate because the gate fires a whole review cycle later: a reviewer who
    # was not briefed pays the round trip to discover the diff needed an
    # architecture pass. The glob set is per-project — this repo's is
    # `harness/hooks/**` + `harness/scripts/**`, not the `src/**` a reader would
    # assume — so it is not inferable, only readable, which is exactly the case a
    # state is for.
    #
    # The fork is about the DIFF; `state` above is about the EFFORT. They are
    # independent questions, and returning here used to answer only the first:
    # a structural diff at `--max` produced a byte-identical envelope to the same
    # diff at `--low`, so the reviewer lost everything `ready_recall` routes —
    # measured, 4 rules + 1 reference, `orchestration-protocol` among them, which
    # is the one that tells a high-effort review how to fan out. The recall
    # instructions are carried in the envelope rather than dropped, because a
    # structural diff at high effort needs BOTH answers, not the newer one.
    structural = _structural_globs_hit(root, changed)
    if structural:
        out = hs_run.StepResult(
            state="needs_architecture_review", exit_code=EXIT_NEEDS_MODEL,
            next_action=(
                "this diff is structural (matches %s) — the reviewer must judge "
                "it against docs/system-architecture.md and record "
                "architecture_review{checked, doc_sha, drift[]} in the "
                "review-decision, or the pr/ship gate refuses it later%s"
                % (", ".join(structural),
                   "" if single_pass else
                   " — and this is a %s-effort run, so the recall ladder in "
                   "references/recall-mode.md applies on top of it" % effort)),
            artifacts=[ReviewBundle(
                effort=effort, changed_files=changed, scope=scope,
                rules_source=rules_source,
                rule_count=len((rules or {}).get("rules_applied") or []),
                standards=standards, risk=risk._asdict()).as_dict()],
            warnings=warnings,
            extra={"structural_globs": list(structural)},
        ).as_dict()
        # The flag that restores what this branch used to drop. Set on the DICT,
        # not through the constructor — `StepResult` has no `route_flags` field
        # (measured: it raises TypeError), and the dispatcher pops the key off the
        # result mapping, which is the same seam `hs_run_plan._attach_route_flags`
        # writes through.
        #
        # Only when the run is NOT single-pass, so a low-effort structural run
        # keeps its budget of 2; `review.yaml`'s `when_flag: recall:` block holds
        # the five documents themselves.
        if not single_pass:
            out["route_flags"] = ("recall",)
        return out

    return hs_run.StepResult(
        state=state, exit_code=EXIT_NEEDS_MODEL,
        next_action="spawn a code-reviewer with this scope/rules/risk bundle "
                    "(this verb only prepares the inputs, it never judges the diff)",
        # applied-rule count, not the wrapper dict's own key count (that dict
        # always carries the same ~4 top-level keys regardless of what actually
        # matched — counting those would silently report a constant no matter
        # what changed).
        artifacts=[ReviewBundle(
            effort=effort, changed_files=changed, scope=scope,
            rules_source=rules_source,
            rule_count=len((rules or {}).get("rules_applied") or []),
            standards=standards, risk=risk._asdict()).as_dict()],
        warnings=warnings,
    ).as_dict()


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
        % (Path(__file__).name, 'review'))
    raise SystemExit(EXIT_BROKEN)
