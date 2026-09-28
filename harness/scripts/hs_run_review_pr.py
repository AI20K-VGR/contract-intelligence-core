#!/usr/bin/env python3
"""hs_run_review_pr.py — the `review-pr` domain's `next` verb for hs-run.

Read-only CI-state gathering for the PR/MR on the current branch. It never
posts a comment, approves, merges, or pushes — it only tells the caller what
the forge's own CLI currently reports, so the model can apply
review-pr/SKILL.md's verdict rules itself. Two things kept deliberately OUT of
this module because they are the model's job, not this CLI's: deciding
Approve/Request-changes, and picking which findings matter.

Forge selection follows review-pr/SKILL.md:37-46 and its
references/forge-detection.md exactly — substring match on `git remote
get-url origin` (`gitlab` before `github`, case-sensitive, mirroring the
skill's own `case "$REMOTE_URL" in *gitlab*) ... *github*) ... *)` shell
pattern), one CLI for the whole call, never both. An unrecognised remote
(including no remote at all) is `unknown_forge`: the skill's own rule is
"inspect all remotes and ASK, do not guess" — this verb cannot ask, so it
stops and hands that instruction back as `next_action` rather than picking a
CLI at random.

Two real gaps in the original scaffold this module closes, not just wraps:

  1. The scaffold's `gh pr checks --json name,state` does not work — `gh pr
     checks` (installed: 2.45.0) has no `--json` flag at all ("unknown flag:
     --json"). The correct machine-readable source for check state is `gh pr
     view --json statusCheckRollup`, used below.
  2. The scaffold only ever called `gh`, collapsing "not authenticated" and
     "still running" into the same `ci_pending` retry. Both CLIs ship a real
     `auth status` subcommand; `_cli_auth_status` calls it before ever
     touching checks, so an auth problem is reported as `cli_unauthenticated`
     — not spun on forever as if it were just slow CI.

Design invariant carried over from the scaffold, worth restating because
getting it wrong reopens the exact bug class this exists to avoid: `--poll-n`
is REQUIRED, never defaulted to 0. The round counter lives in the
`next_action` STRING the caller is told to run verbatim, never in a progress
file or the model's own counting — a silent default-0 would let a caller
"forget" the count and poll past the ceiling forever.

Neither `gh pr checks`'s per-job JSON shape nor `glab ci get`'s pipeline JSON
was exercised against a live PR/MR while writing this (no such fixture was
available) — both fetchers are defensive about unexpected shapes, but treat
that as probed-from-docs-and-`--help`, not proven against a real forge.
"""
from __future__ import annotations

import json
import shlex

import attrs as _attrs  # noqa: E402  (REQUIRED — see harness/requirements.txt)
import shutil
import subprocess
import sys
from pathlib import Path

import hs_run_next_command

# Hardening for the git call below, IMPORTED from its definition site. git reads the
# inspected repository's own config, and keys such as `core.fsmonitor` name a program
# git then EXECUTES; this verb runs git against a repo it does not own.
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
#
# THREE of the four are imported, not all four. `EXIT_NEEDS_MODEL` (rung 10, "a
# model turn is required") is absent because this verb never reaches it: every
# human-decision state it can return — unauthenticated, no CLI installed, an
# unresolved forge — is one where the verb learned NOTHING about the PR, and the
# exit ladder cannot carry "the tooling could not ask" apart from "CI failed"
# anyway. `state` is what tells those apart. The skill body used to promise rung
# 10 for exactly those three; the prose was corrected to match the code, not the
# other way round. Importing the name anyway would need an F401 waiver no other
# verb module carries, and a suppressed warning is how an unused name outlives
# the reason it was kept.
import hs_run  # noqa: E402 — the shared verb-argv parser lives here
from hs_run import EXIT_BROKEN, EXIT_DONE, EXIT_STEP_REMAINING  # noqa: E402

# 30 polls * 60s = a 30-minute ceiling. This is where that number is DEFINED,
# and it is defined nowhere else: the ceiling and the interval are computed from
# these two constants everywhere they are printed, so there is no second copy to
# disagree with.
#
# The comment here used to justify the pair by quoting the skill body — "bound by
# ... else a 30-minute ceiling" — a sentence that does not appear in it. Citing
# prose that is not there is the same defect as prose describing code that does
# not run: it reads as corroboration, and the reader who checks is the only one
# who finds out. A constant does not need an external witness; if the skill body
# and this file ever disagree about the number, this file is the one that runs.
_MAX_POLLS = 30
_POLL_INTERVAL_S = 60


# --------------------------------------------------------------- forge detection

def _git_remote_url(root: Path) -> str:
    """`git remote get-url origin`, empty string on any failure — mirrors the
    skill's own `git remote get-url origin 2>/dev/null || true`. A repo with
    no `origin` remote is a real, non-crashing state (falls through to
    `unknown_forge` below), not a reason to raise."""
    try:
        r = subprocess.run(
            ["git", *_GIT_SAFE, "remote", "get-url", "origin"],
            cwd=str(root), capture_output=True, text=True, timeout=10, env=_git_env())
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


@_attrs.define(frozen=True, kw_only=True)
class ForgeInfo:
    """What `detect_forge` learned about the remote, declared once.

    Three hand-written literals of one shape in a single function, on three
    branches -- and the `unknown` branch is the one no happy-path test walks. A
    field dropped there would surface as a `KeyError` inside a caller that had
    already decided the forge was fine."""

    forge = _attrs.field()
    cli = _attrs.field(default=None)
    remote_url = _attrs.field(default="")

    def as_dict(self) -> dict:
        """Callers index this result by key today; the shape stays a mapping so
        changing HOW it is built changes nothing about what is returned."""
        return _attrs.asdict(self)


def detect_forge(root: Path) -> dict:
    """{"forge": "github"|"gitlab"|"unknown", "cli": "gh"|"glab"|None,
    "remote_url": str}.

    Substring match, `gitlab` checked first — the same order and the same
    case-sensitive `*gitlab*`/`*github*` shell-glob rule
    references/forge-detection.md documents, so a remote this function calls
    "github" is the remote a human running the skill's own bash snippet
    would also call "github". Never falls back past `unknown`: mixing `gh`
    and `glab` in one run, or guessing between them, is exactly what the
    skill's prose forbids."""
    remote = _git_remote_url(root)
    if "gitlab" in remote:
        return ForgeInfo(forge="gitlab", cli="glab", remote_url=remote).as_dict()
    if "github" in remote:
        return ForgeInfo(forge="github", cli="gh", remote_url=remote).as_dict()
    return ForgeInfo(forge="unknown", cli=None, remote_url=remote).as_dict()


# ----------------------------------------------------------- CLI availability

def _cli_auth_status(cli: str, root: Path):
    """(ok, message) from `<cli> auth status` — a real subcommand both `gh`
    and `glab` ship. Caller confirms `shutil.which(cli)` first; this assumes
    the binary exists (a missing binary is `cli_unavailable`, a separate,
    earlier state — see `cmd_next`)."""
    try:
        r = subprocess.run(
            [cli, "auth", "status"], cwd=str(root),
            capture_output=True, text=True, timeout=20)
        return r.returncode == 0, (r.stderr or r.stdout or "").strip()
    except Exception as e:  # noqa: BLE001 — reported honestly, never crashes the verb
        return False, str(e)


# -------------------------------------------------------------- check fetchers

_GH_NO_PR_MARKERS = ("no pull requests found",)


def _normalize_gh_check(item: dict) -> dict:
    """One `statusCheckRollup` entry is one of two GraphQL shapes GitHub
    mixes in the same array — a legacy commit-status `StatusContext` (`state`
    directly) or a `CheckRun` (`status`/`conclusion` split: `status` is the
    run's lifecycle, `conclusion` only fills in once `status == "COMPLETED"`).
    Collapsed here to one flat `{"name", "state"}` shape so the rest of this
    module never has to know which of the two it got."""
    name = item.get("name") or item.get("context") or "?"
    if "status" in item or "conclusion" in item:
        status = (item.get("status") or "").upper()
        if status and status != "COMPLETED":
            return {"name": name, "state": status}
        return {"name": name, "state": (item.get("conclusion") or "PENDING").upper()}
    return {"name": name, "state": (item.get("state") or "PENDING").upper()}


def _gh_checks(root: Path, pr_ref=None):
    """(checks, error). Uses `gh pr view --json statusCheckRollup` — NOT `gh
    pr checks --json ...` (see module docstring: that flag does not exist on
    the installed CLI). `checks == []` with `error is None` is its own real
    state (no open PR for this branch, or a PR with zero configured checks) —
    never folded into "still pending".

    `pr_ref` is the number/URL/branch the caller named. Omitted, the ref is
    left OFF the command line entirely rather than defaulted to something —
    `gh pr view` with no argument resolves to the current branch's PR, which is
    the behaviour every caller working on their own branch already relies on."""
    argv = ["gh", "pr", "view"]
    if pr_ref:
        argv.append(pr_ref)
    argv += ["--json", "statusCheckRollup"]
    try:
        r = subprocess.run(
            argv,
            cwd=str(root), capture_output=True, text=True, timeout=30)
    except Exception as e:  # noqa: BLE001
        return None, str(e)
    if r.returncode != 0:
        msg = (r.stderr or r.stdout or "").strip()
        if any(m in msg.lower() for m in _GH_NO_PR_MARKERS):
            return [], None
        return None, msg or "gh pr view failed (exit %d)" % r.returncode
    try:
        data = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return None, "gh pr view returned non-JSON output"
    return [_normalize_gh_check(c) for c in data.get("statusCheckRollup") or []], None


_GLAB_NO_PIPELINE_MARKERS = ("no pipelines", "not found", "404")


# A GitLab pipeline status is not a GitHub check conclusion, even where the two
# spell it the same. `_glab_checks` collapses the ENTIRE pipeline into one
# synthetic entry, so a word that describes one job on GitHub here describes
# every job at once — and the two that matter both land on the wrong side of the
# shared vocabulary:
#
#   skipped  GitHub: this job was conditional, its siblings still ran and carry
#            the evidence -> OK is right.
#            GitLab: NOTHING ran, and there are no siblings. Measured before this
#            map: `state=ci_done, ci_ok=true, "all checks terminal and green"`.
#   manual   a pipeline parked until a human presses play. Unmapped it is absent
#            from _TERMINAL_STATES, so it reads as pending-and-will-resolve and a
#            poll loop waits out its whole ceiling on a pipeline that will never
#            start on its own.
#
# Mapped at the FETCHER rather than by editing `_OK_STATES`, because the shared
# sets are correct for GitHub and a blanket refusal would turn every PR with one
# conditional job into a false blocker. The counter-control test pins that.
_PIPELINE_STATE = {
    "SKIPPED": "PIPELINE_SKIPPED",
    "MANUAL": "PIPELINE_MANUAL",
}


def _glab_checks(root: Path, pr_ref=None):
    """(checks, error) via `glab ci get -o json` — the current branch's
    pipeline; GitLab has no per-MR check list the way `gh pr view` has, this
    is the pipeline-status parity command references/forge-detection.md
    names. One pipeline maps to one synthetic check entry (`name: "pipeline"`)
    rather than a per-job array — `--with-job-details` exists but needs
    maintainer role, which this read-only verb should not assume it has.

    `pr_ref` rides `-b`, NOT a positional. Measured on glab 1.36.0: `glab ci get
    -o json 123` is refused outright ("accepts 0 arg(s), received 1"), and `-b`
    is the only selector the subcommand has. So a GitLab caller names the MR's
    BRANCH here where a GitHub caller may name a PR number — an asymmetry that
    belongs to the two CLIs, not to this verb, and one this cannot paper over
    without an MR-to-branch lookup it has no reason to make."""
    argv = ["glab", "ci", "get", "-o", "json"]
    if pr_ref:
        argv += ["-b", pr_ref]
    try:
        r = subprocess.run(
            argv,
            cwd=str(root), capture_output=True, text=True, timeout=30)
    except Exception as e:  # noqa: BLE001
        return None, str(e)
    if r.returncode != 0:
        msg = (r.stderr or r.stdout or "").strip()
        if any(m in msg.lower() for m in _GLAB_NO_PIPELINE_MARKERS):
            return [], None
        return None, msg or "glab ci get failed (exit %d)" % r.returncode
    try:
        data = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return None, "glab ci get returned non-JSON output"
    status = data.get("status")
    if not status:
        return [], None
    return [{"name": "pipeline",
             "state": _PIPELINE_STATE.get(str(status).upper(),
                                          str(status).upper())}], None


_FETCH = {"gh": _gh_checks, "glab": _glab_checks}

# A check is TERMINAL once it will not change on its own without external
# action — a mechanical fact this module can compute. Which VERDICT the PR
# should get from a terminal failure (Approve/Request-changes, which
# findings matter) stays the model's job (review-pr/SKILL.md's own verdict
# rules), never decided here. What IS decided here, mechanically, is the
# narrower question this verb owns: did every check reach a terminal state
# it can call "no further action needed from CI itself" — i.e. `ci_ok`.
#
# Per-conclusion judgment call (recorded, not left implicit):
#   * NEUTRAL, SKIPPED, SUCCESS(ES) -> OK. NEUTRAL/SKIPPED are a forge-level
#     "this check did not evaluate the code and reports no defect" signal
#     (e.g. a path-filtered or conditionally-inapplicable job) — treating
#     them as blocking would punish a check for correctly declining to run.
#   * CANCELLED/CANCELED, ERROR, FAILURE, TIMED_OUT, ACTION_REQUIRED, STALE,
#     FAILED -> NOT ok. These are all "did not produce a passing verdict",
#     including CANCELLED: a cancelled run is INCONCLUSIVE, not evidence the
#     code is good, so it must not silently fall into the OK bucket either.
#   * Anything NOT in `_OK_STATES` is not-ok by construction (a closed
#     allow-list, never an open deny-list) — an unlisted forge conclusion
#     value can never silently pass through as OK.
_TERMINAL_STATES = frozenset({
    "SUCCESS", "FAILURE", "ERROR", "NEUTRAL", "CANCELLED", "CANCELED",
    "TIMED_OUT", "ACTION_REQUIRED", "SKIPPED", "STALE",
    "FAILED", "SUCCEEDED",  # GitLab pipeline vocabulary
    # Whole-pipeline states, renamed at the fetcher (see `_PIPELINE_STATE`).
    # TERMINAL because neither resolves on its own — one already finished
    # without running, the other waits on a human — and absent from `_OK_STATES`
    # because neither is evidence the code was tested. Terminal-but-not-ok is
    # exactly the bucket a poll loop must stop on and a reviewer must not read
    # as green.
    "PIPELINE_SKIPPED", "PIPELINE_MANUAL",
})
_OK_STATES = frozenset({"SUCCESS", "NEUTRAL", "SKIPPED", "SUCCEEDED"})


def _all_terminal(checks) -> bool:
    return all(c.get("state") in _TERMINAL_STATES for c in checks)


def _all_ok(checks) -> bool:
    return all(c.get("state") in _OK_STATES for c in checks)


# --------------------------------------------------------------------- argv

def _parse_next_argv(argv):
    """(poll_n, pr_ref, error) for this verb's whole flag set, in ONE parse.

    One parse, not one per flag. The per-flag version declared `options=` with a
    single name, so the OTHER declared flag was undeclared on that pass and
    argparse refused it — a verb cannot learn a second flag by being asked about
    the first one twice.

    Tokenizing is `hs_run.parse_verb_argv`'s job; what stays here is genuinely
    this verb's — the int conversion, the two `--poll-n` refusals (wording
    unchanged, an operator reads it), and validating a ref that is about to be
    spliced into another program's command line."""
    ns = hs_run.parse_verb_argv("hs-run review-pr next", argv,
                                options=("poll-n", "pr"))

    raw = getattr(ns, "poll_n", None)
    if raw is None:
        return None, None, (
            "--poll-n is required — pass the round count named in the previous "
            "call's next_action (never 0/omitted, or the %d-minute ceiling can "
            "never be reached)" % (_MAX_POLLS * _POLL_INTERVAL_S // 60))
    try:
        poll_n = int(raw)
    except ValueError:
        return None, None, "--poll-n must be an integer, got %r" % (raw,)

    pr_ref, err = _validated_pr_ref(getattr(ns, "pr", None))
    if err:
        return None, None, err
    return poll_n, pr_ref, None


def _validated_pr_ref(raw):
    """(ref, error) for `--pr`. `None` in, `None` out — absent is the DEFAULT
    (answer for the current branch), never an error.

    This value crosses into another program's argv, so it is validated at that
    boundary rather than trusted:

      * empty/whitespace — the shape `--pr "$PR"` takes when the variable did
        not expand. Passed through it would silently become "no ref" and answer
        about the current branch: the exact wrong-PR failure this flag exists to
        remove, arriving through the fix for it.
      * leading `-` — `gh`/`glab` would read it as one of their OWN flags
        (`--repo=other/x` retargets the whole query), so a ref is required to
        look like a ref. Refused rather than escaped: `--` insertion would make
        the value legal input to a command line the caller never inspected, and
        no legitimate PR number, URL or branch name starts with a dash."""
    if raw is None:
        return None, None
    ref = str(raw).strip()
    if not ref:
        return None, (
            "--pr was given an empty value — pass the PR/MR number, URL or "
            "branch, or omit the flag to ask about the current branch")
    if ref.startswith("-"):
        return None, (
            "--pr %r starts with a dash, which the forge CLI would read as one "
            "of its own flags — pass the PR/MR number, URL or branch" % ref)
    return ref, None


# ------------------------------------------------------------------- verb

def cmd_next(argv: list, root: Path) -> dict:
    """`hs-run review-pr next --poll-n N [--pr REF]` — gather CI state for a
    PR/MR; never mutates the forge, never picks a verdict.

    `--pr` names WHICH one. Omitted, the answer is about the PR/MR belonging to
    the current branch — the long-standing behaviour, kept as the default so
    nothing that works today needs the flag. It matters because the two are
    indistinguishable downstream: reviewing someone else's PR without checking
    their branch out produced a confident, correctly-shaped envelope describing
    a different PR's CI, and no field in it said so.

    Wrapped so every one of the ten return paths carries `next_command`
    explicitly — see `_cmd_next_impl` for the states
    themselves and `_next_command_for` for which of them names a
    verbatim-runnable command."""
    result = _cmd_next_impl(argv, root)
    return hs_run_next_command.finalize(result, _next_command_for(result))


def _next_command_for(result: dict):
    """The verbatim-runnable command for a `review-pr next` result, or None.

    Only `ci_pending` (the sole exit-11 state this verb reaches) has one: the
    poll loop's own next invocation. Its `next_action` appends a wait hint
    (`# wait ~60s first`, formatted from `_POLL_INTERVAL_S` rather than typed, so
    the sentence cannot drift from the number the loop actually uses) — useful to
    a human, harmless to a shell, but `next_command`
    may also be split with `shlex` and exec'd WITHOUT a shell, where a trailing
    comment becomes two bogus argv tokens. So the machine field is rebuilt from
    the same numbers rather than sliced out of the sentence: deriving it by
    string-splitting the prose would silently break the moment the wording
    changed, which is the coupling the two-field split exists to remove.

    Every other state is exit 0/2/10 — a terminal result, a hard blocker, or a
    human decision (authenticate, install a CLI, pick a forge). None is a
    command this CLI may promise a driver can just run: at 10 the dispatcher
    rejects a non-null value outright, and at 0/2 there is no next step to name.

    The `ci_pending` branch now names its own `next_command` at construction —
    the value object requires it there, since rung 11 is a promise the object
    will not let you leave unkept. So this reads the value back rather than
    formatting a second copy of the same string: two places building one command
    from the same number is one edit away from disagreeing, and the disagreement
    would surface as a driver running a command nobody meant.
    """
    if result.get("state") != "ci_pending":
        return None
    stated = result.get("next_command")
    if stated:
        return stated
    return "hs-run review-pr next --poll-n %d" % result["next_poll_n"]


def _pr_suffix(pr_ref) -> str:
    """The ` --pr <ref>` tail for a command this verb tells a caller to re-run,
    or "" when no ref was named.

    Built in ONE place because it goes on THREE strings (`ci_pending`'s
    `next_action` and `next_command`, `ci_failed`'s retry line) and a copy that
    forgot it would send the next round back to the current branch — a loop that
    starts on the named PR and quietly finishes on another one."""
    #
    # `shlex.quote`, because this string lands in `next_command`, and rung 11
    # promises a driver can run that field VERBATIM — which means it will be
    # split back into argv. A branch name may hold a space (`feat/JIRA-1 retry`
    # is a shape humans type and git accepts), and interpolated raw it becomes
    # two tokens: the re-run then dies at argument resolution reporting
    # `unrecognized arguments` for a PR that is perfectly fine. The sibling
    # `hs_run_security.py` quotes the path it interpolates for the same reason;
    # both modules were written in the same batch and only one of them did.
    return " --pr %s" % shlex.quote(pr_ref) if pr_ref else ""


def _extra(pr_ref, **fields) -> dict:
    """A state's `extra` block, carrying `pr` whenever one was named.

    Present only when the caller named a ref, and absent otherwise, because the
    two are different claims and a `null` would blur them: absent says "this
    answer is about whatever PR the current branch owns", which is the truth on
    the default path. What must never happen is an envelope about PR 123 that
    does not say 123 — a driver polling a PR it did not check out has no other
    record of which one it asked about."""
    if pr_ref:
        fields["pr"] = pr_ref
    return fields


def _cmd_next_impl(argv: list, root: Path) -> dict:
    poll_n, pr_ref, err = _parse_next_argv(argv)
    if err:
        return hs_run.StepResult(
            state="error",
            next_action=err,
            artifacts=[],
            warnings=[err],
            exit_code=EXIT_BROKEN,
        ).as_dict()

    if poll_n >= _MAX_POLLS:
        return hs_run.StepResult(
            state="ci_timeout",
            next_action="%d-minute ceiling reached (%d/%d polls) — escalate "
                            "to the user, do not keep polling"
                            % (_MAX_POLLS * _POLL_INTERVAL_S // 60, poll_n, _MAX_POLLS),
            artifacts=[],
            warnings=[],
            exit_code=EXIT_BROKEN,
        ).as_dict()

    forge = detect_forge(root)
    if forge["forge"] == "unknown":
        return hs_run.StepResult(
            state="unknown_forge",
            next_action="remote %r does not name github or gitlab — inspect `git "
                "remote -v` and ask the user which forge/CLI to use; do not "
                "guess (review-pr/SKILL.md's documented unknown-forge rule)"
                % forge["remote_url"],
            artifacts=[],
            warnings=[],
            exit_code=EXIT_BROKEN,
            extra=_extra(pr_ref, forge=forge["forge"], remote_url=forge["remote_url"]),
        ).as_dict()

    cli = forge["cli"]
    if shutil.which(cli) is None:
        return hs_run.StepResult(
            state="cli_unavailable",
            next_action="install the %s CLI (%s) before this verb can run"
                            % (forge["forge"], cli),
            artifacts=[],
            warnings=[],
            exit_code=EXIT_BROKEN,
            extra=_extra(pr_ref, forge=forge["forge"], cli=cli),
        ).as_dict()

    auth_ok, auth_msg = _cli_auth_status(cli, root)
    if not auth_ok:
        return hs_run.StepResult(
            state="cli_unauthenticated",
            next_action="authenticate first: `%s auth login` (%s)"
                            % (cli, auth_msg or "not logged in"),
            artifacts=[],
            warnings=[auth_msg] if auth_msg else [],
            exit_code=EXIT_BROKEN,
            extra=_extra(pr_ref, forge=forge["forge"], cli=cli),
        ).as_dict()

    checks, fetch_err = _FETCH[cli](root, pr_ref)
    if fetch_err is not None:
        return hs_run.StepResult(
            state="ci_check_failed",
            next_action="fix the underlying failure, then retry: %s" % fetch_err,
            artifacts=[],
            warnings=[fetch_err],
            exit_code=EXIT_BROKEN,
            extra=_extra(pr_ref, forge=forge["forge"], cli=cli),
        ).as_dict()

    if not checks:
        # Exit 0 is this verb's "nothing left for me to report", NOT "CI passed".
        # The distinction is the whole content of this sentence, so it leads with
        # the finding and states the non-greenness as a fact rather than leaving
        # it to be inferred from an exit code that also means success elsewhere.
        # Rung 11 is structurally unavailable here — it promises a
        # verbatim-runnable next command and there is none — and rung 2 would
        # erase a real distinction: a project that simply runs no CI is not a
        # broken one, which is why an empty check list with no error is its own
        # state rather than a fetch failure.
        return hs_run.StepResult(
            state="no_checks_found",
            next_action="the %s reports NO checks for %s — this is an empty "
                            "result, not a passing one, and nothing here says "
                            "the code is good. Nothing is left to watch: decide "
                            "whether the PR/MR exists and whether this project "
                            "runs CI at all."
                            % (forge["forge"],
                               "PR/MR %s" % pr_ref if pr_ref else "the current branch"),
            artifacts=[],
            warnings=[],
            exit_code=EXIT_DONE,
            extra=_extra(pr_ref, forge=forge["forge"], cli=cli),
        ).as_dict()

    if _all_terminal(checks):
        if _all_ok(checks):
            return hs_run.StepResult(
                state="ci_done",
                next_action="all checks terminal and green — proceed",
                artifacts=checks,
                warnings=[],
                exit_code=EXIT_DONE,
                extra=_extra(pr_ref, forge=forge["forge"], cli=cli, ci_ok=True),
            ).as_dict()
        # Split from ci_done on purpose (see module docstring / the merge-
        # blocking defect this closes): all-terminal-but-not-all-green must
        # NEVER ride EXIT_DONE — a caller reading only the exit code (the
        # closed ladder's whole point) would see 0 and proceed. The failing
        # check names go in `warnings`, the field a driver/TUI actually
        # renders, not only the side-channel `ci_ok` flag nothing is
        # obliged to read.
        failing = [c.get("name", "?") for c in checks if c.get("state") not in _OK_STATES]
        return hs_run.StepResult(
            state="ci_failed",
            next_action="CI failed (%s) — fix the underlying failure, then re-run: "
                            "hs-run review-pr next --poll-n 0%s"
                            % (", ".join(failing), _pr_suffix(pr_ref)),
            artifacts=checks,
            warnings=failing,
            exit_code=EXIT_BROKEN,
            extra=_extra(pr_ref, forge=forge["forge"], cli=cli, ci_ok=False),
        ).as_dict()

    return hs_run.StepResult(
        state="ci_pending",
        next_action="hs-run review-pr next --poll-n %d%s  # wait ~%ds first"
                    % (poll_n + 1, _pr_suffix(pr_ref), _POLL_INTERVAL_S),
        # Named HERE, not left to the `finalize` pass. Rung 11 promises a
        # verbatim-runnable step, and the value object enforces that pairing at
        # construction — which is the point: the dict form let this result exist
        # for a whole call stack with the promise unkept, and the only reason
        # that was survivable is that a wrapper happened to fill it in later.
        # `finalize` uses setdefault, so it stays a no-op over this value.
        #
        # The comment hint stays on `next_action` and off this field: the
        # machine string may be shlex-split and exec'd without a shell, where a
        # trailing `# ...` becomes two bogus argv tokens.
        next_command="hs-run review-pr next --poll-n %d%s"
                     % (poll_n + 1, _pr_suffix(pr_ref)),
        artifacts=checks,
        warnings=[],
        exit_code=EXIT_STEP_REMAINING,
        # `next_poll_n` is the round number the NEXT call must pass. Surfaced as
        # its own field so a reader gets a number instead of parsing it back out
        # of the human sentence — and so a driver can see the poll count it is
        # being asked to advance without string-handling either field.
        extra=_extra(pr_ref, forge=forge["forge"], cli=cli, next_poll_n=poll_n + 1),
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
        % (Path(__file__).name, 'review-pr'))
    raise SystemExit(EXIT_BROKEN)
