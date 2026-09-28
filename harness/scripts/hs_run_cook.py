#!/usr/bin/env python3
"""hs_run_cook.py — the `cook` domain's verb entry points for hs-run.

This module replaces the earlier
honest-but-narrow floor (`next` only, "unresolved" for anything real) with the
full per-phase state machine cook actually needs. The asymmetry vs `plan`
(re-verified against the cook lifecycle) drives every shape
decision here — do NOT copy `plan`'s eventual verb shape wholesale:

  - E17: cook's grid promise is PER PHASE (`emit --phase` mandatory), never
    per-plan. `next`'s per-phase loop never gates an individual phase's
    "done" status on a phase micro-grid — the recon's own nuance beyond E17
    is that the phase-count promise is
    enforced ONLY by a separate, later gate (`--require-phase-grids`, cook
    Step 6e), never folded into per-phase completion. See `cmd_close` /
    `_finalize_projection` for where that gate actually lives — and see
    "E27's two artifact paths" below for why BOTH this module's `preflight`
    and its `close`/finalize projection must each run their own independent
    grid check, at two different times, against two different artifact
    shapes.
  - E15: cook's grid fill defaults to NO model (deterministic STUB) — this
    module never makes a grid-fill step a mandatory model turn anywhere.
  - E16: cook has no axis-selection step of its own; the axis-selection
    receipt is a MACRO-grid-only requirement (`grid_emit_guard.py`'s own
    `_is_macro_grid_path`, keyed on file path, not a field) — this module
    never invents one for the per-phase grid.

Wrap, never rewrite (survival invariant #4): every verb below calls into an
existing script's own Python API (`plan_graph`, `grid_emit_guard`,
`grid_flag_carry`, `derive_plan_completion`, `artifact_check`, `plan_status`,
`open_plan`, `close_plan`, `write_verification`, `frontmatter_parser`,
`defer_suite_carry`, `graph_test_scope`) — no judgment is re-implemented
here, only ordering + parameter-passing.

E27 — the trap this module exists to not fall into: cook reads TWO DIFFERENT
artifact paths at two different times.

  1. `preflight` (0.5a-0.5c): the ONE-TIME, plan-level check before phase 1 —
     `plan_graph.py --require`-equivalent (sidecar + `post:` obligations) plus
     `grid_emit_guard.py --require`-equivalent (the MACRO `coverage-grid.json`
     artifact, checked ONLY when grid mode is carried).
  2. `close` (6e-then-6g): the LAST-call check before finalizing — a
     COMPLETELY SEPARATE `grid_emit_guard.py --require-phase-grids`-equivalent
     that counts, for EVERY phase `plan-graph.yaml` declares, whether its own
     PER-PHASE `coverage-grid-<phase>.<fmt>` micro-grid exists. A macro grid
     passing (1) proves NOTHING about (2) — they read different filenames,
     evaluated by different functions (`grid_emit_guard.require_emit` vs
     `grid_emit_guard.require_phase_grids_cli`), and a CLI wiring only the
     first would silently miss the per-phase promise until the plan is
     closed.

C4/F1 fix: `close` being correct in isolation was never
enough, because it was UNREACHABLE on the path that actually runs.
`write_verification`'s own `drive_lifecycle` (called by `cmd_verify`, default
ON) auto-flips `plan.md` to `completed` the instant
`derive_plan_completion.completion_state()["complete"]` — which checks
NOTHING about review-decision or the phase-grid gate — so `cook close` was
often never invoked at all by the time the plan already *looked* done. Two
changes close this, together:

  1. `cmd_close` itself now enforces `completion_state(...)["complete"]` AND
     a review-decision verdict of PASS BEFORE even reaching the phase-grid
     gate — so calling `close` directly (F1's exact repro: 0/2 phases, no
     review) refuses, regardless of grid mode.
  2. `cmd_next`/`cmd_status` no longer trust a `completed`/`in_progress`
     frontmatter status as authoritative (C0/F10) — they derive the
     state from artifacts every time and route through `_finalize_projection`
     regardless of what the frontmatter already claims. Because
     `_finalize_projection` runs its review-decision + phase-grid gates
     BEFORE ever reading `status`, THIS is the path that actually executes
     even when auto-finalize already flipped the frontmatter early — it
     reports `needs_review`/`needs_phase_grid_gate` honestly instead of
     `completed`.

Exit-code normalization (E24 — never pass a wrapped script's raw exit code
through): the four wrapped scripts this module calls for a MUTATING or
HARD-GATING action (`plan_graph`/`grid_emit_guard` internals via `preflight`;
`open_plan`; `close_plan` + `grid_emit_guard.require_phase_grids_cli` via
`close`; `write_verification` via `verify`) use THREE different raw exit-code
conventions among themselves (2 for a plan_graph/grid_emit_guard hard-stop, 1
for an open_plan/close_plan refusal, a SystemExit(1|2) from write_verification's
own `_die()`). Every one of those is mapped HERE to hs-run's own contract
(`EXIT_DONE`/`EXIT_NEEDS_MODEL`/`EXIT_NEEDS_STEP`/`EXIT_BROKEN` — mirroring
`hs_run.py`'s tiers, IMPORTED from it — the per-module copies this comment
once described were retired after ten of them drifted). A wrapped-script
failure NEVER surfaces as hs-run exit 0.

D10/L3 (the four-tier exit ladder, applied per-STATE not per-verb):
a prior version of this module gave EVERY `next`/`status` projection
EXIT_DONE(0) on the theory that "honestly reporting a block IS a successful
CLI run". A red-team + revalidation pass proved that
conflates two different machine-readable facts — "the CLI ran fine" (stdout
JSON, always valid) and "is there more work" (the actual exit code a
`while` loop keys on) — so a driver never learns the difference between
"done" and "0/2 phases passed, go spawn a developer". The table below is now
the single source of truth for every state this module can return:

  EXIT_DONE (0)         — no_plan (nothing exists yet), not_approved (nothing
                          for COOK to act on — a `plan` step must run first),
                          completed, closed/already_closed.
  EXIT_NEEDS_MODEL (10) — phase_needs_work, phase_failed, needs_review,
                          waiting_on_model (`prompt`), `record developer`'s
                          `recorded` (a model must read the report and choose
                          the verdict).
  EXIT_NEEDS_STEP (11)  — needs_open, ok (`preflight`), opened/already_open,
                          verified, phase_needs_reverify, needs_phase_grid_gate,
                          needs_close, `record <non-developer>`'s `recorded`
                          (its own follow-up is just `cook next` again) — a
                          deterministic CLI call remains; no judgment needed.
  EXIT_BROKEN (2)        — no_plan (`preflight`/`open`/`verify`/`close` — the
                          verb's ENTIRE job IS the gate/mutation, so an
                          unresolved plan means that job could not run at
                          all, unlike `next`/`status`'s idle "nothing to do
                          yet"), preflight_blocked, not_startable,
                          no_plan_graph, no_phase_resolved, unknown_phase,
                          phase_needs_post_artifact, state_conflict, and every
                          `error`/`*_failed` state.

Hard Cases — NOT disk-provable, named explicitly rather than assumed:
whether a step was actually delegated through a real `Task(subagent_type=...)`
spawn, vs. the model doing the work inline and reporting success, is a
TRANSCRIPT fact — `cook/SKILL.md:90`'s own admission ("Task-tool calls = 0 ⇒
INCOMPLETE") is unverifiable from disk. This module never claims to have
proven a delegation happened; `cmd_record` and `_finalize_projection` both
attach an explicit warning naming this limitation rather than silently
pretending the two-beat `prompt`/`record` pair is itself proof.
"""
from __future__ import annotations

import os
import re
import shlex
import sys

import attrs as _attrs  # noqa: E402  (REQUIRED — see harness/requirements.txt)
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import artifact_check  # noqa: E402
import derive_plan_completion  # noqa: E402
import frontmatter_parser  # noqa: E402
import defer_suite_carry  # noqa: E402
import graph_test_scope  # noqa: E402
import grid_emit_guard  # noqa: E402
import grid_flag_carry  # noqa: E402
import hs_run_next_command  # noqa: E402
import plan_graph  # noqa: E402
import plan_layout_check  # noqa: E402
import plan_status  # noqa: E402
import write_verification  # noqa: E402
from close_plan import close_plan as _close_plan  # noqa: E402
from open_plan import open_plan as _open_plan  # noqa: E402

# hs_run.py's own four-tier contract, IMPORTED rather than
# re-declared: the per-module copies drifted, so hs_run owns the ladder and
# every domain reads it from there.
# The four-tier ladder (D10), IMPORTED rather than re-declared.
# Ten modules used to hand-copy these four constants and had already drifted:
# rung 11 carried two different names across the tree and two modules declared
# the same constant twice. `hs_run` owns the ladder as a closed `Exit` IntEnum;
# both historical spellings of rung 11 are bound to the same member there, so
# this import changes no name any caller in this file uses.
import hs_run  # noqa: E402
from hs_run import EXIT_BROKEN, EXIT_DONE, EXIT_NEEDS_MODEL, EXIT_NEEDS_STEP  # noqa: E402

_ROLE_PROMPTS = {
    "developer": (
        "Spawn Task(subagent_type='hs:developer') for phase {phase}: implement "
        "red->green per the phase file (test first, intentional fail, then make "
        "it pass). When it returns, run: hs-run cook record developer --phase "
        "{phase} --out <file with its report>, then hs-run cook verify --phase "
        "{phase} --verdict <PASS|BLOCKED> --check <name>:<status> ..."
    ),
    "tester": (
        "Spawn Task(subagent_type='hs:tester') to run the full suite and report "
        "verdict + checks[]. Persist the result via hs-run cook verify (this "
        "module cannot prove from disk that the run went through the Task tool "
        "rather than inline — see Hard Case #1 in this module's header)."
    ),
    "code-reviewer": (
        "Spawn Task(subagent_type='hs:code-reviewer') to review the diff. It MUST "
        "record the verdict through harness/scripts/write_review_decision.py with "
        "--rounds-run <N> (the round it just ran), not by writing the file itself: "
        "the flag is what keeps a per-round review-decision-r<N>.json, so an earlier "
        "BLOCKED survives the round that clears it — the writer REFUSES without it "
        "(exit 2, nothing written). Verdict is PASS/PASS_WITH_RISK/BLOCKED; PASS and "
        "PASS_WITH_RISK both let the plan close, and PASS_WITH_RISK's rationale is "
        "carried into the closed record."
    ),
    "docs-manager": (
        "Spawn Task(subagent_type='hs:docs-manager') to sync project docs "
        "against the finished plan."
    ),
    "git-manager": (
        "Spawn Task(subagent_type='hs:git-manager') to stage + commit the "
        "plan's changes with a conventional commit."
    ),
}

# NARROWED, not retired. `record` no longer needs this: a `run_id` chain (the CLI
# stamps one per invocation -> hook_dispatch resolves the session's latest ->
# the PreToolUse(Agent|Task) hook records it on the spawn) lets `_attest_spawn`
# check whether a spawn of the asked-for role landed against the matching
# `prompt` call, so `record` reports `spawn_attested` and drops this warning on
# a run it could actually verify. Keeping a caveat that fires unconditionally is
# how a reader learns to skip it — and then it is not read on the run that
# matters.
#
# The states BELOW still carry it, and correctly: Step 4 (test) and Step 6
# (docs/git) have no `prompt`/`record` pair to attest against, so for those the
# sentence is still simply true.
_HARD_CASE_WARNING = (
    "cannot verify from disk that this step actually went through a real "
    "Task(subagent_type=...) spawn rather than the model doing the work "
    "inline and reporting success — that is a session-transcript fact, not "
    "a disk fact (Hard Case #1; "
    "cook/SKILL.md:90's own admission: \"Task-tool calls = 0 ⇒ "
    "INCOMPLETE\" is a transcript check). Treat a `record` as an "
    "attestation, never as proof."
)

# The verdicts `close` will finish on. PASS_WITH_RISK is a first-class outcome of the
# review writer (write_review_decision._VERDICTS) and of phase verification
# (`_phase_substate` below), but close demanded the literal string "PASS" — so a review
# that named its residual risk honestly wedged the plan forever, while a review that
# said nothing sailed through. That is backwards pressure on the reviewer. BLOCKED stays
# out: this widens the door, it does not remove it. The writer and this tuple have no
# shared import, so test_hs_run_cook.py pins them to each other.
#
# BOUNDARY — do not copy this tuple into artifact_check.py. That module's `_pass_only`
# set demands exactly PASS for review-decision at a HARD SHIP STAGE (push/pr/merge), on a
# recorded ruling that a soft self-accept is not a ship license. The two gates answer
# different questions and must keep different answers: finishing a plan records that the
# work is done and what risk it carries (`_closed_warnings`), while shipping asks whether
# the risk is acceptable to release. A plan can close carrying risk and still be unable
# to ship — that is the intended shape, not a drift to reconcile.
_CLOSEABLE_VERDICTS = ("PASS", "PASS_WITH_RISK")

# What a TERMINAL state has to keep saying. Steps 4 and 6 are delegations nothing on disk
# can confirm, and the states that warn about them are the ones still in flight — so the
# permanent record, the one read months later, was the only one that looked fully checked.
_CLOSED_ATTESTATION_WARNING = (
    "closed on attestation, not on proof: Step 4 (test) and Step 6 (docs/git) "
    "delegation was never verifiable from disk — " + _HARD_CASE_WARNING
)


def _closed_warnings(rec) -> list:
    """Warnings the closed/completed states carry. Never empty by construction: an
    empty list on a finished plan reads as "every obligation was checked", and two of
    them never were. A risk-carrying verdict adds its rationale, so the residual risk
    travels with the record instead of only living in the review artifact."""
    out = [_CLOSED_ATTESTATION_WARNING]
    if isinstance(rec, dict) and rec.get("verdict") == "PASS_WITH_RISK":
        out.append("review-decision verdict was PASS_WITH_RISK — this plan closed "
                   "carrying reviewer-noted risk: %s"
                   % (rec.get("rationale") or "(no rationale recorded)"))
    return out


# --------------------------------------------------------------- arg parsing

def _help_requested(argv) -> bool:
    """R3/C2: every MUTATING/gating cook verb checks this itself,
    regardless of what hs_run.py's own dispatcher does (that module is out
    of this domain's lane) — `hs-run cook open --help` used to actually open
    the plan (`verb_args = ["--help"]` reaches `cmd_open` unfiltered, since
    the dispatcher only special-cases `-h`/`--help` as the FIRST token after
    the domain, not inside a verb's own argv), and `hs-run cook verify
    --help` used to let write_verification's own argparse print its help to
    STDOUT (corrupting this process's JSON envelope) while still reporting
    state="verified" — a lie, nothing was verified. Checked first, before
    any plan resolution or disk mutation, in every verb below that can
    mutate or gate."""
    return any(a in ("-h", "--help") for a in (argv or []))


def _help_envelope(usage: str) -> dict:
    """A terminal, side-effect-free answer to `-h`/`--help` — EXIT_DONE (no
    more work, matches hs_run.py's own top-level/domain help tier), never
    EXIT_NEEDS_STEP/EXIT_NEEDS_MODEL (asking for usage is not a step toward
    doing anything) and never the verb's own success state (asking for help
    is not the verb having run)."""
    return hs_run.StepResult(
        state="help",
        next_action=usage,
        artifacts=[],
        warnings=[],
        exit_code=EXIT_DONE,
    ).as_dict()


def _strip_flag(argv, name):
    """argv with `name` and its value removed (both `--name value` and
    `--name=value` spellings) — used before forwarding argv to a wrapped
    script's own argparse, which does not know this flag."""
    argv = list(argv or [])
    out = []
    skip_next = False
    for a in argv:
        if skip_next:
            skip_next = False
            continue
        if a == name:
            skip_next = True
            continue
        if a.startswith(name + "="):
            continue
        out.append(a)
    return out


# ------------------------------------------------------------- plan resolve

def _plan_dirs(root: Path) -> list:
    """Every `plans/<id>-<slug>/` directory carrying a `plan.md` (unchanged
    from the P0 floor — the one disk signal guaranteed present the moment
    `scaffold.py plan` has run)."""
    plans_dir = Path(root) / "plans"
    if not plans_dir.is_dir():
        return []
    return sorted(p for p in plans_dir.iterdir()
                  if p.is_dir() and (p / "plan.md").is_file())


def _frontmatter_status(plan_dir: Path):
    """The plan's normalized frontmatter status, or None if unreadable/absent.
    Reuses frontmatter_parser + plan_status.normalize_status rather than a
    second regex — one parser, one fold table."""
    parsed = frontmatter_parser.parse_file(Path(plan_dir) / "plan.md")
    if not parsed.get("ok"):
        return None
    raw = (parsed.get("frontmatter") or {}).get("status")
    return plan_status.normalize_status(raw) if raw else None


def _resolve_plan_dir_verbose(root, explicit=None):
    """(plan_dir_or_None, miss_or_None).

    Same resolution `_resolve_plan_dir` used to do inline, but a miss now
    also names WHY (F6): `_resolve_plan_dir`'s old single `None`
    collapsed three different situations — an explicit `--plan` typo, zero
    startable candidates, and an AMBIGUOUS choice between multiple approved
    plans — into one generic message, which actively misdirected (F6's
    reproduced examples: an in_progress plan on disk reported as "none is
    in_progress"; two approved plans reported as "none is
    approved-and-unopened"). `miss["kind"]` is one of:
      - "explicit_not_found": the `--plan` path given does not exist.
      - "ambiguous_approved": >1 plan is approved-and-unopened at once.
      - "no_candidates": nothing in_progress, uniquely approved, or (as a
        last resort) freshly completed.

    Resolution ORDER is unchanged from before: explicit wins outright; else
    an in_progress plan (`artifact_check.resolve_active_plan`) wins; else
    exactly one approved-and-unopened plan; else the newest just-closed plan
    (mirrors the ship-gate's own allow_completed carve-out). Only when NONE
    of those succeed do we decide which miss reason to report."""
    root = Path(root)
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = root / p
        if p.is_dir():
            return p, None
        # A file INSIDE the plan dir names that plan — `--plan <dir>/plan.md` is the
        # spelling the approved-plan envelope itself hands the operator, and the plan
        # domain already resolves it (`hs_run_plan._resolve_plan_arg`). Testing
        # `is_dir()` alone sent the file spelling to `explicit_not_found`, where the
        # fallback scan then answered about a DIFFERENT plan — `not_approved` on a plan
        # that IS approved. Resolving to the parent keeps one answer per plan.
        if p.is_file():
            # Only a file whose parent actually IS a plan dir. A phase file under
            # `phases/` has a parent that is not one, and returning it resolved to a
            # directory with no plan.md — reported downstream as `not_startable`, a
            # sentence about the plan's readiness for a path that names no plan at all.
            # `plan_approval.py` answers this same input by naming the miss; matching it
            # keeps one CLI with one answer.
            if (p.parent / "plan.md").is_file():
                return p.parent, None
            return None, {"kind": "explicit_not_found", "path": str(p)}
        return None, {"kind": "explicit_not_found", "path": str(p)}

    env_raw = os.environ.get("HARNESS_ACTIVE_PLAN")
    active = artifact_check.resolve_active_plan(str(root))
    if active is not None:
        return active, None
    if env_raw:
        # R15: HARNESS_ACTIVE_PLAN was explicitly SET but
        # resolve_active_plan's own fail-closed contract rejected it (it
        # names something outside <root>/plans/, or nothing at all —
        # artifact_check.py:186-189's own docstring calls this deliberate).
        # That refusal must not be silently overridden by falling through to
        # the disk-scan fallback below and opening a DIFFERENT plan the
        # operator never named — the operator's explicit intent failed, and
        # guessing a substitute is worse than refusing.
        return None, {"kind": "active_plan_rejected", "value": env_raw}

    approved = [d for d in _plan_dirs(root) if _frontmatter_status(d) == "approved"]
    if len(approved) == 1:
        return approved[0], None

    completed = artifact_check.resolve_active_plan(str(root), allow_completed=True)
    if completed is not None:
        return completed, None

    if len(approved) > 1:
        return None, {"kind": "ambiguous_approved",
                       "candidates": [str(d) for d in approved]}
    return None, {"kind": "no_candidates"}


def _resolve_plan_dir(root: Path, explicit=None):
    """Back-compat thin wrapper over `_resolve_plan_dir_verbose` — most
    callers only need the path, not the miss reason."""
    plan_dir, _miss = _resolve_plan_dir_verbose(root, explicit=explicit)
    return plan_dir


def _no_plan_message(miss) -> str:
    """The accurate, reason-specific message for a MUTATING/gate verb
    (`preflight`/`open`/`verify`/`close`) whose entire job could not even
    start because no plan resolved (F6/F8). These verbs all
    report state `no_plan` at EXIT_BROKEN uniformly (D10/L3's "no_plan phải
    trả MỘT con số duy nhất trong toàn cook") — only the message differs by
    the real reason."""
    if not miss:
        return "no approved-and-unopened or in_progress plan found"
    kind = miss["kind"]
    if kind == "explicit_not_found":
        return "--plan %s does not exist" % miss["path"]
    if kind == "active_plan_rejected":
        return ("HARNESS_ACTIVE_PLAN=%r does not resolve to a plan under "
                 "this project's plans/ dir — refusing to silently cook a "
                 "DIFFERENT plan instead; fix or unset HARNESS_ACTIVE_PLAN, "
                 "or pass --plan explicitly" % miss["value"])
    if kind == "ambiguous_approved":
        return ("%d plan(s) are approved-and-unopened at once (%s) — "
                 "ambiguous which to cook; pass --plan explicitly"
                 % (len(miss["candidates"]), ", ".join(miss["candidates"])))
    return "no approved-and-unopened or in_progress plan found"


def _not_approved_message(miss, dirs) -> str:
    """The `next`/`status` (pure projection) equivalent of `_no_plan_message`
    — same reason-distinguishing improvement, but `next`'s own "nothing for
    cook to act on yet" state stays EXIT_DONE (a projection honestly
    reporting an idle state is a complete, successful answer), unlike a
    mutating verb whose job failed to
    even run."""
    if not miss:
        return ("%d plan dir(s) found but none is approved-and-unopened or "
                 "in_progress — approve a plan first" % len(dirs))
    kind = miss["kind"]
    if kind == "explicit_not_found":
        return "no plan at %s" % miss["path"]
    if kind == "active_plan_rejected":
        return ("HARNESS_ACTIVE_PLAN=%r does not resolve to a plan under "
                 "this project's plans/ dir — refusing to silently cook a "
                 "DIFFERENT plan instead; fix or unset HARNESS_ACTIVE_PLAN, "
                 "or pass --plan explicitly" % miss["value"])
    if kind == "ambiguous_approved":
        return ("%d plan(s) are approved-and-unopened at once (%s) — "
                 "ambiguous; pass --plan explicitly"
                 % (len(miss["candidates"]), ", ".join(miss["candidates"])))
    return ("%d plan dir(s) found but none is approved-and-unopened or "
             "in_progress — approve a plan first" % len(dirs))


def _approval_gate_reason(plan_dir: Path, root) -> "str | None":
    """None when this plan may proceed past the approval gate (`preflight`/
    `open`); else the reason it must not.

    R2: C1 moved into cook. Before this fix,
    `cmd_open`/`cmd_preflight` decided a plan was safe to act on PURELY from
    `_frontmatter_status(d) == "approved"` (the old `hs_run_cook.py:288`
    bug) and never read the plan-approval ARTIFACT at all — a REJECTED
    verdict, a drifted approval, or a foreign plan's approval copied in all
    still let `cook open` write `status: in_progress` to disk. The plan
    domain already delegates this judgment correctly to the real owner,
    `artifact_check._check_plan_approval` (its declared owner)
    — this mirrors that exactly, reading the artifact through the SAME
    shared, containment-safe reader (`artifact_check._load_artifact`, used
    elsewhere in this module for `review-decision`) rather than a second
    hand-rolled parser, which would only reopen the F5/C5-shaped risk of a
    THIRD frontmatter/artifact reader disagreeing with the other two.

    Refuses in exactly ONE situation: an approval artifact IS present but
    does not currently validate — bad verdict, wrong plan binding, drifted
    plan_hash, or unreadable/forged (any `_load_artifact` problem other than
    "missing"). This mirrors the plan domain's OWN model precisely: `_project_
    inner`'s "approved" branch (hs_run_plan.py:493-499) is keyed ENTIRELY on
    the approval ARTIFACT's presence+validity, never on `status:` at all —
    `status:` is not even consulted for that decision there. A plan with NO
    approval artifact at all is untouched here regardless of what `status:`
    claims, for the same reason: `open_plan.py`'s own `_STARTABLE` set
    intentionally includes `pending`/`draft` as a solo/back-compat path with
    no approval workflow expected (see its module docstring, and
    `artifact_check.py`'s own: "Self-approval is deliberate anti-drift
    discipline, not an anti-fraud check") — inventing a NEW "status:
    approved requires a backing artifact" rule here would go beyond what
    R2's own three reproduced attacks needed (all three had an artifact
    PRESENT, just invalid) and would conflict with the domain-agnostic
    conformance suite's own cook fixture, which legitimately builds a
    `status: approved` plan with no approval artifact at all
    (`test_hs_run_contract_conformance.py::_cook_write_plan` — the SSOT for
    this contract, goal D12)."""
    rec, problem = artifact_check._load_artifact(Path(plan_dir), "plan-approval")
    if rec is None:
        if problem != "missing":
            return "plan-approval artifact is present but %s" % problem
        return None
    return artifact_check._check_plan_approval(Path(plan_dir), rec, root)


def _phase_order(graph: dict) -> list:
    """A deterministic phase visiting order: plan_graph's own topological
    batches (each batch already sorted by name), flattened. For a plan with
    no edges at all every node lands in one batch, sorted by name — reuses
    `plan_graph.find_parallel_batches` rather than re-deriving order here
    (survival invariant #4)."""
    order = []
    for batch in plan_graph.find_parallel_batches(graph):
        order.extend(batch)
    return order


# ------------------------------------------------------------ 0.5a-0.5c: preflight

def _run_preflight(plan_dir: Path, root=None) -> dict:
    """The ONE-TIME, plan-level preflight (cook Steps 0.5a-0.5c): the
    plan-approval gate (see `_approval_gate_reason`), the
    plan-graph sidecar must exist with every node's `post:` obligation
    declared (`plan_graph.py --require`-equivalent, unconditional per node
    regardless of --require in the wrapped script itself — see
    `plan_graph.py`'s own `_main`), that `post:` obligation must be
    resolvable at all (F4 — see the bad-prefix check below), and — ONLY when
    grid mode is carried (`grid_flag_carry.resolve_grid_carry`) — the MACRO
    `coverage-grid.json` artifact must satisfy `grid_emit_guard.require_emit`
    (0.5c). Also folds `defer_suite_carry.resolve_defer_suite_carry` — purely
    advisory, never appended to `reasons[]` (deferring the suite is never
    itself a block).

    Returns {"blocked": bool, "reasons": [str, ...], "grid_carry": {...},
    "defer_suite_carry": {...}} — never raises; a malformed plan-graph is a
    reason, not a crash."""
    reasons = []
    approval_reason = _approval_gate_reason(plan_dir, root)
    if approval_reason:
        reasons.append("plan-approval (0.5x): %s" % approval_reason)
    graph = plan_graph.parse_phase_graph(plan_dir)
    if graph.get("error"):
        reasons.append("plan-graph (0.5a): %s" % graph["error"])
    else:
        missing = plan_graph.find_missing_post(graph)
        if missing:
            reasons.append(
                "plan-graph (0.5a): node(s) missing a declared 'post:' artifact "
                "obligation: %s" % ", ".join(missing))
        # F4: a post: entry authored WITH the "artifacts/" prefix
        # double-resolves under <plan>/artifacts/artifacts/... and can never
        # satisfy derive_plan_completion — cook then falls into "go implement
        # it again" forever for a phase that already verified PASS. Catch the
        # authoring mistake here, before phase 1 ever starts, rather than
        # mid-cook (`_phase_substate` below is the defense-in-depth fallback
        # for a plan-graph edited to introduce this AFTER preflight already
        # ran).
        bad_prefix = []
        for node in sorted(plan_graph._all_nodes(graph)):
            for name in plan_graph.node_artifacts(graph, node)["post"]:
                if name.startswith("artifacts/") or name.startswith("artifacts\\"):
                    bad_prefix.append("%s: %r" % (node, name))
        if bad_prefix:
            reasons.append(
                "plan-graph (0.5a): post: entries already resolve under "
                "<plan>/artifacts/ — remove the redundant 'artifacts/' "
                "prefix or it will never resolve: %s" % "; ".join(bad_prefix))

    carry = grid_flag_carry.resolve_grid_carry(plan_dir)
    if carry["carried"]:
        msg, code = grid_emit_guard.require_emit(plan_dir)
        if code != 0:
            reasons.append("grid macro presence (0.5c): %s" % msg)

    # Advisory only, like grid_carry above: NEVER appended to reasons[] — the
    # phase's own decision is that deferring the suite must never itself be
    # gated (that would defeat the point of the flag).
    defer_carry = defer_suite_carry.resolve_defer_suite_carry(plan_dir)

    return PreflightResult(reasons=reasons, grid_carry=carry,
                           defer_suite_carry=defer_carry,
                           warnings=_layout_warnings(plan_dir)).as_dict()


@_attrs.define(frozen=True, kw_only=True)
class PreflightResult:
    """What cook's preflight found, declared rather than assembled.

    `blocked` is derived from `reasons` on purpose: the two disagreeing -- a
    non-empty reason list with `blocked: False` -- is the exact "reports done
    when it meant broken" shape, and deriving it makes that disagreement
    unrepresentable instead of merely unlikely."""

    reasons: list = _attrs.field(factory=list)
    grid_carry: dict = _attrs.field(factory=dict)
    defer_suite_carry: dict = _attrs.field(factory=dict)
    warnings: list = _attrs.field(factory=list)

    @property
    def blocked(self) -> bool:
        return bool(self.reasons)

    def as_dict(self) -> dict:
        return {"blocked": self.blocked, "reasons": list(self.reasons),
                "grid_carry": self.grid_carry,
                "defer_suite_carry": self.defer_suite_carry,
                "warnings": list(self.warnings)}


def _layout_warnings(plan_dir: Path) -> list:
    """Plan-layout drift, ADVISORY — `warnings`, never `reasons`.

    Kept out of `reasons` on purpose: `plan_layout_check` is exit-0 by
    construction, and a check that starts blocking work is a check someone
    switches off. The blocking guarantee stays where it already is, in
    `plan_approval`'s hash. What this adds is that the drift is now SAID by the
    verb rather than by a line of skill prose asking a model to remember to run
    a script — a model that forgets produces the same silence as a clean plan.

    Read-only and defensive: an unreadable plan dir yields no warning rather
    than taking preflight down, since the advisory is not what preflight is
    for."""
    try:
        return list(plan_layout_check.layout_warnings(plan_dir))
    except Exception:
        return []


_USAGE_PREFLIGHT = "usage: hs-run cook preflight [--plan <dir>]"


def cmd_preflight(argv, root) -> dict:
    return hs_run_next_command.finalize(_cmd_preflight_impl(argv, root))


def _cmd_preflight_impl(argv, root) -> dict:
    """`hs-run cook preflight [--plan <dir>]` — the direct wrap of cook Steps
    0.5a-0.5c. Unlike `next`, this verb's whole job IS the gate action, so a
    genuine block normalizes to EXIT_BROKEN (E24) — never a silent exit 0.
    A cleared preflight still leaves the deterministic `cook open` step —
    EXIT_NEEDS_STEP, not EXIT_DONE (D10/L3)."""
    if _help_requested(argv):
        return _help_envelope(_USAGE_PREFLIGHT)
    ns = hs_run.parse_verb_argv("hs-run cook preflight", argv, options=("plan",))
    plan_dir, miss = _resolve_plan_dir_verbose(Path(root), explicit=ns.plan)
    if plan_dir is None:
        return hs_run.StepResult(
            state="plan_unresolved",
            next_action=_no_plan_message(miss),
            artifacts=[],
            warnings=[],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    pf = _run_preflight(plan_dir, root=root)
    if pf["blocked"]:
        return hs_run.StepResult(
            state="blocked",
            next_action="fix before opening: %s" % "; ".join(pf["reasons"]),
            artifacts=[str(plan_dir)],
            warnings=pf["reasons"] + pf["warnings"],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    return hs_run.StepResult(
        state="ok",
        next_action="preflight clear — open the plan: hs-run cook open %s" % plan_dir,
        # `--plan <dir>`, NOT the bare positional the sentence shows. `cmd_open`
        # reads its target from `--plan` only, so the bare form names a
        # directory the verb never looks at.
        # That used to fail SILENTLY: the positional was ignored and the verb
        # re-resolved the active plan, reporting `no_plan` for a directory that
        # exists. It now REJECTS it — measured: `hs-run cook open /tmp/x` ->
        # "unrecognized arguments: /tmp/x", exit 2. The declared-flag parser is
        # what closed it; the old containment check could not, since it only
        # asks whether a command-shaped substring is present, never whether the
        # command would do what the sentence says.
        # `next_action` is left exactly as it was — fixing the human sentence is
        # a separate change with a separate reader.
        next_command="hs-run cook open --plan %s" % plan_dir,
        artifacts=[str(plan_dir)], warnings=pf["warnings"],
        extra={"grid_carried": pf["grid_carry"]["carried"],
               "defer_suite_carried": pf["defer_suite_carry"]["carried"]},
        exit_code=EXIT_NEEDS_STEP,
    ).as_dict()


# --------------------------------------------------------------- 0.6: open

_USAGE_OPEN = "usage: hs-run cook open [--plan <dir>]"


def cmd_open(argv, root) -> dict:
    return hs_run_next_command.finalize(_cmd_open_impl(argv, root))


def _cmd_open_impl(argv, root) -> dict:
    """`hs-run cook open [--plan <dir>]` — wraps `open_plan.open_plan`
    (cook Step 0.6). The raw script's own refusal is exit 1 (E24); here it is
    normalized to EXIT_BROKEN(2), never passed through and never reported as
    a silent success. A successful open still leaves the deterministic
    `cook next` step — EXIT_NEEDS_STEP (D10/L3).

    R2: before touching disk, this now runs the SAME
    plan-approval judgment `_run_preflight` runs (`_approval_gate_reason`,
    the real owner `artifact_check._check_plan_approval`) — a REJECTED
    verdict, a drifted approval, or a foreign plan's approval copied in all
    refuse here now, `approval_invalid` (mirrors the plan domain's own state
    name for the identical judgment, hs_run_plan.py:508)."""
    if _help_requested(argv):
        return _help_envelope(_USAGE_OPEN)
    ns = hs_run.parse_verb_argv("hs-run cook open", argv, options=("plan",))
    plan_dir, miss = _resolve_plan_dir_verbose(Path(root), explicit=ns.plan)
    if plan_dir is None:
        return hs_run.StepResult(
            state="plan_unresolved",
            next_action=_no_plan_message(miss),
            artifacts=[],
            warnings=[],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    gate_reason = _approval_gate_reason(plan_dir, root)
    if gate_reason is not None:
        return hs_run.StepResult(
            # `approval_refused`, not `approval_invalid`. The projection verb in
            # the plan domain reports `approval_invalid` at rung 10 for the same
            # artifact; this is `open` refusing to mutate, which is a stop rather
            # than a step someone can take a model turn on.
            state="approval_refused",
            next_action="cook open refuses: %s" % gate_reason,
            artifacts=[str(plan_dir)],
            warnings=[gate_reason],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    res = _open_plan(plan_dir, root=root)
    if not res.ok:
        return hs_run.StepResult(
            state="open_failed",
            next_action=res.message,
            artifacts=[str(plan_dir)],
            warnings=[res.message],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    return hs_run.StepResult(
        state="opened" if res.changed else "already_open",
        next_action="hs-run cook next --plan %s" % plan_dir,
        next_command="hs-run cook next --plan %s" % plan_dir,
        artifacts=[str(plan_dir)],
        warnings=[],
        exit_code=EXIT_NEEDS_STEP,
    ).as_dict()


# ------------------------------------------------------------- 4: verify

_USAGE_VERIFY = (
    "usage: hs-run cook verify [--plan <dir>] --phase P --verdict V "
    "[--stage S] [--check name:status ...] | --from FILE")


def _parse_verify_argv(argv):
    """`cook verify`'s declared flag set, kept next to `_USAGE_VERIFY` above so
    the two cannot drift apart — a flag added to the usage line and forgotten
    here becomes a rejected call for something the usage string advertises."""
    p = hs_run.VerbParser(prog="hs-run cook verify")
    p.add_argument("--plan")
    p.add_argument("--phase")
    p.add_argument("--verdict")
    # `--stage` is what a deferred-suite debt-payment run stamps itself with, and
    # this verb is the ONLY path that suppresses the auto-finalize status flip.
    # Undeclared, the reminder printed a command this parser rejected, so the
    # only way to pay the debt was the raw writer — around that suppression.
    p.add_argument("--stage")
    p.add_argument("--from", dest="from_file")
    p.add_argument("--check", action="append", default=[])
    return p.parse_args(list(argv or []))


def cmd_verify(argv, root) -> dict:
    return hs_run_next_command.finalize(_cmd_verify_impl(argv, root))


def _cmd_verify_impl(argv, root) -> dict:
    """`hs-run cook verify [--plan <dir>] --phase P --verdict V [--check n:s
    ...] | --from FILE` — wraps `write_verification.main` (cook Step 4).

    `write_verification.py` has no `--plan`/`--root` selector flag; it takes
    the plan dir POSITIONALLY. This verb resolves the active/explicit plan
    dir itself and prepends it, and normalizes write_verification's own
    SystemExit(1|2) (its `_die()` path) to EXIT_BROKEN — the raw code is
    never passed through (E24). A successful write still leaves the
    deterministic `cook next` step — EXIT_NEEDS_STEP (D10/L3).

    R1 fix (HIGHEST SEVERITY, and the original defect this whole
    module exists to close): `write_verification.main`'s own call to
    `vsnap.drive_lifecycle` (`write_verification.py:250-251`), gated on
    `verification_snapshot.auto_finalize_enabled()` (default ON), used to
    flip `plan.md` all the way to `completed` the instant every phase held a
    PASS snapshot — behind the review-decision + phase-grid gate
    `cmd_close` enforces. `close` never even ran; the plan was already
    "done", `verify`'s own response never said so ("state": "verified",
    nothing about closing), and a subsequent `review-decision.json` verdict
    BLOCKED then locked the plan in `completed` with NO verb able to reopen
    it (`open_plan` only accepts pending/approved/draft; `close_plan` only
    accepts in_progress). Hand-reproduced in both the self-host shape and
    the exact global-install shape (HARNESS_BIN_ROOT set,
    CLAUDE_PROJECT_DIR pointing at a project distinct from the bin root —
    the self-host shape alone silently no-ops the flip, per the
    `test_default_env_*` tests' own docstrings, so it does not surface the
    bug at all without reproducing that exact shape).

    Fix: force HARNESS_AUTO_FINALIZE=0 for the duration of THIS in-process
    call only (the previous value is saved and restored in `finally` —
    never a global, process-wide disable). `cmd_close` remains the ONLY
    path in this module that can flip a plan to `completed`, and its own
    completion gate is unaffected by this env var (it does not read it) — so
    with this fix a plan can reach `completed` ONLY through a call that
    already enforces review-decision PASS + the phase-grid gate, which
    means the "locked in completed with no way back" failure mode this verb
    used to cause cannot arise via `hs-run cook verify` at all (proven by
    `test_verify_does_not_auto_finalize_plan_behind_review_gate` and the
    BLOCKED-review follow-up in the same test). The per-phase snapshot
    (verification-<phase>.json) still happens regardless — the kill-switch
    only suppresses the STATUS FLIP, matching `verification_snapshot.py`'s
    own comment at line 52.

    C2 fix: `-h`/`--help` anywhere in argv now short-circuits to
    a help envelope BEFORE write_verification ever runs (`_help_requested`,
    checked regardless of what hs_run.py's own dispatcher does — that
    module is a different lane). Before this fix, `--help` reached
    write_verification's own `argparse.ArgumentParser(add_help=True)`,
    which prints its usage to STDOUT — corrupting THIS process's own JSON
    envelope (the help text lands on stdout before the JSON line, so
    `json.loads(stdout)` raised) — while `write_verification.main` still
    returned 0 (argparse's own `-h` handler calls `sys.exit(0)`), so this
    verb still reported `state: "verified"`: a lie, nothing was verified, no
    artifact written. Both stdout AND stderr are now captured (not just
    stderr, as before) around the wrapped call, as defense in depth against
    any other unexpected stdout write from write_verification."""
    if _help_requested(argv):
        return _help_envelope(_USAGE_VERIFY)
    # Full flag set from this verb's own usage string, not just the one flag
    # read here: an incomplete list REJECTS a call that works today. `--check`
    # repeats (`--check name:status ...`), so it is append; the rest are read
    # further down from `argv` directly and are declared only so the parser
    # recognises them.
    ns = _parse_verify_argv(argv)
    plan_dir, miss = _resolve_plan_dir_verbose(Path(root), explicit=ns.plan)
    if plan_dir is None:
        return hs_run.StepResult(
            state="plan_unresolved",
            next_action=_no_plan_message(miss),
            artifacts=[],
            warnings=[],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    rest = _strip_flag(argv, "--plan")
    full_argv = [str(plan_dir)] + rest

    import contextlib
    import io
    buf = io.StringIO()
    prev_auto_finalize = os.environ.get("HARNESS_AUTO_FINALIZE")
    os.environ["HARNESS_AUTO_FINALIZE"] = "0"
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = write_verification.main(full_argv)
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
    finally:
        if prev_auto_finalize is None:
            os.environ.pop("HARNESS_AUTO_FINALIZE", None)
        else:
            os.environ["HARNESS_AUTO_FINALIZE"] = prev_auto_finalize
    err_text = buf.getvalue().strip()

    if code != 0:
        return hs_run.StepResult(
            state="verify_failed",
            next_action=err_text or "write_verification failed (see warnings)",
            artifacts=[str(plan_dir)],
            warnings=[err_text] if err_text else [],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    return hs_run.StepResult(
        # `verification_recorded`, not `verified`. This verb WROTE the artifact and
        # still owes the caller one deterministic step (rung 11); the sibling `test`
        # domain's `verified` is a rung-0 reading of an artifact someone else wrote.
        # One word on two rungs made a driver's next move depend on which verb it
        # happened to ask rather than on what is on disk.
        state="verification_recorded",
        next_action="hs-run cook next --plan %s" % plan_dir,
        next_command="hs-run cook next --plan %s" % plan_dir,
        artifacts=[str(plan_dir / "artifacts")],
        warnings=[],
        exit_code=EXIT_NEEDS_STEP,
    ).as_dict()


# ---------------------------------------------------------- 6e + 6g: close

_USAGE_CLOSE = "usage: hs-run cook close [--plan <dir>]"


def cmd_close(argv, root) -> dict:
    return hs_run_next_command.finalize(_cmd_close_impl(argv, root))


def _cmd_close_impl(argv, root) -> dict:
    """`hs-run cook close [--plan <dir>]` — wraps the closing steps, in
    order: (1) the completion + review gate, (2)
    the 6e phase-count grid gate (`grid_emit_guard.require_phase_grids_cli`),
    THEN (3) `close_plan.close_plan` (6g).

    F1's exact repro (HIGHEST SEVERITY): before this fix, `close`
    ran ONLY the 6e grid gate — which returns 0 immediately when grid mode is
    off (cook's DEFAULT, E15) — so a plan with 0/2 phases verified and no
    review-decision closed anyway. Before `close` (and before every
    auto-finalize path — see this module's docstring for how `next` covers
    the auto-finalize path) enforce `review-decision` = PASS AND
    `completion_state(...)["complete"]`, else EXIT_BROKEN naming that
    function's own reason. This is a SEPARATE call from `preflight`'s 0.5c
    macro grid check (E27), reading a different file set
    (`coverage-grid-<phase>.<fmt>` per declared phase, not the macro
    `coverage-grid.json`). Any failure refuses to even attempt the close
    (never partially closes then reports a mismatched success).

    R3: `-h`/`--help` used to reach this verb's own body
    unfiltered and actually close the plan (`hs-run cook close --help`
    flipped `status: in_progress -> completed`) — guarded here regardless of
    what hs_run.py's dispatcher does."""
    if _help_requested(argv):
        return _help_envelope(_USAGE_CLOSE)
    ns = hs_run.parse_verb_argv("hs-run cook close", argv, options=("plan",))
    plan_dir, miss = _resolve_plan_dir_verbose(Path(root), explicit=ns.plan)
    if plan_dir is None:
        return hs_run.StepResult(
            state="plan_unresolved",
            next_action=_no_plan_message(miss),
            artifacts=[],
            warnings=[],
            exit_code=EXIT_BROKEN,
        ).as_dict()

    comp = derive_plan_completion.completion_state(plan_dir, root=root)
    if not comp["complete"]:
        return hs_run.StepResult(
            # `phases_incomplete`, not `needs_implementation`. This is the MUTATING
            # close verb refusing to write (rung 2); the projection reports the same
            # tree at rung 0 as work still owed. Same predicate, different question
            # — so a different word, matching how `review_missing` was split from
            # `needs_review` at the gate directly below.
            state="phases_incomplete",
            next_action=comp["reason"],
            artifacts=[str(plan_dir)],
            warnings=[comp["reason"]],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    rec, _p = artifact_check._load_artifact(plan_dir, "review-decision")
    if not isinstance(rec, dict) or rec.get("verdict") not in _CLOSEABLE_VERDICTS:
        return hs_run.StepResult(
            # `review_missing`, not `needs_review`. Same predicate, different
            # question: this is a MUTATING verb refusing to write, where the
            # projection verb's `needs_review` reports the same tree at rung 10
            # as work still owed. One word riding both rungs told a driver two
            # different things about one artifact.
            state="review_missing",
            next_action="hs-run cook prompt code-reviewer, then hs-run cook "
                             "record code-reviewer --out <file> before close can "
                             "proceed",
            artifacts=[str(plan_dir)],
            warnings=["cook close requires a review-decision verdict in %s "
                         "before it will finalize the plan"
                         % (_CLOSEABLE_VERDICTS,)],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    msg, code = grid_emit_guard.require_phase_grids_cli(plan_dir)
    if code != 0:
        return hs_run.StepResult(
            state="blocked_grid_phase_gate",
            next_action=msg,
            artifacts=[str(plan_dir)],
            warnings=[msg],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    # Fourth refusal, narrowest question and last asked: only a plan that opted
    # into defer_suite rides this branch at all (`_suite_debt_unpaid` is never
    # consulted otherwise), and only when its canonical verification still
    # lacks a closeable verdict. Reuses `_suite_debt_unpaid` — the exact
    # function `pending` above already reads — so the two can never answer
    # this question differently.
    if (defer_suite_carry.resolve_defer_suite_carry(plan_dir)["carried"]
            and _suite_debt_unpaid(plan_dir)):
        return hs_run.StepResult(
            state="suite_debt_unpaid",
            next_action=_PENDING_DEBT_ITEM,
            artifacts=[str(plan_dir)],
            warnings=[_PENDING_DEBT_ITEM],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    res = _close_plan(plan_dir, root=root)
    if not res.ok:
        return hs_run.StepResult(
            state="close_failed",
            next_action=res.message,
            artifacts=[str(plan_dir)],
            warnings=[res.message],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    return hs_run.StepResult(
        state="closed" if res.changed else "already_closed",
        next_action="cook chain complete for %s" % plan_dir,
        # Stated rather than inherited. 0 IS right here — the chain is over —
        # but a rung that arrives by default looks identical to one nobody
        # thought about, and four states reached callers that way.
        exit_code=EXIT_DONE,
        artifacts=[str(plan_dir)], warnings=_closed_warnings(rec),
    ).as_dict()


# --------------------------------------------------------- two-beat prompt/record

def cmd_prompt(argv, root) -> dict:
    return hs_run_next_command.finalize(_cmd_prompt_impl(argv, root))


def _cmd_prompt_impl(argv, root) -> dict:
    """`hs-run cook prompt <role> [--phase <id>]` — beat 1 of the two-beat
    model pattern. Always returns EXIT_NEEDS_MODEL(10): by
    definition its entire job is "go spawn a subagent now." Never named
    `call` — the name would promise execution — and never spawns anything itself."""
    if not argv:
        return hs_run.StepResult(
            state="error",
            next_action="usage: hs-run cook prompt <role> [--phase <id>]",
            artifacts=[],
            warnings=["missing role"],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    role, rest = argv[0], argv[1:]
    if role not in _ROLE_PROMPTS:
        return hs_run.StepResult(
            state="error",
            next_action="unknown role %r (known: %s)"
                            % (role, ", ".join(sorted(_ROLE_PROMPTS))),
            artifacts=[],
            warnings=[],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    phase = hs_run.parse_verb_argv("hs-run cook prompt %s" % role, rest,
                                   options=("phase",)).phase
    if role == "developer" and not phase:
        return hs_run.StepResult(
            state="error",
            next_action="prompt developer needs --phase <id>",
            artifacts=[],
            warnings=[],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    text = _ROLE_PROMPTS[role].format(phase=phase or "")
    record_cmd = "hs-run cook record %s --out <file>" % role
    if phase:
        record_cmd += " --phase %s" % phase
    return hs_run.StepResult(
        state="waiting_on_model",
        next_action="spawn the subagent per prompt_text, then run: %s" % record_cmd,
        artifacts=[],
        warnings=[],
        exit_code=EXIT_NEEDS_MODEL,
        extra={"prompt_text": text, "role": role},
    ).as_dict()


_ATTEST_MODE_ENV = "HARNESS_SPAWN_ATTEST_MODE"


def _attest_spawn(role):
    """(attested, note) — did a spawn of `role` land against this session's most
    recent `hs-run cook prompt` call?

    This is what `run_id` bought. `_HARD_CASE_WARNING` used to be unconditionally
    true; now the chain (CLI stamps an id -> dispatcher resolves it -> the
    PreToolUse hook records it on the spawn) leaves a disk fact where there was
    only a transcript fact.

    Matching is on run_id AND session AND subagent_type. Dropping the last one
    would leave a check that proves only that SOMETHING was spawned, so a model
    could spawn any agent and still record a `developer` step — the laundering
    this exists to catch, surviving it.

    Returns `(False, note)` for every hole in the chain, and the note says NO
    EVIDENCE, never "no spawn happened". The difference is the whole design: the
    hook may be disabled, the state dir may differ, the session may have been
    resumed, agents may run in parallel. Claiming absence from those is the
    overreach that got the `Agent|Task` spawn-window guard disabled outright for
    over-blocking legitimate work."""
    try:
        import json as _json
        import harness_paths
        import hs_run
        import spawn_provenance

        state_dir = harness_paths.state_dir()
        session = os.environ.get("HARNESS_SESSION_ID") or ""

        # `hs_run` owns the ledger format. This used to be a second hand-written
        # parser of it, agreeing with the writer only by coincidence.
        run_id = hs_run.latest_run_id(session=session, domain="cook", verb="prompt",
                                      state_dir=state_dir)
        if not run_id:
            # Names Task explicitly: this is still the "did a real
            # Task(subagent_type=...) spawn happen" question, just answered at
            # an earlier point in the chain. Dropping the word would strip the
            # reader of the one term that says WHAT was not attested — the
            # caveat becomes a shrug.
            return False, ("no record of an `hs-run cook prompt %s` call for this "
                            "session, so a real Task(subagent_type=...) spawn "
                            "cannot be attested against it — treat this `record` "
                            "as an attestation, not proof (no evidence either "
                            "way)" % role)

        # Read the agent name back out of the prompt this module ALREADY hands
        # the model, rather than keeping a second table beside `_ROLE_PROMPTS`.
        # A parallel table is one edit away from disagreeing with the prompt it
        # is supposed to mirror, and the disagreement would show up as a
        # false "not attested" on a run that did everything right.
        m = re.search(r"subagent_type='([^']+)'", _ROLE_PROMPTS.get(role, ""))
        want = m.group(1) if m else "hs:%s" % role
        # `spawn_provenance` owns its own format — this used to reach past it
        # into `_store_path()` and walk the lines here, a fourth hand-written
        # parser agreeing with the writer only by coincidence.
        # TRI-STATE, and the third state is why this is not a bare `if`.
        # `None` means the store could not be READ (a directory at the path, a
        # permission fault) — "I could not look" is not "it did not happen", and
        # collapsing it into False turns a strict check into a wrong one, even in
        # block mode.
        seen = spawn_provenance.has_spawn(session=session, run_id=run_id,
                                          subagent_type=want)
        if seen is None:
            return None, ("the spawn ledger path exists but is not a readable "
                           "file — no evidence either way")
        if seen:
            return True, None
        return False, ("no record of a `%s` Task spawn against this prompt call "
                        "(no evidence either way — the hook may be off, the "
                        "state dir may differ, or the session may have been "
                        "resumed)" % want)
    except Exception:
        # Fail-OPEN even in block mode: "I could not look" is not "it did not
        # happen", and a gate that conflates them is not strict, it is wrong.
        # The THIRD return value says so — `None` means "unreadable", distinct
        # from `False` ("read it, found nothing"), and only `False` may block.
        # Collapsing the two is how a broken store becomes an outage.
        return None, ("could not read the spawn ledger — no evidence either way")


def cmd_record(argv, root) -> dict:
    result = _cmd_record_impl(argv, root)
    if result.get("state") == "recorded":
        attested, note = _attest_spawn(result.get("role"))
        result["spawn_attested"] = attested
        warnings = [w for w in (result.get("warnings") or [])
                    if w is not _HARD_CASE_WARNING]
        if attested is True:
            # The blanket warning is RETIRED on an attested run rather than kept
            # "just in case": a caveat that fires unconditionally trains the
            # reader to skip it, and then it is not there when it matters.
            result["warnings"] = warnings
        else:
            result["warnings"] = warnings + [note]
            # `attested is None` = the ledger could not be READ. Only a clean
            # read that found nothing (`False`) may block; an unreadable store
            # says nothing about whether a spawn happened.
            if (attested is False
                    and (os.environ.get(_ATTEST_MODE_ENV) or "").strip().lower() == "block"):
                result["exit_code"] = EXIT_BROKEN
                result["next_action"] = note
    return hs_run_next_command.finalize(result)


def _cmd_record_impl(argv, root) -> dict:
    """`hs-run cook record <role> --out <file> [--phase <id>]` — beat 2. Reads
    the subagent's report file and advances; it never claims the file's
    content actually came from a real Task-tool spawn (Hard Case #1) — that
    is a transcript fact this CLI has no window into (the
    reasoning about why a CLI cannot see who spawned what).

    Exit tier (D10/L3) depends on the role: `developer`'s own follow-up
    (`cook verify --verdict <PASS|BLOCKED> ...`) needs a MODEL to read the
    report and choose the verdict — EXIT_NEEDS_MODEL. Every other role's
    follow-up is just `hs-run cook next` (pure re-projection, no judgment
    left) — EXIT_NEEDS_STEP."""
    if not argv:
        return hs_run.StepResult(
            state="error",
            next_action="usage: hs-run cook record <role> --out <file> [--phase <id>]",
            artifacts=[],
            warnings=["missing role"],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    role, rest = argv[0], argv[1:]
    if role not in _ROLE_PROMPTS:
        return hs_run.StepResult(
            state="error",
            next_action="unknown role %r (known: %s)"
                            % (role, ", ".join(sorted(_ROLE_PROMPTS))),
            artifacts=[],
            warnings=[],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    ns = hs_run.parse_verb_argv("hs-run cook record %s" % role, rest,
                                options=("out", "phase"))
    out_path = ns.out
    if not out_path:
        return hs_run.StepResult(
            state="error",
            next_action="record needs --out <file>",
            artifacts=[],
            warnings=[],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    if not Path(out_path).is_file():
        return hs_run.StepResult(
            state="error",
            next_action="--out file does not exist: %s" % out_path,
            artifacts=[],
            warnings=[],
            exit_code=EXIT_BROKEN,
        ).as_dict()
    phase = ns.phase
    if role == "developer":
        follow_up = ("hs-run cook verify --phase %s --verdict <PASS|BLOCKED> "
                     "--check <name>:<status> ..." % (phase or "<id>"))
        tier = EXIT_NEEDS_MODEL
        # Null, not the sentence above: it carries `<PASS|BLOCKED>` placeholders
        # a model must resolve by READING the report — that judgment is exactly
        # why this branch is tier 10. Handing back a string with angle brackets
        # in it would be a command that fails at the shell, dressed as one that
        # runs.
        follow_up_cmd = None
    else:
        follow_up = "hs-run cook next"
        tier = EXIT_NEEDS_STEP
        follow_up_cmd = "hs-run cook next"
    return hs_run.StepResult(
        state="recorded",
        next_action=follow_up,
        next_command=follow_up_cmd,
        artifacts=[out_path],
        warnings=[_HARD_CASE_WARNING],
        exit_code=tier,
        extra={"role": role},
    ).as_dict()


# ---------------------------------------------------------------- finalize

def _finalize_projection(plan_dir: Path, root) -> dict:
    """Cook Steps 4-6's projection once every phase has passed: review (6c) ->
    the 6e phase-count grid gate (E27's SECOND path, distinct from
    `preflight`'s macro check) -> close (6g). Steps 4 (test) and 6f
    (docs/git) fold into these same disk facts ("no dedicated
    artifact... folded into verification.json" / "nothing distinguishes
    spawned via Task from written inline") — this function never invents a
    disk check for either, it only warns that they are unverifiable.

    C4: this is the path that ACTUALLY EXECUTES even when
    `write_verification`'s auto-finalize already flipped `plan.md` to
    `completed` before review/grid ever ran — `cmd_next` calls this
    regardless of what the frontmatter already claims (see this module's
    docstring + `cmd_next`), so review-decision and the phase-grid gate are
    enforced on the SAME call that a driver actually makes, not only on a
    `close` call that may never happen."""
    rec, _p = artifact_check._load_artifact(plan_dir, "review-decision")
    if not isinstance(rec, dict) or rec.get("verdict") not in _CLOSEABLE_VERDICTS:
        return hs_run.StepResult(
            state="needs_review",
            next_action="hs-run cook prompt code-reviewer, then record",
            artifacts=[str(plan_dir)],
            warnings=[
                "Step 4 (test) delegation cannot be verified from disk either "
                "way — " + _HARD_CASE_WARNING
            ],
            exit_code=EXIT_NEEDS_MODEL,
        ).as_dict()

    msg, code = grid_emit_guard.require_phase_grids_cli(plan_dir)
    if code != 0:
        return hs_run.StepResult(
            state="needs_phase_grid_gate",
            next_action=msg,
            # The ONE state in this domain where the REMEDY is not expressible
            # as a verbatim command: `grid_engine.py build` refuses hand-typed
            # axis values on purpose (`build_executor_axes: at least one step
            # must be supplied (axis values must come from plan, not
            # hand-typed)`), so the missing micro-grid needs a model to read the
            # phase file first — there is no fixed string this CLI could hand a
            # driver that would produce it. `next_action` (msg) keeps naming
            # every missing phase and the `grid_engine.py emit --phase <id>`
            # recipe for the human.
            #
            # `next_command` names the gate RE-CHECK, but only for the phases
            # this call found missing — NOT a bare `cook next`. Measured: a bare
            # `cook next` here re-derives the identical state, so a driver
            # looping on 11 spins forever (reproduced: 6/6 iterations, byte-
            # identical envelope). Pointing at the guard's own read-only check
            # instead makes the repeat SELF-LIMITING — it exits 2 while the
            # grids are still missing and 0 once they land, so the loop breaks
            # on the gate's own answer rather than on this projection's.
            #
            # The tier stays 11: re-tiering to 10 was measured and rejected — it
            # contradicts this state's already-tested contract in three test
            # files (test_hs_run_cook.py, test_hs_run.py, and the conformance
            # suite's own exit-11 fixture).
            next_command=("python3 harness/scripts/grid_emit_guard.py --plan "
                          "%s --require-phase-grids" % plan_dir),
            artifacts=[str(plan_dir)], warnings=[msg],
            exit_code=EXIT_NEEDS_STEP,
        ).as_dict()

    status = _frontmatter_status(plan_dir)
    if status != "completed":
        return hs_run.StepResult(
            state="needs_close",
            next_action="hs-run cook close --plan %s" % plan_dir,
            next_command="hs-run cook close --plan %s" % plan_dir,
            artifacts=[str(plan_dir)],
            warnings=[
                "Step 6 docs/git delegation cannot be verified from disk either "
                "way — " + _HARD_CASE_WARNING
            ],
            exit_code=EXIT_NEEDS_STEP,
        ).as_dict()
    return hs_run.StepResult(
        state="completed",
        exit_code=EXIT_DONE,
        next_action="nothing left — plan closed",
        artifacts=[str(plan_dir)],
        warnings=_closed_warnings(rec),
    ).as_dict()


def _phase_snapshot_record(plan_dir: Path, phase: str):
    """The phase's own phase-latest marker as a record, or None.

    NOT verification-<phase>.json: that IS the file whose absence puts a phase
    in this branch, so reading it would answer None exactly when the answer
    matters. `write_verification` maintains phase-latest-<phase>.json on every
    run regardless of verdict, precisely so a per-phase verdict survives a
    LATER phase overwriting the single canonical verification.json —
    `derive_plan_completion._phase_latest_regression` reads it for the same
    reason. Returns None on anything unreadable or on a marker whose `phase`
    disagrees with its filename: that disagreement is corruption, and trusting
    the name over the content would let a copied marker answer for a phase it
    never covered.
    """
    p = plan_dir / "artifacts" / ("phase-latest-%s.json" % phase)
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    # The SHARED parser, not a second json.loads: one reader means one answer
    # about what a malformed artifact is, and it already fails soft.
    rec, err = artifact_check._parse_artifact_text(text, p)
    if err or not isinstance(rec, dict) or rec.get("phase") != phase:
        return None
    return rec


_EXIT5_EXPLANATION = (
    "exit code 5 on this scoped run means the declared test set "
    "collected no tests, not that the suite is broken")

# Measured: pytest aborts at USAGE with exit 4 when any named path is absent, and
# runs nothing at all — including the files that do exist. Different code, and a
# different instruction, from exit 5 (files loaded, no tests in them), so a run
# that names a not-yet-written path ships this sentence instead of guessing.
_ABSENT_EXIT_EXPLANATION = (
    "exit code 4 here means a declared path is not on disk yet — pytest stops at "
    "usage and runs nothing, including the tests that DO exist, so write the "
    "missing file first; exit code 5 instead means the set loaded but held no "
    "tests, and neither means the suite is broken")

_NO_TEST_PATHS_WARNING = (
    "defer_suite carried but phase %s declares no file that looks like a "
    "test path in plan-graph.yaml — nothing to scope")

_NOTHING_DECLARED_WARNING = (
    "defer_suite carried but phase %s declares no files at all in "
    "plan-graph.yaml — this node's test scope cannot be derived")

_MALFORMED_DECLARATION_WARNING = (
    "defer_suite carried but phase %s's files_to_create/files_to_modify is "
    "wrong-typed in plan-graph.yaml — the value is there but is not a list, so "
    "no scope could be read from it; write it as a YAML list (one `- path` per "
    "line). Advisory only; this does not block")

_ABSENT_IN_SCOPE_WARNING = (
    "defer_suite scoped phase %s to a set that includes declared test path(s) "
    "not yet on disk (%s) — they are named in the command on purpose, so the "
    "run reports them missing instead of passing without them; write them, or "
    "fix the declared paths in plan-graph.yaml")

_DECLARED_ABSENT_WARNING = (
    "defer_suite carried but phase %s declares at least one test path that "
    "does not exist on disk — create the missing test file(s) or fix the "
    "declared paths in plan-graph.yaml. Advisory only; this does not block")


def _phase_scoped_next_action(plan_dir: Path, phase: str, default_next_action: str):
    """(next_action, extra_warnings) for `needs_implementation` once
    `defer_suite` (phase 2's own carry contract) is folded in — nodes phase
    1's `graph_test_scope.resolve_test_scope` into the ONE state this plan's
    per-phase loop reaches once per phase, so it stops being orphaned
    (`no-orphan-code`).

    `default_next_action` passes through unchanged, with `extra_warnings ==
    []`, whenever: the flag is not carried (no state may leak scoped
    behavior onto an unflagged plan); the resolved status is
    `declared_absent` (phase 4 owns that advisory, not this function); or the
    resolver itself could not derive a scope (`no_graph`/`unknown_node` —
    genuinely unexpected this far into `_cmd_next_impl`, since the SAME
    plan-graph already parsed cleanly a few lines up, but degrading rather
    than trusting an undecidable scope is the honest answer either way).

    Never executes a test runner itself (the engine COMPUTES the
    command and SAYS it; the agent runs it) and never raises (mirrors both
    wrapped resolvers' own no-raise contract)."""
    carry = defer_suite_carry.resolve_defer_suite_carry(plan_dir)
    if not carry["carried"]:
        return default_next_action, []
    scope = graph_test_scope.resolve_test_scope(plan_dir, phase)
    status = scope["status"]
    if status in ("resolved", "declared_absent"):
        # Declared-but-absent paths go in the command TOO. Test-first means the
        # phase's own new test does not exist yet when the scope is read, and
        # dropping it here ran only the OLD tests and reported green — measured,
        # with no warning at all. Naming it makes the runner say "file not found",
        # which IS the first red a test-first loop is supposed to see.
        #
        # `declared_absent` (NOTHING resolved yet) is the same situation with one
        # file less luck — the PURE test-first shape, where the only declared test
        # is the one this phase is about to write. Falling back to the unscoped
        # default there made the flag stop applying at the phase's reddest moment,
        # and made the two shapes behave differently for no reason a reader could
        # act on.
        named = sorted(set(scope["files"]) | set(scope["declared"]))
        cmd = "python3 -m pytest %s -q" % " ".join(shlex.quote(f) for f in named)
        warnings = []
        if scope["declared"]:
            warnings.append(_ABSENT_IN_SCOPE_WARNING
                            % (phase, ", ".join(sorted(scope["declared"]))))
        return (
            "phase %s has no verification recorded — build it red->green, "
            "then run the test set defer_suite scoped to this phase (not "
            "the full suite): %s. %s. Then: hs-run cook prompt developer "
            "--phase %s, hs-run cook record developer --phase %s --out "
            "<file>, hs-run cook verify --phase %s --verdict ... --check ..."
            % (phase, cmd,
               _ABSENT_EXIT_EXPLANATION if scope["declared"]
               else _EXIT5_EXPLANATION,
               phase, phase, phase)
        ), warnings
    if status == "no_test_paths":
        return default_next_action, [_NO_TEST_PATHS_WARNING % phase]
    if status == "nothing_declared":
        return default_next_action, [_NOTHING_DECLARED_WARNING % phase]
    if status == "malformed_declaration":
        return default_next_action, [_MALFORMED_DECLARATION_WARNING % phase]
    return default_next_action, [
        "defer_suite carried but the test-scope resolver could not derive "
        "phase %s's scope (%s: %s) — falling back to the unscoped hint"
        % (phase, status, scope.get("error") or "no node data")
    ]


def _phase_substate(plan_dir: Path, phase: str, graph: dict):
    """(substate, verdict, post_reason) for a phase NOT yet in
    derive_plan_completion's passed_phases:

      - "phase_failed": the canonical verification.json names this phase
        with a non-PASS verdict (red->green ran, verify said no).
      - "phase_needs_reverify": the canonical verification.json names this
        phase with a PASS verdict, but its verification-<phase>.json
        snapshot is missing — completion_state only trusts the snapshot
        (a deleted artifact regresses the projection), so the fix
        is to re-run verify, not to redo the implementation.
      - "phase_needs_post_artifact" (F4): the canonical
        verification.json PASSES for this phase and its snapshot exists, but
        the plan-graph's OWN declared `post:` obligation for this node is
        STILL not satisfied (e.g. an "artifacts/"-prefixed post: entry that
        can never resolve — see `_run_preflight`'s own rejection of that
        authoring mistake — or a second required artifact besides the
        snapshot). Reuses `derive_plan_completion._node_post_satisfied` so
        this branch's reason string is the SAME one completion_state would
        give, never re-derived. Without this branch the code fell through to
        "needs_implementation" — telling the model to redo work that
        already passed, forever (`hs_run_cook.py:583-604`'s own bug).
      - "needs_implementation": no verification recorded for this phase at
        all yet (the common case for a phase not yet started)."""
    snap = plan_dir / "artifacts" / ("verification-%s.json" % phase)
    rec, _p = artifact_check._load_artifact(plan_dir, "verification")
    if not (isinstance(rec, dict) and rec.get("phase") == phase):
        # The canonical record names exactly ONE phase — whichever verified
        # last — so asking it about an earlier phase always answers "not this
        # one" and drops through to needs_implementation: redo work that
        # already passed. The per-phase snapshot carries its own phase +
        # verdict, so fall back to it. Missing snapshot AND no canonical
        # mention is the genuine "never verified" case and still falls
        # through. Which phase verified last is not a property of the phase.
        rec = _phase_snapshot_record(plan_dir, phase)
    if isinstance(rec, dict) and rec.get("phase") == phase:
        verdict = rec.get("verdict")
        if verdict not in ("PASS", "PASS_WITH_RISK"):
            return "phase_failed", verdict, None
        if not snap.is_file():
            return "phase_needs_reverify", verdict, None
        post = plan_graph.node_artifacts(graph, phase)["post"]
        why = derive_plan_completion._node_post_satisfied(
            plan_dir / "artifacts", post, phase)
        if why:
            return "phase_needs_post_artifact", verdict, why
    return "needs_implementation", None, None


# The `stage` a debt-payment verify must carry. Any other value — notably the
# per-phase default — is a scoped run and does not settle the debt.
DEBT_STAGE = "deferred-suite"

# Built from DEBT_STAGE rather than repeating it: the sentence tells the agent the
# exact command, and a literal drifting from the value the gate compares against
# would print instructions that do not settle the debt they describe.
_PENDING_DEBT_ITEM = (
    "the deferred full suite has not been verified yet for this plan — run "
    "it once and record it before cook close, stamped as the run it was: "
    "hs-run cook verify --phase <last-node> --stage %s --verdict "
    "PASS --check regression:PASS" % DEBT_STAGE)


def _suite_debt_unpaid(plan_dir: Path) -> bool:
    """The ONE signal authorized for "has the defer_suite debt been
    paid" — the plan's own canonical verification artifact carries a
    closeable verdict, exactly the same read `_finalize_projection`'s
    review-decision gate above already does for a different artifact kind.
    No test count, no junit — one more field on a record that already carries
    it. The stage says WHICH run it was, not how much it ran, so a scoped run
    deliberately stamped as the debt run still reads as paid: an agent who
    forgets is caught, one who misrepresents is not (named in
    `deferred-suite.md`).

    Shared by design: phase 5's own `cook close` gate reads this SAME
    function, so `pending` here and that gate can never disagree about
    whether the debt is paid — two readers of one fact instead of two
    independently-derived opinions of it.

    Read-only, no subprocess: `artifact_check._load_artifact` parses the
    file already on disk. Missing/unreadable reads as unpaid — no evidence
    means no consent this happened.

    The `stage` is load-bearing, and reading the verdict ALONE was measured
    wrong: every phase's scoped verify overwrites this same canonical file, so
    the last phase silently paid the debt with a handful of tests and close
    returned 0 with the full suite never run. `stage` already exists on the
    record and is descriptive free text, so requiring the debt-payment value
    distinguishes the two runs without counting tests, reading junit, or
    inventing an artifact — the run says which run it was."""
    rec, _p = artifact_check._load_artifact(Path(plan_dir), "verification")
    if not isinstance(rec, dict):
        return True
    return not (rec.get("verdict") in _CLOSEABLE_VERDICTS
                and str(rec.get("stage") or "").strip() == DEBT_STAGE)


def _pending_for_debt(plan_dir: Path) -> list:
    """`pending[]`'s own content for the defer_suite debt — derived from disk on
    EVERY call (never a stored cursor, matching `Envelope.pending`'s own
    contract), so a call made right after the debt is paid regresses to `[]`
    exactly as honestly as the disk does. Absent the flag: always `[]` — a
    plan that never opted in never rides this channel (the
    default-is-invariant, restated for a field the reminder owns).

    Exactly one item, never a phase name (`verification-<phase>.json` is
    first-wins and every defer_suite snapshot is small by design, so "find
    the snapshot with a matching total" cannot answer this question either
    way — see `deferred-suite.md`)."""
    if not defer_suite_carry.resolve_defer_suite_carry(plan_dir)["carried"]:
        return []
    if _suite_debt_unpaid(plan_dir):
        return [_PENDING_DEBT_ITEM]
    return []


def _attach_route_flags(plan_dir: Path, result: dict) -> None:
    """cook's own answer to "which conditional `when_flag:` blocks apply" —
    mirrors `hs_run_plan._attach_route_flags` in shape (attach only when at
    least one flag is on; ABSENT, never empty, when none are — the dispatcher
    pops this key generically at `hs_run.py:2313`, no domain-specific change
    needed here). Reuses `defer_suite_carry.resolve_defer_suite_carry` rather
    than re-parsing `plan.md` frontmatter a second time — that resolver
    already has the exact fail-closed, never-raise contract this needs
    (unreadable frontmatter reads as not-carried, never an exception)."""
    if defer_suite_carry.resolve_defer_suite_carry(plan_dir)["carried"]:
        result.setdefault("route_flags", ["defer_suite"])


def cmd_next(argv, root) -> dict:
    return hs_run_next_command.finalize(_cmd_next_impl(argv, root))


def _cmd_next_impl(argv, root) -> dict:
    """`hs-run cook next [--plan <dir>] [--phase <id>]` — the per-phase
    projection. Every call re-reads disk fresh; nothing here is
    an authoritative progress file. `--phase` forces the phase inspected
    (mainly useful for `hs-run cook verify`'s own follow-up); absent, the
    first not-yet-passed phase (in `_phase_order`'s deterministic order) is
    used — validated against the plan-graph's own node list first (F15): a typo'd/nonexistent `--phase` is EXIT_BROKEN, never handed
    to the state machine as if it were a real unstarted node.

    C0/F10: `status:` frontmatter is corroboration ONLY, never
    authoritative — this used to read `status == "completed"` and
    short-circuit before any artifact check ran (a progress file the
    projection contract forbids). Now: derive the answer from plan-graph + completion_state
    every time; a `completed`/`in_progress` frontmatter that DISAGREES with
    what the artifacts show is a first-class `state_conflict` at
    EXIT_BROKEN, naming both sides — never a silent "done"."""
    root = Path(root)
    ns = hs_run.parse_verb_argv("hs-run cook next", argv,
                                options=("plan", "phase"))
    explicit_plan, forced_phase = ns.plan, ns.phase

    dirs = _plan_dirs(root)
    if not dirs:
        return hs_run.StepResult(
            state="no_plan",
            exit_code=EXIT_DONE,
            next_action="no plan exists to cook yet — create + approve one "
                             "first (hs-run plan next), then cook it",
            artifacts=[],
            warnings=[],
            extra={"summary_numbers": "0 plans found"},
        ).as_dict()

    plan_dir, miss = _resolve_plan_dir_verbose(root, explicit=explicit_plan)
    if plan_dir is None:
        # R15 / conformance property 7 (D12): a caller that
        # EXPLICITLY named a target — a `--plan` that does not exist, or
        # an explicitly-set HARNESS_ACTIVE_PLAN that resolve_active_plan's
        # own fail-closed contract rejected — must never read as an idle
        # "nothing to do yet" (EXIT_DONE), even while a DIFFERENT real
        # plan sits on disk. That is a genuinely blocking situation (the
        # named target failed to resolve), not an ambiguous "no plan
        # exists ANYWHERE yet" one — mirrors the plan domain's own
        # identical fix for `--plan <bogus>` (hs_run_plan.py's own
        # C0-MOVED note on this exact branch). `ambiguous_approved` /
        # `no_candidates` are deliberately NOT included here: those stay
        # at EXIT_DONE to match `test_property6_ambiguous_ordering_
        # same_exit_code_across_domains`'s cross-domain parity
        # requirement with the plan domain's own `multiple_plans`
        # (exit 0).
        #
        # Decided BEFORE the result is built rather than written over it
        # afterwards: the value object is frozen, and a result that a later
        # line can still edit is not a result, it is a scratchpad.
        named_target_failed = bool(
            miss and miss.get("kind") in ("active_plan_rejected", "explicit_not_found"))
        return hs_run.StepResult(
            state="not_approved",
            exit_code=EXIT_BROKEN if named_target_failed else EXIT_DONE,
            next_action=_not_approved_message(miss, dirs),
            artifacts=[str(d) for d in dirs], warnings=[],
            extra={"summary_numbers": "%d plan(s) found" % len(dirs)},
        ).as_dict()

    result = _cmd_next_for_plan(plan_dir, forced_phase, root)
    # `pending`/`route_flags` attach HERE, once, to every state
    # `_cmd_next_for_plan` can return — mirroring `hs_run_plan._project`'s own
    # `result.setdefault(...)` pattern rather than requiring each of that
    # function's dozen early returns to remember it separately. Derived from
    # disk fresh on this call, never a stored cursor (`Envelope.pending`'s own
    # contract) — flag off leaves both untouched (`route_flags` absent,
    # `pending` `[]`, matching the default-is-invariant).
    _attach_route_flags(plan_dir, result)
    result.setdefault("pending", _pending_for_debt(plan_dir))
    return result


def _cmd_next_for_plan(plan_dir: Path, forced_phase, root) -> dict:
    """`_cmd_next_impl`'s per-phase projection body, once a `plan_dir` is
    resolved — split out so `pending`/`route_flags` can attach centrally at
    the ONE call site above instead of at each of this function's early
    returns."""
    status = _frontmatter_status(plan_dir)
    if status == "approved":
        pf = _run_preflight(plan_dir, root=root)
        if pf["blocked"]:
            return hs_run.StepResult(
                state="preflight_blocked",
                next_action="fix before opening: %s" % "; ".join(pf["reasons"]),
                artifacts=[str(plan_dir)],
                warnings=pf["reasons"],
                exit_code=EXIT_BROKEN,
            ).as_dict()
        return hs_run.StepResult(
            state="needs_open",
            next_action="hs-run cook open --plan %s" % plan_dir,
            next_command="hs-run cook open --plan %s" % plan_dir,
            artifacts=[str(plan_dir)],
            warnings=[],
            exit_code=EXIT_NEEDS_STEP,
        ).as_dict()

    if status not in ("in_progress", "completed"):
        return hs_run.StepResult(
            state="not_startable",
            next_action="plan status is %r — cook cannot act on it" % status,
            artifacts=[str(plan_dir)],
            warnings=[],
            exit_code=EXIT_BROKEN,
        ).as_dict()

    # From here `status` is corroboration only. The real answer is
    # derived from the plan-graph + completion_state, never cached from
    # frontmatter — a disagreement is a first-class state_conflict, not a
    # silently-trusted "done".
    graph = plan_graph.parse_phase_graph(plan_dir)
    if graph.get("error"):
        if status == "completed":
            return hs_run.StepResult(
                state="state_conflict",
                next_action="frontmatter says completed but plan-graph.yaml is "
                    "unreadable (%s) — cannot corroborate; refusing to trust "
                    "either side silently" % graph["error"],
                artifacts=[str(plan_dir)],
                warnings=["frontmatter: status=completed",
                             "artifacts: %s" % graph["error"]],
                exit_code=EXIT_BROKEN,
            ).as_dict()
        return hs_run.StepResult(
            state="no_plan_graph",
            next_action="plan-graph.yaml problem: %s" % graph["error"],
            artifacts=[str(plan_dir)],
            warnings=[graph["error"]],
            exit_code=EXIT_BROKEN,
        ).as_dict()

    comp = derive_plan_completion.completion_state(plan_dir, root=root)
    if not comp["complete"]:
        if status == "completed":
            return hs_run.StepResult(
                state="state_conflict",
                next_action="frontmatter says completed but artifacts show %s — the "
                    "two disagree, refusing to report either as authoritative"
                    % comp["reason"],
                artifacts=[str(plan_dir)],
                warnings=["frontmatter: status=completed",
                             "artifacts: %s" % comp["reason"]],
                exit_code=EXIT_BROKEN,
            ).as_dict()
        order = _phase_order(graph)
        all_nodes = plan_graph._all_nodes(graph)
        if forced_phase is not None and forced_phase not in all_nodes:
            return hs_run.StepResult(
                state="unknown_phase",
                next_action="--phase %r is not a node in this plan's "
                                 "plan-graph.yaml (known: %s)"
                                 % (forced_phase,
                                    ", ".join(sorted(all_nodes)) or "(none)"),
                artifacts=[str(plan_dir)],
                warnings=[],
                exit_code=EXIT_BROKEN,
            ).as_dict()
        phase = forced_phase or next(
            (n for n in order if n not in comp["passed_phases"]), None)
        if phase is None:
            return hs_run.StepResult(
                state="no_phase_resolved",
                next_action="plan-graph declares no phases",
                artifacts=[str(plan_dir)],
                warnings=[],
                exit_code=EXIT_BROKEN,
            ).as_dict()
        substate, verdict, post_why = _phase_substate(plan_dir, phase, graph)
        numbers = "%d/%d phase(s) passed" % (len(comp["passed_phases"]), comp["n_total"])
        if substate == "phase_failed":
            return hs_run.StepResult(
                state="phase_failed",
                next_action="phase %s verification verdict is %s — fix and "
                                 "re-run: hs-run cook verify --phase %s --verdict "
                                 "..." % (phase, verdict, phase),
                artifacts=[str(plan_dir / "artifacts" / "verification.json")],
                warnings=[],
                exit_code=EXIT_NEEDS_MODEL,
                extra={"phase": phase, "verdict": verdict, "summary_numbers": numbers},
            ).as_dict()
        if substate == "phase_needs_reverify":
            return hs_run.StepResult(
                state="phase_needs_reverify",
                next_action=(
                    "verification-%s.json snapshot is missing though the "
                    "canonical verification still shows verdict %s for phase "
                    "%s — re-run hs-run cook verify --phase %s --verdict %s "
                    "--check <name>:<status> ... to regenerate it"
                    % (phase, verdict, phase, phase, verdict)),
                # Both the phase AND the verdict are already KNOWN here (the
                # canonical verification still names them) — this state is a
                # missing SNAPSHOT of a decision already made, not a new
                # decision, which is why it is tier 11 and not 10. The `--check`
                # placeholders are dropped rather than passed through: measured,
                # `write_verification` makes `--check` optional (`action=
                # "append", default=[]`), so this shorter form runs verbatim,
                # whereas the sentence's `<name>:<status> ...` would not.
                next_command=("hs-run cook verify --plan %s --phase %s "
                              "--verdict %s" % (plan_dir, phase, verdict)),
                artifacts=[str(plan_dir / "artifacts")],
                warnings=[],
                extra={"phase": phase, "verdict": verdict,
                       "summary_numbers": numbers},
                exit_code=EXIT_NEEDS_STEP,
            ).as_dict()
        if substate == "phase_needs_post_artifact":
            return hs_run.StepResult(
                state="phase_needs_post_artifact",
                next_action="phase %s verification verdict is %s (already "
                    "PASS-equivalent) but its plan-graph.yaml 'post:' "
                    "obligation is not satisfied: %s — fix the post: entry "
                    "for this node in plan-graph.yaml (a bare filename under "
                    "artifacts/, never prefixed with 'artifacts/' itself) or "
                    "produce the artifact it names"
                    % (phase, verdict, post_why),
                artifacts=[str(plan_dir / "artifacts")],
                warnings=[post_why],
                exit_code=EXIT_BROKEN,
                extra={"phase": phase, "verdict": verdict, "summary_numbers": numbers},
            ).as_dict()
        # `needs_implementation` is what `_phase_substate` returns for a phase
        # with no verification recorded at all — a phase not yet started. It had
        # no branch here, so it fell into `phase_needs_work` below, whose own
        # registry row says "The phase's verification did not pass": one name
        # covering both "never built" and "built and rejected".
        #
        # The cost was not cosmetic. `cook.yaml` routes per-phase-tdd.md and
        # subagent-patterns.md — 185 lines carrying the delegate-by-default
        # mandate — at `needs_implementation`, and the loop never emitted it, so
        # those drawers were reachable only through `status`, the read-only verb.
        # That is why cook/SKILL.md still carries 14 lines restating the mandate:
        # prose has to repeat what routing was built to deliver.
        if substate == "needs_implementation":
            default_next_action = (
                "phase %s has no verification recorded — build it "
                "red->green, then: hs-run cook prompt developer "
                "--phase %s, hs-run cook record developer --phase %s "
                "--out <file>, hs-run cook verify --phase %s "
                "--verdict ... --check ..."
                % (phase, phase, phase, phase))
            next_action, extra_warnings = _phase_scoped_next_action(
                plan_dir, phase, default_next_action)
            return hs_run.StepResult(
                state="needs_implementation",
                next_action=next_action,
                artifacts=[str(plan_dir)],
                warnings=extra_warnings,
                exit_code=EXIT_NEEDS_MODEL,
                extra={"phase": phase, "summary_numbers": numbers},
            ).as_dict()
        return hs_run.StepResult(
            state="phase_needs_work",
            next_action="hs-run cook prompt developer --phase %s, then "
                             "hs-run cook record developer --phase %s --out "
                             "<file>, then hs-run cook verify --phase %s "
                             "--verdict ... --check ..."
                             % (phase, phase, phase),
            artifacts=[str(plan_dir)],
            warnings=[],
            exit_code=EXIT_NEEDS_MODEL,
            extra={"phase": phase, "summary_numbers": numbers},
        ).as_dict()

    return _finalize_projection(plan_dir, root)


# ------------------------------------------------------------------ status

def cmd_status(argv, root) -> dict:
    return hs_run_next_command.finalize(_cmd_status_impl(argv, root))


def _cmd_status_impl(argv, root) -> dict:
    """`hs-run cook status [--plan <dir>]` — a human-oriented, whole-plan
    summary (every phase's pass/fail, not just the current one). Pure
    projection, same posture as `next`: always EXIT_DONE (`status` is the ONE verb that always reports 0, read-only, reports
    only), UNLESS this call itself cannot give a trustworthy single answer —
    a `state_conflict` (frontmatter disagrees with derived artifacts, C0) is
    the one pre-existing exception, at EXIT_BROKEN.

    R18 fix: with two approved-and-unopened plans on disk and no
    `--plan` given, this used to report `state: "no_plan"` while its OWN
    `next_action` said "2 plan(s) are approved-and-unopened at once" — a
    direct self-contradiction. Named honestly now (`ambiguous_approved`).
    The EXIT CODE is deliberately left at EXIT_DONE, unlike the R15 fix in
    `cmd_next` — the domain-agnostic conformance suite (D12, the SSOT for
    this contract) asserts `status` stays exit 0 even for an explicit
    mistyped `--plan` (`test_property7_status_is_exit_zero_on_mistyped_
    plan`, parametrized across every domain, no carve-out offered for an
    ambiguous or rejected target either); the redteam report's own suggested
    fix for R18 ("trạng thái CHẶN không được trả 0") would have violated
    that already-built, concurrently-owned property test, so the exit-code
    change was dropped — see this run's report for the explicit note."""
    root = Path(root)
    ns = hs_run.parse_verb_argv("hs-run cook status", argv, options=("plan",))
    plan_dir, miss = _resolve_plan_dir_verbose(root, explicit=ns.plan)
    if plan_dir is None:
        if miss and miss.get("kind") == "ambiguous_approved":
            return hs_run.StepResult(
                state="ambiguous_approved",
                next_action=_not_approved_message(miss, _plan_dirs(root)),
                artifacts=[str(d) for d in miss["candidates"]], warnings=[],
                # Property 7: this is `status`, the one always-0 verb. It names
                # the ambiguity in the body and leaves the choice — and the
                # rung — to whoever acts on it.
                exit_code=EXIT_DONE,
            ).as_dict()
        return hs_run.StepResult(
            state="no_plan",
            exit_code=EXIT_DONE,
            next_action=_not_approved_message(miss, _plan_dirs(root)),
            artifacts=[],
            warnings=[],
        ).as_dict()
    graph = plan_graph.parse_phase_graph(plan_dir)
    status = _frontmatter_status(plan_dir) or "unknown"
    if graph.get("error"):
        if status == "completed":
            return hs_run.StepResult(
                state="state_conflict",
                next_action="frontmatter says completed but plan-graph.yaml is "
                    "unreadable (%s)" % graph["error"],
                artifacts=[str(plan_dir)],
                warnings=["frontmatter: status=completed",
                             "artifacts: %s" % graph["error"]],
                exit_code=EXIT_BROKEN,
            ).as_dict()
        return hs_run.StepResult(
            state="no_plan_graph",
            next_action="plan-graph.yaml problem: %s" % graph["error"],
            artifacts=[str(plan_dir)], warnings=[graph["error"]],
            # EXIT_BROKEN, matching the sibling emitter further up. Both reach
            # this line from the same fact — plan-graph.yaml cannot be parsed —
            # and an unreadable graph is exactly as unusable whichever branch
            # noticed it. The rung split here was justified in a comment rather
            # than by a difference in the tree, which is how one word ends up
            # telling two drivers two different things about one broken file.
            exit_code=EXIT_BROKEN,
        ).as_dict()
    comp = derive_plan_completion.completion_state(plan_dir, root=root)
    order = _phase_order(graph)
    phases = [{"phase": n, "passed": n in comp["passed_phases"]} for n in order]
    numbers = "%d/%d phase(s) passed" % (len(comp["passed_phases"]), comp["n_total"])
    if status == "completed" and not comp["complete"]:
        return hs_run.StepResult(
            state="state_conflict",
            next_action="frontmatter says completed but artifacts show %s"
                             % comp["reason"],
            artifacts=[str(plan_dir)],
            warnings=["frontmatter: status=completed",
                         "artifacts: %s" % comp["reason"]],
            exit_code=EXIT_BROKEN,
            extra={"phases": phases, "summary_numbers": numbers},
        ).as_dict()

    if comp["complete"]:
        # R9: every phase passing does NOT mean the plan is
        # REALLY done — review-decision + the phase-grid gate must also
        # clear, exactly what `next`'s own `_finalize_projection` already
        # enforces (C4/F1). Before this fix `status` trusted whatever
        # `status:` said the instant `comp["complete"]` agreed with it,
        # without ever checking those two gates itself — so on the IDENTICAL
        # disk state (e.g. after write_verification's own premature
        # auto-finalize flip, R1) `cook next` could honestly report
        # `needs_review` (rc 10) while `cook status` said `completed` (rc
        # 0): one plan, two contradicting answers. `status`'s own posture is
        # unchanged (always exit 0, read-only) — only the STATE
        # NAME it reports is now derived from the SAME finalize projection
        # `next` uses, never a frontmatter shortcut.
        proj = _finalize_projection(plan_dir, root)
        return hs_run.StepResult(
            state=proj["state"],
            next_action=proj["next_action"],
            # NOT the projection's rung. `next` and `status` read the same disk
            # and agree on the STATE; they deliberately disagree on the exit,
            # because Property 7 makes `status` the one always-0 verb — it
            # reports what is owed in the body and never escalates its own exit
            # for someone else's unfinished work. Carrying the rung across here
            # was measured and reverted: it turned a read-only report into a
            # failed action for every caller that branches on the number.
            exit_code=EXIT_DONE,
            artifacts=[str(plan_dir)],
            warnings=proj.get("warnings", []),
            extra={"phases": phases, "summary_numbers": numbers},
        ).as_dict()

    # The other half of the fix above. That branch stopped trusting `status:` when
    # the phases agreed it was complete; this one still returned the frontmatter
    # value verbatim whenever they did not — and `plan_status.CANONICAL_STATUSES`
    # is a DIFFERENT vocabulary from `State`. Two of its five values (`pending`,
    # `in_progress`) are not `State` members at all, so `cook status` shipped
    # states that the state map, the routing table and the never-done set could
    # not see, while every coverage gate called the domain fully covered. A
    # partly-lifted shortcut reads as deliberate, which is why the second half
    # outlived the first.
    #
    # `phases_remain`, not the `needs_implementation` this branch used to carry.
    # The frontmatter value is not lost — it rides `extra` as `plan_status` for a
    # caller that genuinely wants the plan's own label rather than the verb's
    # reading of the tree. It is a SEPARATE key on purpose: the two answer
    # different questions, and letting them share the `state` slot is what made
    # them look interchangeable.
    #
    # Why the word had to change: `next` now emits `needs_implementation` for the
    # phase it resolved, at rung 10, since that is the state the registry routes
    # the delegate mandate at. This branch answers a WIDER question — "does this
    # plan still have unfinished phases", about the whole plan, at rung 0 — and
    # one word riding both 0 and 10 tells two drivers two different things about
    # one tree. Same split the six renames earlier in this migration made: the
    # verb that acts on a phase keeps the specific word, the whole-plan
    # projection takes a word that says what it actually measured.
    return hs_run.StepResult(
        state="phases_remain",
        next_action="hs-run cook next --plan %s" % plan_dir,
        # Property 7 again: the next_action names work that is still owed, and
        # `status` says so in the body while still leaving on 0. The rung is the
        # verb's own health, not the plan's.
        exit_code=EXIT_DONE,
        artifacts=[str(plan_dir)], warnings=[],
        extra={"phases": phases, "summary_numbers": numbers,
               "plan_status": status},
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
        % (Path(__file__).name, 'cook'))
    raise SystemExit(EXIT_BROKEN)
