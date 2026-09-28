"""hs_run_ship.py — the `ship` domain for hs-run.

`ship` is the highest-risk domain this CLI will ever host: a bug here can
push code or open a PR nobody reviewed. `next` is deliberately the
narrowest possible slice of that domain — it REPORTS what the push-stage gate
would say, and does nothing else. It never approves, pushes, or opens a PR.

The gate DECISION comes from exactly one PUBLIC function, called with
`plan_dir` left `None` so `check_stage` owns its own resolution end to end:

  - artifact_check.check_stage(stage, root, plan_dir=None) -> None|str
    (None = pass; a string = the block reason, verbatim, never invented here)

`check_stage` reads the stage's own `allow_completed_plan` policy flag off
`plan_dir=None` and resolves accordingly — passing a pre-resolved `plan_dir`
in would SKIP that branch (see `check_stage`'s own `if plan_dir is not None`
short-circuit) and silently defeat the policy this domain exists to mirror.
This module therefore never pre-resolves the plan for the decision. It makes
one SEPARATE, report-only call to `resolve_active_plan(..., allow_completed=
True)` — mirroring (never feeding) the same policy — purely to populate the
`artifacts` list for the operator; that call cannot change pass/block, only
which plan dir (if any) shows up as evidence.

Deliberately `check_stage()`, not the private `_artifact_path`/`_load_artifact`
some call sites reach for directly: a verb built on the public entry point
cannot break when a private helper's name changes.

WHY THE ANSWER IS SIX WORDS AND NOT ONE
This verb used to answer every refusal with `blocked`. Measured across a
temp-tree census: 31 distinct reasons reached that one word, spanning missing
plans, unreadable receipts, cross-plan replays and self-contradictory policy.
A reader learned that something was wrong and nothing about what to do — one
warning light for an empty tank, a flat tyre and a seized engine.

The states below split that word by WHAT THE READER DOES NEXT, never by reason.
That is why 31 reasons become 6 states rather than 31: `receipt_invalid`
absorbs twelve of them because all twelve are resolved by opening the same one
file, and a state nobody would act on differently is a distinction with no
consumer.

DECISION AND LABEL ARE SEPARATE JOBS, ON PURPOSE
`check_stage` alone decides whether this refuses, and its reason string is
handed back verbatim as `next_action`. The classifier below only chooses which
NAME to put on that refusal, by re-reading the same disk conditions in the same
order `check_stage` itself walks. It cannot make the verb refuse something the
gate allowed, or allow something the gate refused — the worst a classifier bug
can do is misname a refusal whose reason text is right there in the envelope.
"""
from __future__ import annotations

from pathlib import Path

import artifact_check
import hs_run_next_command

# The four-tier ladder (D10), IMPORTED rather than re-declared.
# Ten modules used to hand-copy these four constants and had already drifted:
# rung 11 carried two different names across the tree and two modules declared
# the same constant twice. `hs_run` owns the ladder as a closed `Exit` IntEnum;
# both historical spellings of rung 11 are bound to the same member there, so
# this import changes no name any caller in this file uses.
import hs_run  # noqa: E402 — the shared verb-argv parser lives here
from hs_run import EXIT_BROKEN, EXIT_DONE, EXIT_NEEDS_MODEL, EXIT_STEP_REMAINING  # noqa: E402


def _architecture_review_owed(plan_dir, root) -> bool:
    """Is the gate refusing because a structural diff lacks its architecture pass?

    Asks `artifact_check`'s own branch rather than matching its sentence. The
    reason string is written for a human and gets reworded; a second module keyed
    on its prose drifts apart the day someone improves it — the same reasoning
    `hs_run_git` gives for re-deriving its no-plan fork from disk.

    Reachable only since this verb learned to judge `merge`: the branch needs a
    stage that requires `review-decision`, which `push` does not and `merge` does.
    Fail-safe on any error — an unreadable artifact is not evidence that an
    architecture pass is owed, and the caller's existing `policy_broken` answer is
    the honest one when this cannot tell.
    """
    if plan_dir is None:
        return False
    try:
        from pathlib import Path as _Path
        return artifact_check._architecture_review_consistency(
            _Path(str(plan_dir)), str(root)) is not None
    except Exception:  # noqa: BLE001
        return False


def _stage_for(root) -> str:
    """Which stage the pre-push gate will actually run: `merge` or `push`.

    Delegates to `push_gate.stage_for_checkout`, the projection-side sibling of
    the `stage_for` the pre-push hook itself calls — same `is_protected`
    predicate, one step earlier, so this verb and the gate cannot disagree about
    which stage a branch is in.

    Why it matters: the two stages require different things. Measured with
    `protected: [main, master]` filled in, `merge` requires verification,
    review-decision AND plan-approval where `push` requires verification alone —
    so a verb hard-coded to `push` reports `ready` on a protected branch whose
    real gate is about to refuse over two receipts it never looked at. The
    shipped default is `protected: []`, which makes this inert today; that file
    exists to be filled, and a verb that only becomes wrong once someone
    configures the repo is worse than one that is wrong now.
    """
    try:
        import push_gate
        return push_gate.stage_for_checkout(root)
    except Exception:  # noqa: BLE001 — an unreadable helper claims no protection
        return "push"


def _enforcing(stage: str) -> bool:
    """Whether the stage policy actually checks anything here.

    A `hard: false` stage, or a hard one with an empty `requires:`, returns
    `None` from `check_stage` on a tree with no receipts at all — the same
    `None` a fully-evidenced tree returns. Measured: with `push.hard: false`
    and zero artifacts on disk, this verb reported `ready`.

    Reading the policy is what separates those two `None`s. It is a question
    about CONFIGURATION, so it is answered from the policy file rather than by
    inspecting the tree — a tree that happens to be empty and a policy that
    happens to demand nothing are different facts and only one of them is about
    the operator's work.

    Never raises: `load_policy()` raises loudly on a missing or malformed
    policy, and that is `check_stage`'s call to make, not this helper's. By the
    time this runs `check_stage` has already loaded the same policy through the
    same cached path, so a raise here would be a second opinion about a file
    that already answered.
    """
    try:
        policy = artifact_check.load_policy()["stages"].get(stage)
    except Exception:  # noqa: BLE001 — the gate above already ruled on this file
        return True
    if not isinstance(policy, dict) or not policy.get("hard"):
        return False
    return bool(policy.get("requires"))


def _receipt_fault(root: Path, plan_dir):
    """Which SHAPE of receipt fault this tree has: `"missing"`, `"invalid"`,
    or None when no required receipt is at fault.

    Deliberately NOT the state name. The state literals live at the emit site
    below, because the repo's shared result reader (`verb_result_shapes`) —
    which the routing gate, the conformance gate and the STATE.md renderer all
    ask — resolves a state only when it is a literal in the emitting function.
    Measured: with the names returned from here, all four refusal states were
    invisible to it, the generated map documented two of six, and the routing
    gate reported four live states as vocabulary no verb can return. A helper
    that answers a narrower question and lets the caller name the state keeps
    one vocabulary in one place and stays legible to every reader of it.

    Walked in `check_stage`'s OWN order, because the first thing that refuses
    is the thing the reader has to fix first. Re-derived from disk through the
    same helpers the gate uses rather than by matching its prose: a reason
    string is written for a human and gets reworded, and a classifier keyed on
    its wording would silently start misfiling refusals the day somebody
    improves a sentence.

    `plan_dir` is the already-resolved dir — passed in rather than re-resolved
    so the label describes the same plan the envelope reports as evidence.
    """
    stage = _stage_for(root)
    try:
        policy = artifact_check.load_policy()["stages"].get(stage) or {}
    except Exception:  # noqa: BLE001 — already ruled on by check_stage
        policy = {}

    for kind in policy.get("requires") or []:
        # An unrecognised kind is a typo in `requires:`. It reads like a receipt
        # problem — the message names an artifact — but no receipt can fix it,
        # so it is not a receipt fault and falls through to the policy state.
        if kind not in artifact_check._REQUIRED_FIELDS:
            return None
        rec, problem = artifact_check._load_artifact(Path(plan_dir), kind)
        if rec is None:
            # Absent, or resolving outside the plan's own artifacts dir. A gate
            # that refuses to read through an escape has, for the reader's
            # purposes, no receipt — and in both cases the next move is to
            # produce a real one at the real path.
            if problem == "missing" or "outside" in str(problem):
                return "missing"
            return "invalid"
        if artifact_check._check_artifact(Path(plan_dir), kind, root=str(root),
                                          stage=stage):
            # Present, parsed, and refused on its CONTENT — wrong plan, a
            # failing check, a verdict the stage does not accept. One file to
            # open, which is what makes these twelve reasons one state.
            return "invalid"

    return None


def cmd_gates_check(argv: list, root: Path) -> dict:
    """Report the push-stage gate's verdict, named by what to do about it.

    Tier-10 when the gate is clear: the gate having nothing left to say is NOT
    the same as the next step being safe to automate. The step that follows is
    `git push`, and ship/SKILL.md prohibits reaching it without a live human
    confirm — precisely because these gates are self-approvable, so an agent can
    write its own PASS artifacts and clear them. Tier-11 would contradict that in
    the one place it is machine-readable: the ladder defines 11 as a
    deterministic step a driver MAY run unattended, and a push cannot be
    withdrawn once anyone has fetched it. `next_command` stays null for the same
    reason: the rung is advice to whoever reads it, that field is the half a
    driver dispatches on, and leaving it populated would route around the rung.

    Tier-2 on every refusal, carrying the gate's own block reason verbatim —
    never re-worded, so the operator sees the SAME text `hs-cli gates`/CI would
    show. The state is what changed: four names instead of one word, chosen by
    where the reader goes next. There is no "no active plan, nothing to ship"
    Tier-0: the push stage has no `require_plan: false` override, so "no plan
    resolved" is itself one of `check_stage`'s block reasons, not a free pass —
    reporting it as EXIT_DONE would be the exact same shape of lie a pre-resolved
    plan_dir override used to tell for a completed plan.

    This verb takes no flags of its own — it always judges the resolved active
    plan. `argv` is still PARSED, against an empty declaration, so a mistyped
    flag is a named error rather than a token silently dropped: this verb's
    answer is read as permission to push, and "blocked for some other reason"
    is not a safe thing to hand back to someone who typed something the verb
    never understood."""
    hs_run.parse_verb_argv("hs-run ship next", argv)
    # The stage is MEASURED, not assumed: on a protected branch the pre-push
    # gate runs `merge`, which requires review-decision and plan-approval on top
    # of verification. Hard-coding `push` made this verb answer `ready` for a
    # tree whose real gate was about to refuse over two receipts it never read.
    stage = _stage_for(root)
    reason = artifact_check.check_stage(stage, str(root))
    # Report-only: which plan (if any) push's own allow_completed_plan policy
    # would anchor to. This NEVER feeds back into the decision above — it is
    # purely evidence for the operator reading `artifacts`, and the input the
    # classifier names its refusal against.
    #
    # The flag is READ from the same policy file `check_stage` reads
    # (artifact_check.py:1225), not hard-coded. It was hard-coded `True`, which
    # matches the shipped policy today and would silently stop matching the day
    # someone edits it — and the two disagreeing produces one envelope holding
    # both a resolved plan and a refusal saying no plan resolved. A constant
    # that happens to equal a config value is not the config value; it is a
    # copy that cannot be told apart from the original until it is wrong.
    _stage_policy = artifact_check.load_policy()["stages"].get(stage) or {}
    plan_dir = artifact_check.resolve_active_plan(
        str(root),
        allow_completed=bool(_stage_policy.get("allow_completed_plan", False)))
    artifacts = [str(plan_dir)] if plan_dir is not None else []

    if reason:
        if plan_dir is None:
            # Nothing to anchor to. The fix is in `plans/` or in the
            # environment, never in a receipt — a different place from every
            # other refusal here, which is why it is a different word.
            return hs_run_next_command.finalize(hs_run.StepResult(
                state="no_plan_resolved", exit_code=EXIT_BROKEN,
                next_action=reason, artifacts=artifacts,
            ).as_dict())
        fault = _receipt_fault(root, plan_dir)
        if fault == "missing":
            # Rung 10, not 11, and the distinction is the whole safety property
            # of this domain. 11 licenses a driver to run the step unattended,
            # and the ONLY command that clears this state writes the very
            # receipt that authorises the push — `write_verification.py` takes
            # the verdict on its command line, so an unattended driver would be
            # deciding PASS before any suite ran and then clearing the gate with
            # its own paper. `harness/rules/verification-mechanism.md` calls
            # that out directly: self-report does not self-approve. Remote CI
            # does not catch it either, since it reads the receipt out of the
            # tree that was already pushed.
            #
            # The sibling domain reached the same answer independently:
            # `hs_run_test.py` reports the analogous `no_verification` at rung
            # 10, because deciding whether a recorded failure is the deliberate
            # red half of a TDD cycle is not a fact on disk. Turning a suite run
            # into a verdict is a model turn, and a state whose remaining work
            # needs one is rung 10 by the ladder's own definition.
            #
            # The command is still NAMED, in `next_action` — the sentence a
            # person reads. Only `next_command`, the field a driver dispatches
            # on, stays null. Two fields, two readers.
            return hs_run_next_command.finalize(hs_run.StepResult(
                state="receipt_missing", exit_code=EXIT_NEEDS_MODEL,
                next_action=(
                    "%s\n\nRun the suite for real FIRST, then record what it "
                    "actually did: python3 harness/scripts/write_verification.py "
                    "%s --phase <node-id> --verdict <PASS|PASS_WITH_RISK|BLOCKED> "
                    "--check <name>:<PASS|FAIL|SKIP>. The verdict is an outcome "
                    "to report, never a value to pick — this receipt is what "
                    "clears the push gate." % (reason, plan_dir)),
                artifacts=artifacts,
            ).as_dict())
        if fault == "invalid":
            # One file, on disk, unusable. The gate's own reason names what is
            # wrong with it; every one of the twelve reasons that land here is
            # resolved by opening that file.
            return hs_run_next_command.finalize(hs_run.StepResult(
                state="receipt_invalid", exit_code=EXIT_BROKEN,
                next_action=reason, artifacts=artifacts,
            ).as_dict())
        # Nothing is wrong with a receipt, and the gate still refused. On `push`
        # that could only be the stage floor or the rule-scan consistency check —
        # both faults in a policy file, hence the state name.
        #
        # That reasoning WAS total when the stage was hard-coded to `push`, and it
        # said so with the condition attached: "if this verb is ever taught to
        # judge one of those, this tail stops being total". It was — `_stage_for`
        # now returns `merge` on a protected branch, and `merge` requires
        # `review-decision` (measured, stage-policy.yaml), which is exactly the
        # precondition `check_stage`'s architecture-review branch waits on. So on
        # a protected branch this tail CAN be reached by a reason that is not a
        # policy fault at all: a structural diff whose review-decision carries no
        # `architecture_review.checked`.
        #
        # Split rather than renamed: `policy_broken` on a genuine self-contradiction
        # is still the right word and still the common case, and folding a missing
        # architecture pass into it would tell the reader to go fix a config file
        # over a receipt they can actually write.
        #
        # Re-derived by CALLING the gate's own branch, never by matching its
        # sentence. The reason string is written for a human and gets reworded;
        # two modules keyed on its prose drift apart the day someone improves it.
        # Asking the function is the same seam `hs_run_git` uses for its own fork.
        if _architecture_review_owed(plan_dir, root):
            return hs_run_next_command.finalize(hs_run.StepResult(
                state="needs_architecture_review", exit_code=EXIT_NEEDS_MODEL,
                next_action=reason, artifacts=artifacts,
            ).as_dict())
        return hs_run_next_command.finalize(hs_run.StepResult(
            state="policy_broken", exit_code=EXIT_BROKEN,
            next_action=reason, artifacts=artifacts,
        ).as_dict())

    if not _enforcing(stage):
        # The gate passed by not looking. Said out loud, because the previous
        # answer here was the same `ready` an evidenced tree gets, and a reader
        # had no way to tell "nothing blocked you" from "you are covered".
        #
        # This changes the SENTENCE, not the policy: the local personal-first
        # stance — generate receipts here, enforce them in remote CI — is
        # deliberate and untouched. Still rung 10: a human decides what to do
        # about an unenforced gate, exactly as they would about a cleared one.
        return hs_run_next_command.finalize(hs_run.StepResult(
            state="gates_not_enforced", exit_code=EXIT_NEEDS_MODEL,
            next_action=(
                "the %r stage policy requires no receipt here, so NOTHING was "
                "checked — this is 'nobody is asking', not 'you are covered'. "
                "Local posture is generate-here/enforce-in-CI, so the remote "
                "receipts-gate still judges this branch. Confirm with the human "
                "(hs:ship Step 9) before pushing." % stage),
            artifacts=artifacts,
        ).as_dict())

    # No `next_command`: naming `git push` here would hand a driver the exact
    # instruction the human-confirm rule exists to intercept. `next_action`
    # still says what happens next — a sentence a person reads, not a field a
    # driver dispatches on (two fields, two readers).
    return hs_run_next_command.finalize(hs_run.StepResult(
        state="ready", exit_code=EXIT_NEEDS_MODEL,
        next_action="push-stage gates clear for %s — this verb reports only. "
                        "Confirm with the human first (hs:ship Step 9), then "
                        "push or open the PR." % (plan_dir or root),
        artifacts=artifacts,
    ).as_dict())


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
        % (Path(__file__).name, 'ship'))
    raise SystemExit(EXIT_BROKEN)
