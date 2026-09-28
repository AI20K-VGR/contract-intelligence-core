#!/usr/bin/env python3
"""hs_run_fix.py — the `fix` domain's verb entry point for hs-run.

`hs:fix` walks six steps. A survey of what each one leaves behind measured that
only TWO are readable by a program, and this module takes those two and says so
about the rest rather than manufacturing evidence:

  1 Scout      — no required artifact. Reports land in the SHARED `plans/reports/`
                 under a slug the model picks, beside reports from other sessions.
                 "N report files exist" reads the same whether this bug was scouted
                 or a different one was, last week.
  2 Diagnose   — same, plus the SKILL prose and the only code that scaffolds a
                 report disagree about the filename shape, so neither is
                 computable in advance.
  3 Fix        — a dirty tree is a real git fact, but `git status` carries no
                 actor. A concurrent session's edit produces the identical
                 reading, and this repo is multi-actor by construction.
  4 red→green  — a suite RESULT is not a disk fact. The sibling `test` domain
                 states this boundary about itself (`hs_run_test.py:25-27`) and
                 refuses to manufacture a `run` verb for it; this domain inherits
                 that rather than re-litigating it.
  5 Review     — READABLE: `artifact_check._load_artifact(plan_dir,
                 "review-decision")`, the call `hs_run_cook` already makes.
  6 Gate       — READABLE: `artifact_check.check_stage("push", root)`, the call
                 `hs_run_ship` already wraps.

Both readable steps need a plan, which is where `fix` differs from every sibling:
a bug fix may legitimately run with none. That is not a degenerate case to paper
over — the push gate genuinely cannot clear without one (`write_verification.py`
takes `plan_dir` as a mandatory positional, and the verification schema lists
`plan` under `required` typed `string`). So the fork is the FIRST thing this verb
answers, and it answers it out loud: a tree with no plan is told it has no plan,
never told a gate it could not read has passed.

Zero new detection logic, the invariant this CLI family holds: every predicate
below is answered by the library that already owns it, at the same call site its
sibling domain uses. A second implementation of a judgment is a second thing to
drift, and the drift shows up as a weaker claim rather than an error.
"""
from __future__ import annotations

import sys
from pathlib import Path

import attrs as _attrs  # noqa: E402  (REQUIRED — see harness/requirements.txt)

import artifact_check
import hs_run_next_command

import hs_run  # noqa: E402
from hs_run import EXIT_BROKEN, EXIT_NEEDS_MODEL  # noqa: E402


@_attrs.define(frozen=True, kw_only=True)
class PlanRef:
    """Which plan an answer is about, and what is wrong with it.

    `verdict` and `reason` are empty rather than absent when there is nothing to
    say, so a reader never has to tell "nothing wrong" apart from "this emit site
    forgot the key" — the same guarantee `StateRouting` makes for its own rows.
    """

    plan = _attrs.field()
    verdict = _attrs.field(default="")
    reason = _attrs.field(default="")

    def as_dict(self) -> dict:
        return {"plan": str(self.plan), "verdict": str(self.verdict),
                "reason": str(self.reason)}


def _review_verdict(plan_dir: Path) -> str:
    """The recorded review verdict, or "" when none is on disk.

    Wraps `artifact_check._load_artifact`, the same call `hs_run_cook._cmd_close_impl`
    makes for the same question. A malformed record answers "" rather than raising:
    from this verb's side "there is no usable verdict" and "there is no file" lead
    to the identical next move, and the artifact's own validator owns the finer
    distinction.
    """
    try:
        rec, _path = artifact_check._load_artifact(plan_dir, "review-decision")
    except Exception:  # noqa: BLE001 — an unreadable artifact is "no verdict"
        return ""
    if not isinstance(rec, dict):
        return ""
    return str(rec.get("verdict") or "")


def _previous_state() -> str:
    """Where this session's last `fix` run got to, or "" when there is nothing.

    A fix spans several turns — build, review, gate — and the turn that resumes
    otherwise has one way to learn where the last one stopped: re-run every
    projection and re-read the tree, paying the whole context cost again for an
    answer the CLI computed and discarded one turn earlier. This is the read side
    of the breadcrumb the ledger already writes at `_write()`.

    Never a DECISION input. The branches below all re-derive from disk, and this
    rides `extra` as context for the reader — a stale or missing breadcrumb must
    change nothing about what the verb answers, only about how much the reader
    has to reconstruct. An anonymous session gets "" (see `latest_state`: two
    unnamed runs are not one session), which is exactly the case where a
    breadcrumb would be someone else's.
    """
    try:
        return hs_run.latest_state(session=hs_run._resolve_session(),
                                   domain="fix") or ""
    except Exception:  # noqa: BLE001 — an unreadable ledger is "no breadcrumb"
        return ""


def cmd_next(argv: list, root: Path) -> dict:
    """Where a fix stands, read off disk — never guessed from the narration.

    The order is the projection rather than a preference: a tree with no plan
    cannot reach either later gate, and the review gate sits before the push gate
    in `cook`'s own close sequence. Answering the push gate first would send the
    caller at the later of two blockers.
    """
    out = _cmd_next_impl(argv, root)
    # Stamped at the ONE seam every branch leaves through, rather than at four
    # emit sites that would drift. Only when there is something to say: an absent
    # key reads as "no previous run", which is the honest shape when the ledger
    # has nothing for this session.
    #
    # Written at the TOP level, not under an `extra` key. `_cmd_next_impl` returns
    # what `StepResult.as_dict()` already produced, and that method FLATTENS
    # `extra` into the envelope — measured, `extra={"previous_state": ...}` comes
    # back as a top-level `previous_state` with no `extra` key anywhere. Re-adding
    # `out["extra"]` here therefore did not join that mechanism, it invented a
    # second one: every other extra in the CLI reads as `blob["x"]` while this one
    # alone read as `blob["extra"]["x"]`, and a consumer written against either
    # shape misses the other.
    prev = _previous_state()
    if prev:
        out["previous_state"] = prev
    return hs_run_next_command.finalize(out)


def _cmd_next_impl(argv: list, root: Path) -> dict:
    # Raises VerbArgError on a mistyped flag; the dispatcher maps that to a valid
    # EXIT_BROKEN envelope, so catching it here would turn a named error into a
    # silent fall-through to the no-plan branch.
    hs_run.parse_verb_argv("hs-run fix next", argv)

    # One stage per run, resolved once and used by every read below, so the plan
    # this verb anchors to is the plan the gate will judge.
    import push_gate
    stage = push_gate.stage_for_checkout(root)
    policy = artifact_check.load_policy()["stages"].get(stage) or {}
    plan_dir = artifact_check.resolve_active_plan(
        str(root),
        allow_completed=bool(policy.get("allow_completed_plan", False)))

    if plan_dir is None:
        # Rung 2, not 10. This is not "a model decides what to do next" — the
        # push gate's own precondition is absent, and no amount of reading will
        # produce one. The three exits are named because they are genuinely all
        # of them: the stage policy's `require_plan` defaults True and push does
        # not override it.
        return hs_run.StepResult(
            state="no_plan_resolved", exit_code=EXIT_BROKEN,
            next_action=(
                "no plan resolved under %s/plans, so the %s-stage gate cannot "
                "clear and there is nowhere to record a verification. Open a "
                "minimal plan (status: in_progress), or point HARNESS_ACTIVE_PLAN "
                "at one. A fix without a plan can still be built and committed — "
                "it just cannot pass the stage gate, and this verb will not "
                "pretend otherwise." % (root, stage)),
        ).as_dict()

    verdict = _review_verdict(Path(plan_dir))
    if verdict not in ("PASS", "PASS_WITH_RISK"):
        # Rung 10: what remains is a review, and deciding a diff is sound is the
        # definition of a model turn. The command is still named in next_action —
        # only rung 11 promises a driver may dispatch it.
        return hs_run.StepResult(
            # `needs_review`, not `review_missing`. The name split this session
            # runs one way: the MUTATING verb takes the new word, the projection
            # keeps the old one. `cook close` refusing to write is
            # `review_missing` at rung 2; this verb only READS the same tree and
            # reports work still owed, which is `needs_review` at rung 10 —
            # exactly what `cook next` reports for the identical predicate.
            state="needs_review", exit_code=EXIT_NEEDS_MODEL,
            next_action=(
                "%s has no PASS review-decision recorded%s. Spawn the reviewer, "
                "then record the verdict — reviewing your own fix at this gate is "
                "the thing the gate exists to prevent."
                % (Path(plan_dir).name,
                   "" if not verdict else " (found %r)" % verdict)),
            artifacts=[PlanRef(plan=Path(plan_dir).name,
                               verdict=verdict).as_dict()],
        ).as_dict()

    blocked = artifact_check.check_stage(stage, str(root))
    if blocked:
        return hs_run.StepResult(
            state="gate_blocked", exit_code=EXIT_NEEDS_MODEL,
            next_action="the review passed but the %s-stage gate refuses: %s"
                        % (stage, blocked),
            artifacts=[PlanRef(plan=Path(plan_dir).name, verdict=verdict,
                               reason=blocked).as_dict()],
        ).as_dict()

    # Rung 10, not 0. Everything this verb can PROVE from disk is satisfied, and
    # what remains — is the root cause genuinely fixed, or was a symptom patched —
    # is not disk-provable. Saying "done" here would put the verb's own health
    # behind a claim about the work.
    return hs_run.StepResult(
        state="ready", exit_code=EXIT_NEEDS_MODEL,
        next_action=(
            "review PASSED and the %s-stage gate clears for %s. Everything "
            "readable from disk is satisfied; whether the ROOT CAUSE is fixed "
            "rather than a symptom is not, so confirm that before shipping."
            % (stage, Path(plan_dir).name)),
        artifacts=[PlanRef(plan=Path(plan_dir).name,
                           verdict=verdict).as_dict()],
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
        % (Path(__file__).name, 'fix'))
    raise SystemExit(EXIT_BROKEN)
