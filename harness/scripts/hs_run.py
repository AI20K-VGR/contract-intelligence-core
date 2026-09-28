#!/usr/bin/env python3
"""hs_run.py — `hs-run <domain> <verb>`: the deterministic step-sequence CLI.

Sibling to hs-cli (`harness/scripts/hs_cli.py`), never a replacement for it — hs-cli
stays untouched (survival
invariant #1). Where hs-cli is operator-facing (install/health/config verbs), hs-run
owns the deterministic parts of the plan/cook WORKFLOW: it resolves "what step comes
next" by reading a registry (base file `harness/data/hs-run-registry.yaml` PLUS every
fragment under `harness/data/hs-run-registry.d/*.yaml` — see "Registry" below) and
calling the registered Python callable — it never encodes a domain/verb in an if/else
chain, so a third domain is a data-file row, not a code edit (survival invariant #3).

Registry (D7): concurrent build phases (P1 owns `plan`'s verbs, P2 owns
`cook`'s) must never write the SAME file at once — a monolithic
registry would force exactly that collision. So the registry is base-file + drop-in
directory: each domain gets its own `hs-run-registry.d/<domain>.yaml` fragment, merged
at load time in sorted-filename order (never directory iteration order — that would
make the merge's meaning depend on filesystem happenstance). A `(domain, verb)` key
declared in two sources is a hard error (`RegistryConflictError`, mapped to exit 2
naming both files) — silent last-wins would let a typo'd filename silently hijack a
verb. A malformed fragment fails the same way (`RegistryParseError`), never silently
skipped (a skipped fragment makes a verb vanish with a misleading "unknown verb"
error, not a "this file is broken" one). `HARNESS_HS_RUN_REGISTRY` is a SEPARATE,
pre-existing single-file override that REPLACES the whole base+fragments pipeline —
see `load_registry()`'s docstring for why that, not a merge, is what makes test
isolation actually isolating.

Three-tier output contract (D10 — the four-tier ladder), all three on
every invocation:

  1. exit code   — 0 done · 10 a MODEL turn is required · 11 one more DETERMINISTIC
                   step remains (run next_action, call again) · 2 broken. hs-cli has
                   no such split (its 12 verbs are each a complete, single operator
                   action); tiers 10/11 are NEW here because a plan/cook step can
                   genuinely be "I have projected the next action, but it can only be
                   carried out by a model turn" (the two-beat pattern: `prompt`
                   -> spawn -> `record`) OR "there is more purely mechanical work left,
                   go run it and re-call me" (D10 — added after the red-team review
                   found 10 was being asked to mean both at once). `main()` rejects any
                   OTHER value a verb tries to return (non-int, bool, or an int outside
                   {0, 10, 11, 2}) — forced to EXIT_BROKEN with a loud warning, never
                   silently passed through as a bare, undocumented exit code.
  2. stdout JSON — exactly one line, `{schema, state, next_action, next_command,
                   artifacts, warnings, registry_sources, root, root_source, ...}`.
                   `next_action` is the sentence a HUMAN reads; `next_command` is the
                   string a DRIVER runs verbatim, or `null` when the next step is not
                   a command at all (one field serving both
                   readers served neither). `main()` enforces the pairing: exit 11
                   demands a real `next_command`, exit 10 forbids a non-null one; a
                   violation is forced to EXIT_BROKEN with a named warning, the same
                   way an out-of-ladder exit code already is. This is the ONLY thing
                   written to stdout. A verb that crashes still gets a valid JSON
                   envelope (state="error") — a downstream
                   `json.loads(subprocess.run(...).stdout)` must never raise on this CLI,
                   full stop. `registry_sources` (which registry files were actually
                   loaded) and `root`/`root_source` (which project directory this
                   invocation resolved to, and how) are added by `main()` itself to
                   EVERY envelope, success or error ("the envelope must
                   self-declare its sources"; an `artifacts: []` with no hint of where
                   the CLI looked, or which registry file it trusted, is an answer
                   nobody can verify).
  3. human line  — `state=... · <numbers> · <next thing to do> · <command to re-run>`,
                   written to STDERR, never stdout. Decision + why (documented once,
                   here, not per call site): mixing a prose line into stdout would force
                   every machine consumer to guess where the JSON ends and prose begins
                   (no such boundary exists in a single text stream without inventing
                   one) — stderr is the conventional side-channel for exactly this
                   (mirrors hs-cli's own error-vs-result split, e.g. cmd_doctor). Tests
                   for this file assert stdout parses as ONE JSON blob and the human
                   line is independently present on stderr.

`next` is a PROJECTION, never a progress file: every verb here derives its
answer by reading on-disk artifacts fresh, each call. Nothing in this module persists
an authoritative "step N done" record — a cache of a prior read is, at most, a cache,
never the source of truth.

Root resolution (fixed after the red-team review): `CLAUDE_PROJECT_DIR`
wins when it names an existing directory; a SET-BUT-STALE value (deleted/rotated
project, a typo) is a hard error, never a silent fall-through to CWD (that silent
fallback is exactly what produced the report's reproduced bugs: "no plan exists yet"
from a subdirectory that has one two levels up, `scaffold` building a second `plans/`
tree under that subdirectory, and a stale env value materializing a whole plan tree at
a dead path). Absent, `_walk_up_for_root()` walks up from CWD looking for a `plans/`
dir or a `.git` entry — never `harness_paths.project_root()` (goal D6: its
global-install branch falls back to the SHARED bin root, not the caller's project).
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import sys
from enum import IntEnum, StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parents[1]  # harness/scripts -> harness -> repo root (mirrors hs_cli.py)
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

# Imported AFTER the sys.path insert above (harness/ carries no __init__.py by design,
# so a sibling in scripts/ is reachable only once that entry is in place). Not lazy:
# the registry is read on every invocation of this CLI, so there is no cold path to
# protect. This module used to subclass yaml.SafeLoader here to make a repeated
# mapping key raise — ruamel's safe loader raises DuplicateKeyError for that on its
# own, at every nesting depth, so the subclass is gone.
import harness_root  # noqa: E402
import yaml_io  # noqa: E402
from ruamel.yaml.constructor import DuplicateKeyError  # noqa: E402

# Re-bound (not re-defined) so `except ProjectRootError` below still resolves —
# see the docstring at this module's old class-definition site (now removed;
# the class itself lives in harness_root.py, this module's shared sibling).
ProjectRootError = harness_root.ProjectRootError

_REGISTRY_NAME = "hs-run-registry.yaml"
_REGISTRY_DIR_NAME = "hs-run-registry.d"
_SCHEMA = "hs-run/1"

# ------------------------------------------------------------------- run identity
#
# `run_id` exists to turn one specific "we cannot check that" into a check. Today
# `hs_run_cook.py` ships this admission verbatim:
#
#     cannot verify from disk that this step actually went through a real
#     Task(subagent_type=...) spawn rather than the model doing the work inline
#     and reporting success — that is a session-transcript fact, not a disk fact
#
# So `record` is an attestation, and the prose rule "Task-tool calls = 0 =>
# INCOMPLETE" is a transcript check nothing enforces. The chain that closes it:
# this CLI stamps an id per invocation and appends it to a per-session ledger; a
# PreToolUse(Agent|Task) hook tags each spawn with the session's most recent id;
# `record` then asks whether a spawn carrying the matching `prompt` call's id
# exists. Transcript fact becomes disk fact.
#
# TWO PROPERTIES THIS FILE OWNS, both load-bearing for everything downstream:
#
# 1. EVERY envelope carries it — help and error paths included. A run that ended
#    in an error still RAN, and a spawn following it is still attributable.
#    Stamping only the happy path would make "the CLI errored" and "nothing was
#    recorded" indistinguishable to the reader.
#
# 2. Bookkeeping NEVER gates the verb. A verb dying because it could not mint an
#    id or write a line would be a self-inflicted outage, and the harness has
#    already paid for that lesson once: the `Agent|Task` spawn-window guard was
#    disabled outright after it over-blocked legitimate work. `run_id: null` means
#    "not provable" — a DIFFERENT claim from "no spawn happened", and the reader
#    downstream must keep those apart.
_RUN_LEDGER_REL = ("hs-run", "runs.jsonl")
# Bounded like the spawn ledger: a maintenance rewrite, never a per-record
# read-modify-write of a count.
_RUN_LEDGER_MAX_LINES = 2000
# How far past the cap the ledger may drift before a trim runs. This is what
# turns "occasional whole-file rewrite" from a claim into a fact: without it the
# trim fires on every append once the cap is reached, which is per-record
# bookkeeping over a 2000-line file. With it, one rewrite per 200 appends.
_RUN_LEDGER_SLACK = 200


def run_ledger_path(state_dir=None):
    """Where the per-session run ledger lives.

    Public because the hook and the `record` verbs read the same file — a second
    module hard-coding this path is how two readers end up disagreeing about
    where the truth is."""
    if state_dir is None:
        import harness_paths
        state_dir = harness_paths.state_dir()
    return Path(state_dir).joinpath(*_RUN_LEDGER_REL)


def _resolve_session():
    """The live session id, or None. Order copied from `emit_disabled_demand`
    (`$HARNESS_SESSION_ID` then the newest `state/sessions/<id>.json` by mtime)
    rather than reinvented — a second resolution order would silently disagree
    with the first on exactly the sessions that matter."""
    try:
        import os as _os
        sid = _os.environ.get("HARNESS_SESSION_ID")
        if sid:
            return sid
        import harness_paths
        files = [p for p in (harness_paths.state_dir() / "sessions").glob("*.json")
                 if p.is_file()]
        if not files:
            return None
        return max(files, key=lambda p: p.stat().st_mtime).stem or None
    except Exception:
        return None


def _mint_run_id():
    """A fresh id per invocation, or None if even this fails.

    Not derived from time+pid: two invocations inside the same clock tick would
    collide, and a shared id lets a spawn be credited to a call that never asked
    for it — the exact laundering the mechanism exists to prevent."""
    try:
        import uuid
        return uuid.uuid4().hex[:16]
    except Exception:
        return None


def _ledger_actor():
    """Attribution for one ledger line, or "" when identity cannot be resolved.

    Delegates to `hook_runtime.resolve_actor()` — the ONE resolver every other
    machine-written store in this repo stamps with. A private scheme here would
    attribute the same run two different ways depending on which store you read,
    and the whole point of the field is that those answers agree.

    Fail-open to "": this is telemetry. An identity lookup that raises costs the
    field, never the line."""
    try:
        import hook_runtime
        return str(hook_runtime.resolve_actor() or "")
    except Exception:  # noqa: BLE001 — attribution never gates the write
        return ""


def _trim_run_ledger(p: Path) -> None:
    """Bound the ledger, WITHOUT a per-append rewrite of the whole file.

    The previous version read and rewrote the file whenever it exceeded the cap,
    and its docstring called that "an occasional whole-file rewrite ... not
    per-record bookkeeping". At steady state that was false: once the file
    reached the cap, EVERY subsequent append rewrote all of it. Measured cost was
    not just throughput — two threads appending 120 records across the boundary
    lost 23 of them, because a line appended between the read and the write is
    outside the text being written back. The old docstring named that hazard
    ("would drop a concurrent session's record with nothing noticing") one line
    above the code that caused it.

    Two changes make the claim true. HYSTERESIS: the file is allowed past the cap
    up to a slack margin, so a rewrite happens once per `_RUN_LEDGER_SLACK`
    appends rather than once per append. And the rewrite happens INSIDE the same
    exclusive lock the append takes, so a concurrent append is serialized against
    it instead of racing it.

    The NEWEST lines are kept. This store answers "did a spawn just happen", so
    trimming the new end would delete precisely the evidence anyone asks for."""
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    if len(lines) <= _RUN_LEDGER_MAX_LINES + _RUN_LEDGER_SLACK:
        return
    import register_store
    register_store.atomic_write(p, "\n".join(lines[-_RUN_LEDGER_MAX_LINES:]) + "\n")


def read_run_ledger(state_dir=None) -> list:
    """Every well-formed record in the ledger, oldest first. Never raises.

    The ONE reader. A torn line is skipped without discarding the rows around it
    — that behaviour was in both hand-written parsers and is preserved here
    rather than re-derived per caller."""
    import json as _json
    out: list = []
    try:
        p = Path(run_ledger_path(state_dir))
        if not p.is_file():
            return out
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 — an unreadable ledger is "no evidence"
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            blob = _json.loads(line)
        except Exception:  # noqa: BLE001 — a torn line must not drop its neighbours
            continue
        rec = RunRecord.from_wire(blob)
        if rec is not None:
            out.append(rec)
    return out


def stuck_streak(*, session, domain, state, state_dir=None) -> int:
    """How many times IN A ROW this session's `domain` has just answered `state`.

    CONSECUTIVE, not cumulative. Two blocks either side of a run that succeeded are two
    separate attempts, and folding them together escalates work that already recovered.

    An anonymous session returns 0 for the reason `latest_state` returns None: two
    unnamed runs are not one session, and pooling them escalates one caller because a
    different one was stuck.
    """
    if not session or not domain or not state:
        return 0
    streak = 0
    for rec in read_run_ledger(state_dir):
        if rec.session != session or rec.domain != domain:
            continue
        streak = streak + 1 if rec.state == state else 0
    return streak


def escalation_policy() -> dict:
    """The repeat threshold and the domains it applies to, from the registry.

    Declared rather than hardcoded: the number is a judgement about how many failures
    make a wall, and a project whose runs are cheap should be able to say a different
    one without editing the engine.
    """
    base = _base_registry_path()
    cfg = (_read_registry_file(base).get("advice_escalation") or {}) \
        if base.is_file() else {}
    return {
        "repeat_threshold": int(cfg.get("repeat_threshold") or 3),
        "domains": [str(d) for d in (cfg.get("domains") or [])],
    }


def scope_posture_policy() -> dict:
    """Where scope-cutting is decided and where it is merely obeyed.

    Declared rather than hardcoded for the same reason the escalation threshold is: a
    project can move `plan` out of `auto_domains` or add a build step without editing
    the engine. The default stays `full` in code as well as in data — a registry that
    fails to load must not silently start trimming scope.
    """
    base = _base_registry_path()
    cfg = (_read_registry_file(base).get("scope_posture") or {}) \
        if base.is_file() else {}
    return ScopePosture.from_entry(cfg).as_dict()


def output_rung_policy() -> dict:
    """Which rungs exist above markdown, where each one applies, and the rule.

    Declared for the same reason the scope posture is: a project that publishes from
    a different step should be able to say so without editing the engine. The default
    stays `markdown` in code as well as in data — a registry that fails to load must
    not silently start rendering pages.
    """
    base = _base_registry_path()
    cfg = (_read_registry_file(base).get("output_rung") or {}) \
        if base.is_file() else {}
    return OutputRungs.from_entry(cfg).as_dict()


def _apply_output_rung(result: dict, domain: str, *, rung) -> dict:
    """Stamp the rung, and pull the rendering rule in ONLY above the default.

    A domain outside every rung gets no field at all: a field that is always the same
    teaches the reader to skip it, and the day it is not the same they skip it then
    too.
    """
    policy = output_rung_policy()
    covered = {d for names in policy["rungs"].values() for d in names}
    if domain not in covered:
        return result
    out = dict(result)
    out["output_rung"] = rung or policy["default"]
    if rung and rung != policy["default"]:
        # There is nothing to publish but the page, so the publish rung says the page
        # was rendered rather than leaving the reader to infer it.
        out["output_rendered"] = True
        # Named here, appended at the envelope seam — `rules` on the result is not the
        # `rules` the caller reads.
        out["output_rung_rule"] = policy["rule"]
    return out


def _note_inapplicable_flags(result: dict, domain: str, typed) -> dict:
    """Say when an engine flag was typed where it means nothing.

    Every one of these flags is answered by the engine and scoped to the domains
    where it changes something. Typed anywhere else it was STRIPPED and forgotten,
    so the run looked exactly like a run without it — the operator asked for a
    posture, a rung or counsel, got none, and was told nothing. Silence is the one
    answer an operator cannot act on.

    Not an error: the step still answers, and failing a run over a flag that changes
    nothing would be worse than ignoring it. It is reported instead.
    """
    scoped = engine_flags()
    stray = sorted(f for f in typed if domain not in set(scoped.get(f) or []))
    if not stray:
        return result
    out = dict(result)
    out["flags_ignored"] = stray
    where = "; ".join(
        "%s applies to %s" % (f, ", ".join(scoped.get(f) or []) or "no domain")
        for f in stray)
    out["next_action"] = "%s — NOTE: %s had no effect here (%s)." % (
        out.get("next_action") or "", ", ".join(stray), where)
    return out


def engine_flags() -> dict:
    """The flags the ENGINE answers, and the domains each one means something in.

    Derived from the policies that own them rather than listed a second time: a
    hand-kept list is how `--yagni` came to be stripped in one place and still
    reported as a skill-only flag in another. A reader — the CLI stripping argv, or a
    gate asking which layer a flag belongs to — gets one answer.
    """
    rungs = output_rung_policy()["rungs"]
    # A plain mapping of flag -> domains, built from the policies that own each one.
    # Not a record: the KEYS are data (a rung added to the registry adds a flag), so
    # a fixed set of fields would be the hand-kept list this function exists to
    # replace.
    out = {"--advice": list(escalation_policy()["domains"]),
           "--yagni": sorted(set(scope_posture_policy()["auto_domains"])
                             | set(scope_posture_policy()["enforce_domains"]))}
    for rung, domains in rungs.items():
        out["--%s" % rung] = list(domains)
    return out


def _apply_scope_posture(result: dict, domain: str, *, yagni: bool) -> dict:
    """Stamp the posture, and pull the rule in ONLY when the posture is to cut.

    The pointer is conditional on purpose. A rule reference that arrives on every run
    is a reference nobody opens, and the whole reason routing keys on state is that a
    pointer is worth something at the moment it applies and worth nothing before.

    Domains outside both lists get no field at all rather than a `full` they never
    consult: a field that is always the same teaches the reader to skip it, and the
    day it is not the same they will skip it then too.
    """
    policy = scope_posture_policy()
    auto, enforce = set(policy["auto_domains"]), set(policy["enforce_domains"])
    if domain not in auto | enforce:
        return result
    out = dict(result)
    out["scope_posture"] = "yagni" if yagni else policy["default"]
    if domain in auto:
        out["scope_posture_auto"] = True
    if yagni:
        # Named here, appended at the envelope seam. `rules` on the result is not the
        # `rules` the caller reads: the envelope rebuilds that list from step routing,
        # so a pointer written here is overwritten a hundred lines later and the
        # overwrite is silent — measured, the flag reported `yagni` with the rule
        # nowhere in the output.
        out["scope_posture_rule"] = policy["rule"]
    return out


def latest_run_id(*, session, domain=None, verb=None, state_dir=None):
    """The most recent `run_id` for this session, or None.

    The one query both consumers hand-rolled: `hook_dispatch` wanted the last
    record for a session; `hs_run_cook` wanted the last `cook`/`prompt` one. Same
    walk, same last-wins rule, same "a blank id is not evidence" guard — which is
    why it is one function and not two that agree by coincidence."""
    found = None
    for rec in read_run_ledger(state_dir):
        if rec.session != session or not rec.run_id:
            continue
        if domain is not None and rec.domain != domain:
            continue
        if verb is not None and rec.verb != verb:
            continue
        found = rec.run_id
    return found


def latest_state(*, session, domain=None, verb=None, state_dir=None):
    """The last state this session reached in `domain`, or None if it never ran.

    The read side of the breadcrumb. A skill resuming mid-work would otherwise
    have exactly one way to learn where it got to: re-run every projection and
    re-read the tree, paying the full context cost again for an answer the CLI
    already computed and threw away one turn earlier.

    None vs "" are DIFFERENT claims and both are reachable: None means no run of
    this domain is on record, "" means one is but it predates the field. A reader
    that folded them together could not tell "never started" from "started on an
    older build".

    Same walk, same last-wins rule as `latest_run_id` — one traversal of this file
    rather than two that agree by coincidence.

    An ANONYMOUS session is not a session, and asking with one returns None rather
    than a pooled answer. `session` is empty on 1,822 of the 2,025 records in this
    repo's live ledger (90%), because `_resolve_session()` yields nothing when the
    environment carries no id — and `rec.session != session` is False for two
    unrelated anonymous runs, so the filter matched all of them. Reproduced: two
    runs recorded with no session, and this returned the SECOND one's state to a
    caller asking about the first. A breadcrumb that hands back someone else's
    position is worse than no breadcrumb, because the reader has no way to tell.
    """
    if not session:
        return None
    found = None
    for rec in read_run_ledger(state_dir):
        if rec.session != session or not rec.run_id:
            continue
        if domain is not None and rec.domain != domain:
            continue
        if verb is not None and rec.verb != verb:
            continue
        found = rec.state
    return found


def _record_run(run_id, session, domain, verb, state_dir=None, state="") -> None:
    """Append one ledger line. Fail-open.

    Append-only with `actor` + `ts`, which is the machine-written store contract
    (`harness/rules/harness-contract.md`) rather than a preference. Both halves
    were broken here: the record carried no `actor` at all, and the size cap did
    a read-modify-write — see `_trim_run_ledger` for what that cost, measured.

    The append and the trim share ONE exclusive lock. Taking the lock only for
    the trim would leave the window this store lost records through: the trim
    writes back text it read before a concurrent append landed."""
    if not run_id:
        return
    try:
        import json as _json
        import time as _time

        import register_store

        p = Path(run_ledger_path(state_dir))
        p.parent.mkdir(parents=True, exist_ok=True)
        rec = RunRecord(run_id=run_id, session=session, domain=domain,
                        verb=verb, actor=_ledger_actor(), ts=_time.time(),
                        state=str(state or ""))
        line = _json.dumps(rec.as_dict(), ensure_ascii=False) + "\n"
        with register_store.register_lock(p.with_suffix(p.suffix + ".lock")):
            with p.open("a", encoding="utf-8") as fh:
                fh.write(line)
            _trim_run_ledger(p)
    except Exception:
        pass  # bookkeeping never gates the verb — see the block comment above

# --------------------------------------------------------------- exit-code tiers
# NEW vs hs_cli.py (which only ever uses 0/1/2, none of them this four-way split —
# infrastructure recon): `10` means "the CLI's own work is done —
# it correctly projected the next action — but that action itself is a MODEL turn
# (spawn a subagent, then feed the result back via a `record` verb) and cannot be
# carried out by this process." `11` (D10, added after the red-team review found `10`
# was being overloaded to also mean "just run this other CLI command") means "one more
# DETERMINISTIC step remains — run `next_action`, then call again"; it is the caller's
# job to loop on `11`, never on `10`. Neither is an error; EXIT_BROKEN (2) stays
# reserved for an unresolvable domain/verb, an unloadable registry, or a crash.
class State(StrEnum):
    """The state vocabulary as a closed set rather than 64 free-floating string
    literals scattered across ten modules.

    StrEnum (3.11+; every CI job runs 3.12 and no job declares a lower floor):
    `json.dumps` emits the plain string and `State.NO_PLAN == "no_plan"` holds,
    so no consumer changes and no test changes. What it buys is that a mistyped
    member is an AttributeError where you typed it, instead of a brand-new state
    name arriving at a reader with no branch for it.

    Grouped by domain below, because a flat alphabetical list hides which verb
    owns what, and that is the first question anyone reading a state has.

    NOT a per-domain enum: `error`, `blocked` and `no_plan` are emitted by
    several domains, and splitting them would create the same name in four
    types — the exact drift this replaces."""
    # cross-domain
    ERROR = "error"
    HELP = "help"
    OK = "ok"
    READY = "ready"
    # Not any domain's answer — the ENGINE's, raised when a domain has returned the
    # same answer often enough that repeating it has stopped being an attempt. The
    # domain's own state rides alongside as `domain_state`; this one only changes what
    # to do next.
    STUCK = "stuck"
    # `ready` when the review makes ONE pass; this when it fans out (effort >= medium).
    # A different set of documents arrives, and a bigger one — orchestration before any
    # spawn, then the recall ladder — so it is a different step wearing the same word.
    # Review-only today, but named for the shape rather than the domain: any verb whose
    # next move is a fan-out is at the same fork.
    READY_RECALL = "ready_recall"
    BLOCKED = "blocked"
    NO_PLAN = "no_plan"
    UNRESOLVED = "unresolved"
    NOT_A_PLAN_DIR = "not_a_plan_dir"
    PLAN_UNRESOLVED = "plan_unresolved"
    STATE_CONFLICT = "state_conflict"
    MULTIPLE_PLANS = "multiple_plans"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    VERIFIED = "verified"
    RECORDED = "recorded"
    WAITING_ON_MODEL = "waiting_on_model"
    # plan
    SCAFFOLDED = "scaffolded"
    NEEDS_RESEARCH = "needs_research"
    NEEDS_PLANNER = "needs_planner"
    NEEDS_REDTEAM = "needs_redteam"
    NEEDS_MODEL_ATTESTATION = "needs_model_attestation"
    NO_PLAN_GRAPH = "no_plan_graph"
    APPROVED = "approved"
    NOT_APPROVED = "not_approved"
    APPROVAL_INVALID = "approval_invalid"
    APPROVAL_REFUSED = "approval_refused"
    APPROVAL_DRIFTED = "approval_drifted"
    AMBIGUOUS_APPROVED = "ambiguous_approved"
    HANDED_OFF_TO_COOK = "handed_off_to_cook"
    # plan — the scope-sizing leg. `needs_scope_sizing` means the sizer has not
    # run (or left no readable receipt); `scope_needs_split` means it ran, said
    # this plan is too big for one plan, and nobody has answered that yet.
    NEEDS_SCOPE_SIZING = "needs_scope_sizing"
    SCOPE_NEEDS_SPLIT = "scope_needs_split"
    # plan — the grid leg. Peer states of the plan ladder, not sub-states: one
    # name, one routing row, one exit code per call. The two judgment rungs
    # (axes, fill) ride exit 10; the three deterministic rungs (build, expand,
    # emit) ride exit 11 and each carries a verbatim-runnable command. None of
    # them is a failure — each means "this grid step has not run yet".
    GRID_NEEDS_AXES = "grid_needs_axes"
    GRID_NEEDS_FILL = "grid_needs_fill"
    GRID_NEEDS_BUILD = "grid_needs_build"
    GRID_NEEDS_EXPAND = "grid_needs_expand"
    GRID_NEEDS_EMIT = "grid_needs_emit"
    GRID_UNRESOLVED = "grid_unresolved"
    # plan — `plan graph`'s answers. A QUERY verb: these describe the sidecar it
    # was asked about, not the run's progress. `ABSENT` vs `MALFORMED` is decided
    # by whether the file exists, never by matching the parser's error wording.
    # `OK` is the cross-domain member above, reused deliberately.
    ABSENT = "absent"
    MALFORMED = "malformed"
    INVALID = "invalid"
    # cook
    NEEDS_OPEN = "needs_open"
    OPENED = "opened"
    # The idempotent halves of open/close. hs_run_cook.py returns these as bare
    # strings when the verb ran but changed nothing; they were never enumerated,
    # so a routing row for either read as pointing at a state no verb returns.
    ALREADY_OPEN = "already_open"
    OPEN_FAILED = "open_failed"
    NEEDS_IMPLEMENTATION = "needs_implementation"
    # The whole-plan reading of the same tree `NEEDS_IMPLEMENTATION` describes one
    # phase of. Separate words because they ride separate rungs: `next` acts on
    # the resolved phase at 10, `status` reports the plan at 0, and one word on
    # both tells two drivers two different things about one repo.
    PHASES_REMAIN = "phases_remain"
    NEEDS_CLOSE = "needs_close"
    CLOSED = "closed"
    ALREADY_CLOSED = "already_closed"
    CLOSE_FAILED = "close_failed"
    PREFLIGHT_BLOCKED = "preflight_blocked"
    PHASE_FAILED = "phase_failed"
    PHASE_NEEDS_WORK = "phase_needs_work"
    PHASE_NEEDS_REVERIFY = "phase_needs_reverify"
    PHASE_NEEDS_POST_ARTIFACT = "phase_needs_post_artifact"
    NO_PHASE_RESOLVED = "no_phase_resolved"
    UNKNOWN_PHASE = "unknown_phase"
    NEEDS_PHASE_GRID_GATE = "needs_phase_grid_gate"
    BLOCKED_GRID_PHASE_GATE = "blocked_grid_phase_gate"
    NOT_STARTABLE = "not_startable"
    # test
    # Split in two: a tree with no language marker at all, and a recognised stack
    # that never declared a runner. The sentences already differed; the machine
    # field did not, so a driver branching on state alone saw one situation.
    NO_STACK_DETECTED = "no_stack_detected"
    STACK_NO_TEST_CMD = "stack_no_test_cmd"
    VERIFY_FAILED = "verify_failed"
    # review
    NEEDS_REVIEW = "needs_review"
    PHASES_INCOMPLETE = "phases_incomplete"
    VERIFICATION_RECORDED = "verification_recorded"
    REVIEW_MISSING = "review_missing"
    # A fourth close refusal, narrower than the three above it: those ask
    # "is the plan done", this asks "did an opt-in deferred-suite plan pay
    # its debt" — only reachable when the plan carried the flag.
    SUITE_DEBT_UNPAID = "suite_debt_unpaid"
    REJECTED = "rejected"
    UNRESOLVED_CONFLICT = "unresolved_conflict"
    # security
    #
    # `swept_blocked` used to be the only unhappy answer, and it carried six reasons
    # in three groups a reader must act on differently — a real leak, a scan that
    # never finished, and a git that could not answer at all. `swept_clear` was worse:
    # of its seven paths, three meant "I could not look" rather than "I looked and
    # found nothing", including a tree with an AWS key on disk that had no `.git`.
    #
    # Order matters where these are decided: `repo_unreadable` outranks `leak_found`,
    # because a broken git yields an EMPTY hit list that was never measured, and an
    # empty list reads exactly like a clean one.
    SWEPT_CLEAR = "swept_clear"
    # Same sweep, same verdict, but the stack declares no dependency-audit command —
    # said out loud so the next step does not invent one.
    SWEPT_CLEAR_NO_DEP_TOOL = "swept_clear_no_dep_tool"
    LEAK_FOUND = "leak_found"
    SCAN_INCOMPLETE = "scan_incomplete"
    REPO_UNREADABLE = "repo_unreadable"
    NO_REPO = "no_repo"
    # Nothing has leaked yet and `.env` is not covered — one deterministic step away.
    ENV_UNPROTECTED = "env_unprotected"
    SECRET_FOUND = "secret_found"
    DEPS_MISSING = "deps_missing"
    # Installed and importable, but outside its declared range — the tier an import
    # check reports as fine, where the break lands at the first real call instead.
    DEPS_STALE = "deps_stale"
    # `report` reads what the run recorded; preflight only ever saw the run coming.
    NO_VERIFICATION = "no_verification"
    VERIFICATION_MALFORMED = "verification_malformed"
    SUITE_FAILED = "suite_failed"
    # git
    NOTHING_STAGED = "nothing_staged"
    # `push-plan`: the three shapes a push can be in before it is attempted, plus
    # the gate verdict. `no_upstream` is not a failure — a first push is a different
    # command, and calling it an error would send the reader looking for a break.
    NO_UPSTREAM = "no_upstream"
    NOTHING_TO_PUSH = "nothing_to_push"
    PUSH_GATE_BLOCKED = "push_gate_blocked"
    READY_TO_PUSH = "ready_to_push"
    NOTHING_CHANGED = "nothing_changed"
    GIT_DIFF_FAILED = "git_diff_failed"
    # ship
    #
    # `blocked` carried thirty-one measured reasons across seven groups. These five
    # split it by what the READER must do next, not by reason: twelve of the thirty-one
    # are "the receipt is on disk but unusable", and they all end in the same action,
    # so `receipt_invalid` absorbs them rather than becoming twelve names nobody needs.
    #
    # `gates_not_enforced` is the one that was never said at all: with `push.hard`
    # false, a tree carrying ZERO receipts answered `ready`, and the reader had no way
    # to tell "nothing blocked you" from "you are covered".
    GATES_NOT_ENFORCED = "gates_not_enforced"
    NO_PLAN_RESOLVED = "no_plan_resolved"
    RECEIPT_MISSING = "receipt_missing"
    RECEIPT_INVALID = "receipt_invalid"
    # The gate's own configuration contradicts itself — fix the config, not the receipt.
    POLICY_BROKEN = "policy_broken"
    # review-pr
    CI_DONE = "ci_done"
    CI_PENDING = "ci_pending"
    CI_FAILED = "ci_failed"
    CI_TIMEOUT = "ci_timeout"
    CI_CHECK_FAILED = "ci_check_failed"
    NO_CHECKS_FOUND = "no_checks_found"
    UNKNOWN_FORGE = "unknown_forge"
    CLI_UNAVAILABLE = "cli_unavailable"
    CLI_UNAUTHENTICATED = "cli_unauthenticated"
    # skills
    CATALOG_READY = "catalog_ready"
    # Live and disabled stay separate names because the routes are opposite: the
    # off-skill proxy bounces a live target straight back, and a direct invoke of a
    # stashed one finds nothing. One word for both wastes a turn in either direction.
    TARGET_LIVE = "target_live"
    TARGET_DISABLED = "target_disabled"
    # An answer about the catalog, not a failure of it — fixed by re-reading the
    # listing, where `catalog_broken` is fixed by repairing the install.
    TARGET_UNKNOWN = "target_unknown"
    CATALOG_BROKEN = "catalog_broken"
    # fix — `no_plan_resolved` is shared with the ship domain, which rules the
    # same predicate (a hard stage needs a plan and none resolved) at the same
    # rung 2, so it is declared once there rather than twice.
    GATE_BLOCKED = "gate_blocked"
    # review — the structural fork, read from the same pair the pr/ship gate reads
    NEEDS_ARCHITECTURE_REVIEW = "needs_architecture_review"
    # review — the argument names a history mode (PR / commit / codebase) this
    # verb's door does not open onto. A refusal, deliberately not a mode name.
    WRONG_DOOR = "wrong_door"
    # git — a rebase/merge/cherry-pick/revert is mid-flight and HEAD is detached.
    # Distinct from `unresolved_conflict`, which clears the moment the reader
    # stages the fix while the operation itself is still unfinished.
    SEQUENCER_IN_PROGRESS = "sequencer_in_progress"
    # test — a recorded PASS the raw result files do not back
    VERDICT_UNBACKED = "verdict_unbacked"
    # setup — `deps_missing` is shared with the test domain, which rules the same
    # predicate at the same rung; it is declared once, above.
    SCHEMA_LEGACY = "schema_legacy"
    TRUST_NEEDED = "trust_needed"
    CONFIGURED = "configured"
    POLICY_UNREADABLE = "policy_unreadable"


_STATE_VALUES = frozenset(State)


class Exit(IntEnum):
    """The ladder as a closed type rather than four loose ints.

    IntEnum, not Enum: `Exit.DONE == 0` stays True and `json.dumps` emits the
    bare integer, so every existing consumer — shell drivers reading `$?`, the
    envelope's own `exit_code` field, 236 tests — is untouched. What changes is
    that `Exit(3)` RAISES. The ladder is closed by contract and was
    enforced only by a frozenset a caller had to remember to consult; now the
    type itself refuses a fifth rung.

    Why this mattered enough to buy: ten modules each re-declared these four
    constants as bare ints. Ten independent chances for `11` to become `1` in
    one of them, with the frozenset check living in an eleventh file."""
    DONE = 0
    BROKEN = 2
    NEEDS_MODEL = 10
    NEEDS_STEP = 11


# Long-form aliases, kept as the names the ten domain modules and the test suite
# already import. They are the SAME objects, not copies — `EXIT_DONE is Exit.DONE`
# — so there is one ladder with two spellings rather than two ladders.
EXIT_DONE = Exit.DONE
EXIT_NEEDS_MODEL = Exit.NEEDS_MODEL
EXIT_BROKEN = Exit.BROKEN

# Rung 11 answers to BOTH spellings, because the ten hand-written copies had
# already drifted into two: `EXIT_NEEDS_STEP` in four modules, `EXIT_STEP_REMAINING`
# in six. That drift is the concrete damage the copies caused and nothing caught
# it. Both names are bound to the SAME enum member, so `EXIT_NEEDS_STEP is
# EXIT_STEP_REMAINING` — one rung, two spellings, not two rungs. Retiring one
# spelling is a separate mechanical change across ~30 call sites; keeping both
# here is what lets the ten copies be deleted TODAY without touching any caller.
EXIT_STEP_REMAINING = Exit.NEEDS_STEP
EXIT_NEEDS_STEP = Exit.NEEDS_STEP

# The complete, closed ladder — a verb returning anything outside this
# set (a string, a bool, `1`, `3`, ...) is a CONTRACT VIOLATION `main()` catches and
# forces to EXIT_BROKEN with a named warning, never silently passed through raw.
# Kept alongside `Exit` because it answers a different question: `Exit` refuses to
# CONSTRUCT a bad rung, this checks a value that already exists (a verb's raw return).
_VALID_EXIT_CODES = frozenset(Exit)


# ------------------------------------------------------------- argv parsing

class VerbArgError(ValueError):
    """Raised instead of exiting when a verb's argv is malformed.

    Subclasses ValueError so the dispatcher's existing catch already maps it to
    EXIT_BROKEN with a valid envelope — no new guard, no new code path."""


class VerbParser(argparse.ArgumentParser):
    """argparse with both of its exit doors nailed shut.

    Bare argparse writes usage to STDOUT and calls sys.exit on any argv problem.
    That breaks the one thing this CLI promises unconditionally: stdout is always
    a JSON envelope. `json.loads` on an empty stdout raises, and the caller
    cannot tell "the CLI rejected my flags" from "the CLI crashed".

    `exit_on_error=False` is NOT enough, and the reason is version-dependent in a
    way worth stating. On 3.11 it let `unrecognized arguments` through to
    SystemExit; on 3.12 that hole is closed. But `--help` escapes it on EVERY
    version — measured 3.12: SystemExit(0) with usage on stdout. So this class
    overrides error() AND exit(), and is built add_help=False; the dispatcher
    intercepts -h/--help upstream and answers with a help ENVELOPE.

    What it catches that the hand-rolled `_extract_flag` could not:
      - `--plan --phase one`: _extract_flag took the next token blindly, so
        `--plan` silently became the string "--phase".
      - an unknown flag: previously vanished without a word, letting a verb
        auto-resolve a target the operator never named."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("add_help", False)
        super().__init__(*args, **kwargs)

    def error(self, message):
        raise VerbArgError("%s: %s" % (self.prog, message))

    def exit(self, status=0, message=None):
        raise VerbArgError("%s: %s" % (self.prog, message or "argument error"))


_SKILL_FLAG_RE = re.compile(r"--[a-z][a-z0-9-]*")


@lru_cache(maxsize=None)
def _skill_name_for(domain: str) -> str:
    """The SKILL a domain belongs to — its own name unless the registry says
    otherwise.

    They match for most domains, which is why passing a domain straight to
    `skill_flags` looked right for a long time. `review.yaml` declares `skill:
    code-review`, and there the lookup silently returned nothing."""
    try:
        return str((load_step_routing().get(domain) or {}).get("skill") or domain)
    except Exception:
        # Same posture as every other read on this path: a registry that cannot
        # be parsed degrades the MESSAGE, it does not take down the command the
        # reader was running.
        return domain


@lru_cache(maxsize=None)
def skill_flags(skill: str) -> frozenset:
    """Flags the SKILL of this name declares, read from its `argument-hint`.

    Takes a SKILL name, not a domain. It was spelled `domain` and every caller
    passed one, which reads as correct until a domain whose skill is named
    something else comes along — `review`/`code-review` returned an empty set
    and fifteen flags lost their layer message. `_skill_name_for` does the
    translation; the parameter is named for what it wants.

    Two flag layers share one spelling. `hs:plan` declares `--grid`, `--tdd`,
    `--deep` and friends; the model reads them and they change what it does
    (`--grid` becomes `grid: true` in the plan's frontmatter). The CLI's own set
    is smaller and overlaps on `--fast`. Nothing on either surface says which
    layer a flag lives on, so a reader who types a skill flag at the CLI gets
    `unrecognized arguments: --grid` — the same sentence a typo produces, on an
    envelope carrying `rules: []` and `references: []`. The step loses its whole
    routing over a layer mix-up.

    PARSED from the skill, never a second list here. A copy would drift, and the
    flag added to the skill next month would fall back to the generic message —
    which is the failure being fixed, arriving later and quieter.

    Returns an empty set when the skill, the field or the file is missing: this
    only IMPROVES an error message, so an unreadable skill costs the nicer
    sentence and nothing else. Which is also why every failure here is swallowed
    — a CLI that died because it could not read a skill file, while trying to
    write a friendlier message about a flag, would be worse than the flag.

    Located through `catalog.skills_dir()`, the resolver every other reader of a
    SKILL.md already uses: under a global install skills live in the shared BIN
    tree while the project keeps only its own data, so a project-relative path
    would look in a directory that does not exist on that machine."""
    try:
        import catalog
        path = catalog.skills_dir() / skill / "SKILL.md"
        text = path.read_text(encoding="utf-8")
    except Exception:
        return frozenset()
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return frozenset()
    for line in lines[1:40]:
        if line.startswith("argument-hint:"):
            return frozenset(_SKILL_FLAG_RE.findall(line))
        if line.strip() == "---":
            break  # end of frontmatter; the field is not there
    return frozenset()


def _name_the_flag_layer(message: str, domain: str, argv) -> str:
    """Add the layer to an argv error, when the rejected token is a SKILL flag.

    `unrecognized arguments: --grid` is the same sentence a typo produces, so a
    reader who mixed up the two layers has nothing to go on — and the error
    envelope they get carries `rules: []`, so the step's routing is gone too.

    Only for a token the skill actually declares. A flag belonging to no layer
    keeps the plain message, because telling someone `--paln` is "a skill flag"
    would be worse than saying nothing: it sends them to the skill body to look
    for something that is not there. That distinction is the counter-control the
    gate pins, and it is the reason this reads the declaration instead of
    appending a helpful sentence to every argv error."""
    # Keyed on the SKILL, which is usually but not always the domain name. The
    # registry lets a row declare its own (`review.yaml` says `skill:
    # code-review`), and looking the flags up by domain returned nothing there —
    # so every one of that skill's flags read as an ordinary typo, which is the
    # exact failure this function exists to prevent. It went unseen because each
    # case testing it drove `plan`, where the two names happen to match.
    skill = _skill_name_for(domain)
    declared = skill_flags(skill)
    if not declared:
        return message
    hit = [tok for tok in (argv or []) if tok in declared and tok in message]
    if not hit:
        return message
    # No example of what a skill flag DOES. The first version illustrated with
    # "`--grid` becomes `grid: true` in the plan's frontmatter", which is true of
    # plan and was printed verbatim for `cook --review` — an illustration that
    # points at the wrong flag in the wrong domain teaches the reader something
    # false, and no test caught it because every case asserted on the flag name.
    # Naming the layer is the whole job here; what the flag means is the skill's
    # to say.
    return ("%s — %s belongs to the hs:%s SKILL, not to this command. Skill "
            "flags shape what the model does; they are not argv for `hs-run`. "
            "Re-run without it." % (message, ", ".join(hit), skill))


def parse_verb_argv(prog, argv, options=(), flags=(), positionals=(), varargs=None):
    """Parse one verb's argv against its DECLARED flag set.

    This is what replaces the hand-rolled per-flag extractor. That extractor was
    not blind — it already refused `--plan` with nothing after it and `--plan
    --phase one` — and it matches this on five of six shapes. The sixth is the
    reason to switch: a MISTYPED flag (`--paln p1`) returned None from it, so the
    verb fell through to auto-resolving a target the operator never named. Here
    it is a named error.

    That gain has a cost worth stating plainly: a verb whose flag list is
    incomplete will now REJECT a call that works today. So every list is derived
    from the verb's own call sites rather than from its usage string, and where a
    vocabulary already has an owner (review's effort levels live in
    `review_recall.LEVELS`) the caller passes it in rather than restating it — a
    second copy would reject the next level added.

    Returns an argparse Namespace. `options` take a value, `flags` are boolean,
    `positionals` are required in order. Raises VerbArgError, which the
    dispatcher already maps to a valid EXIT_BROKEN envelope.

    `varargs` names one trailing `nargs="*"` slot for verbs whose positional count
    is genuinely open — a plan target that may be given positionally OR through
    `--plan`, and nothing at all when neither is used. Without it those verbs had
    to keep a second, hand-written parser, and a second parser is how one of them
    ends up accepting an argv shape the other refuses."""
    p = VerbParser(prog=prog)
    for name in positionals:
        p.add_argument(name)
    if varargs:
        p.add_argument(varargs, nargs="*")
    for name in options:
        p.add_argument("--%s" % name.lstrip("-").replace("_", "-"),
                       dest=name.lstrip("-").replace("-", "_"))
    for name in flags:
        p.add_argument("--%s" % name.lstrip("-").replace("_", "-"),
                       dest=name.lstrip("-").replace("-", "_"), action="store_true")
    return p.parse_args(list(argv or []))


# ------------------------------------------------------------- value objects

def _seq_of_str(name) -> Callable[[Any], tuple]:
    """Converter+validator pair for the two sequence fields.

    A converter is the whole reason this layer is attrs and not dataclasses:
    ~96 call sites pass a list, and normalising at the boundary beats 96 hand
    edits. None is REJECTED rather than coerced to () — a None here is a branch
    that forgot to assign, which is precisely the bug this layer exists to
    surface, and silently turning it into "nothing" would bury it.

    Hand-written rather than attrs' built-in validators because those raise with
    ~370 characters of Attribute() internals dumped into the message, which
    lands in a user-facing envelope."""
    def convert(value):
        if value is None:
            raise TypeError(
                "%s: expected a sequence of strings, got None — pass () for "
                "'nothing'; None is the signature of a branch that forgot to "
                "assign" % name)
        if isinstance(value, str):
            raise TypeError(
                "%s: expected a sequence of strings, got a single string: %r "
                "— wrap it in a tuple" % (name, value))
        out = tuple(value)
        bad = [v for v in out if not isinstance(v, str)]
        if bad:
            raise TypeError("%s: every element must be a string, got %r" % (name, bad[0]))
        return out
    return convert


def _seq_of_any(name) -> Callable[[Any], tuple]:
    """`_seq_of_str` without the element-type check — for `artifacts` only.

    `artifacts` is not a list of paths on every domain: `hs-run review next`
    puts a structured dict there (scope, rule_count, risk), and `hs-run cook verify`
    puts paths. The two guards that matter are kept, because both fail SILENTLY:
    None (a branch that forgot to assign, buried as "nothing") and a bare string
    (`tuple("plan.md")` is eight one-character entries, not one path). What a domain
    chose to put in the container is the domain's business, and the element check was
    only ever unexercised — this class was constructed by nothing until the
    `from_verb` seam below."""
    def convert(value):
        if value is None:
            raise TypeError(
                "%s: expected a sequence, got None — pass () for 'nothing'; None is "
                "the signature of a branch that forgot to assign" % name)
        if isinstance(value, str):
            raise TypeError(
                "%s: expected a sequence, got a single string: %r — wrap it in a "
                "tuple" % (name, value))
        return tuple(value)
    return convert


# Thin named wrappers, not `_seq_of_any("artifacts")` inline. attrs' mypy plugin
# resolves a converter only when it is a `def`, a type, or a lambda; a call that
# RETURNS a function — and equally a module-level name BOUND to one — reads as
# "unsupported converter", and the field silently falls back to Any, which is the
# opposite of what declaring it was for. The single implementation and its per-field
# error text stay where they are; these only give the plugin a definition to see.
def _convert_artifacts(value):
    return _seq_of_any("artifacts")(value)


def _convert_warnings(value):
    return _seq_of_str("warnings")(value)


import attrs as _attrs  # noqa: E402  (REQUIRED — see harness/requirements.txt; hs-run cannot degrade)
# The modern `attrs` namespace, not the legacy `attr` one: `attrs.define is
# attr.define` (same objects), but the pip distribution is named `attrs`, so
# importing under that name keeps declaration and import spelled identically
# and needs no entry in preflight_deps._MODULE_OVERRIDES.


@_attrs.define(frozen=True, kw_only=True)
class StateRouting:
    """One state's routing row, normalized.

    Every key present with its empty value, so a consumer never has to
    distinguish "absent" from "empty" and no reader needs a `.get(...) or {}`
    dance at the point of use. Declaring that guarantee is stronger than
    documenting it: a field added here is a field every row carries, and the
    caps gate reads the declaration rather than a list repeated beside it."""

    rules: list = _attrs.field(factory=list)
    refs: list = _attrs.field(factory=list)
    docs: list = _attrs.field(factory=list)
    advisory = _attrs.field(default=None)
    when_flag: dict = _attrs.field(factory=dict)
    # One sentence naming what this state IS, for the generated per-skill STATE.md.
    # Not routed to the model and not in the envelope: `advisory` is what a run needs
    # said out loud AT the step, this is what a reader needs to understand the machine
    # BEFORE running anything. Two audiences, two fields — folding them would put
    # index prose into every envelope that fires the state.
    summary = _attrs.field(default=None)

    @classmethod
    def from_entry(cls, entry):
        entry = entry or {}
        # `refs` resolve under the owning skill; `docs` are repo-relative. Separate
        # keys rather than one list with a prefix rule, because a mix-up between the
        # two resolves to a missing file only by accident — a skill-relative path
        # under `docs:` would be looked for at the repo root and simply not be there.
        return cls(
            rules=[str(r) for r in (entry.get("rules") or [])],
            refs=[str(r) for r in (entry.get("refs") or [])],
            docs=[str(d) for d in (entry.get("docs") or [])],
            advisory=(str(entry["advisory"]).strip() if entry.get("advisory") else None),
            # A conditional block carries the same THREE pointer kinds an
            # unconditional row does. This rebuilt it with `refs` alone, so a block
            # naming `rules:` or `docs:` lost them here — before any consumer saw
            # the row, with no warning and every gate green, because the loader is
            # the only place that could have noticed and it was the one dropping
            # them. Measured when fixed: 3 conditional blocks existed and none
            # declared anything but `refs`, so nothing had hit it; the first block
            # that needed a conditional rule would have found out by not getting it.
            when_flag={str(flag): {
                "rules": [str(r) for r in ((cond or {}).get("rules") or [])],
                "refs": [str(r) for r in ((cond or {}).get("refs") or [])],
                "docs": [str(d) for d in ((cond or {}).get("docs") or [])]}
                for flag, cond in (entry.get("when_flag") or {}).items()},
            summary=(str(entry["summary"]).strip() if entry.get("summary") else None))

    def as_dict(self) -> dict:
        return {"rules": list(self.rules), "refs": list(self.refs),
                "docs": list(self.docs), "advisory": self.advisory,
                "when_flag": dict(self.when_flag), "summary": self.summary}


@_attrs.define(frozen=True, kw_only=True)
class OutputRungs:
    """The rungs above the default, where each applies, and the rendering rule.

    A declared record for the same reason the scope posture is: the writer of
    `rungs` and the reader of it are different functions, and a key dropped between
    them arrives as an empty mapping — which reads exactly like "this project
    publishes from nowhere".
    """
    default: str = "markdown"
    rungs: dict = _attrs.field(factory=dict)
    rule: str = "harness/rules/output-rendering.md"

    @classmethod
    def from_entry(cls, entry: dict) -> "OutputRungs":
        entry = entry or {}
        return cls(
            default=str(entry.get("default") or "markdown"),
            rungs={str(k): [str(d) for d in (v or [])]
                   for k, v in (entry.get("rungs") or {}).items()},
            rule=str(entry.get("rule") or "harness/rules/output-rendering.md"))

    def as_dict(self) -> dict:
        return {"default": self.default,
                "rungs": {k: list(v) for k, v in self.rungs.items()},
                "rule": self.rule}


@_attrs.define(frozen=True, kw_only=True)
class ScopePosture:
    """Where scope-cutting is decided, where it is merely obeyed, and the rule.

    A declared record rather than a dict literal: the reader of `enforce_domains`
    is a different function from the writer, and a key dropped in the middle
    arrives as a `None` there instead of a `TypeError` here.
    """
    default: str = "full"
    auto_domains: tuple = ()
    enforce_domains: tuple = ()
    rule: str = "harness/rules/scope-and-contract-discipline.md"

    @classmethod
    def from_entry(cls, entry: dict) -> "ScopePosture":
        entry = entry or {}
        return cls(
            default=str(entry.get("default") or "full"),
            auto_domains=tuple(str(d) for d in (entry.get("auto_domains") or [])),
            enforce_domains=tuple(str(d) for d in (entry.get("enforce_domains") or [])),
            rule=str(entry.get("rule")
                     or "harness/rules/scope-and-contract-discipline.md"))

    def as_dict(self) -> dict:
        return {"default": self.default,
                "auto_domains": list(self.auto_domains),
                "enforce_domains": list(self.enforce_domains),
                "rule": self.rule}


@_attrs.define(frozen=True, kw_only=True)
class DomainRouting:
    """One domain's routing block, normalized.

    `skill` is the directory reference pointers resolve against and defaults to
    the domain name — they diverge (`review` routes into the `code-review`
    skill), so the key exists rather than being inferred. `covers_skill` is a
    separate BOOLEAN claim: that the CLI owns rule selection for that skill. One
    name, one key; the claim is not carried by whether a name happens to be
    present."""

    skill = _attrs.field()
    covers_skill = _attrs.field(default=False, converter=bool)
    always: dict = _attrs.field(factory=dict)
    states: dict = _attrs.field(factory=dict)

    @classmethod
    def from_block(cls, domain, blk):
        blk = blk or {}
        return cls(
            skill=str(blk.get("skill") or domain),
            covers_skill=bool(blk.get("covers_skill")),
            always={"rules": [str(r) for r in
                              ((blk.get("always") or {}).get("rules") or [])]},
            states={str(s): StateRouting.from_entry(e).as_dict()
                    for s, e in (blk.get("states") or {}).items()})

    def as_dict(self) -> dict:
        return {"skill": self.skill, "covers_skill": self.covers_skill,
                "always": dict(self.always), "states": dict(self.states)}


@_attrs.define(frozen=True, kw_only=True)
class RunRecord:
    """One line of the run ledger, declared once.

    This was a dict literal built in `_record_run` and re-parsed, independently,
    by `hs_run_cook` and `hook_dispatch` — three hand-written agreements about a
    format that lives on disk and is read as spawn evidence. Each only had to
    drift once, and the drift would show as a weaker provenance claim rather than
    an error.

    `from_wire` is deliberately tolerant: an unknown key is DROPPED, not fatal.
    An older binary reading a ledger a newer one wrote must skip the field it
    does not know — refusing the line would mean adding a field silently blinds
    every deployed reader."""

    run_id = _attrs.field(default="")
    session = _attrs.field(default="")
    domain = _attrs.field(default="")
    verb = _attrs.field(default="")
    actor = _attrs.field(default="")
    ts = _attrs.field(default=0.0)
    # The run's own last answer, so a later turn can read where it got to instead
    # of re-running every projection to rediscover it. Defaults empty rather than
    # absent: a line written before this field existed must still parse, and ""
    # says "this line predates the field" without pretending to be a state.
    state = _attrs.field(default="")

    def as_dict(self) -> dict:
        return _attrs.asdict(self)

    @classmethod
    def from_wire(cls, blob):
        """A RunRecord from a parsed line, or None when the line is not a record."""
        if not isinstance(blob, dict):
            return None
        known = {f.name for f in _attrs.fields(cls)}
        return cls(**{k: v for k, v in blob.items() if k in known})


@_attrs.define(frozen=True, kw_only=True)
class RunContext:
    """The provenance triple every envelope carries, whatever path produced it.

    `{registry_sources, root, root_source}` was typed out TEN times in this
    module -- once per early return, including the error and help paths nobody
    exercises by hand. Ten copies of one shape is ten chances to omit a field on
    exactly the path a reader most needs it, and the omission looks like an
    envelope that simply had nothing to say about where it looked.

    Declared once: a missing field is a TypeError at the call site instead of an
    absent key at a reader three modules away."""

    registry_sources: list = _attrs.field(factory=list)
    root = _attrs.field(default="", converter=str)
    root_source = _attrs.field(default="")

    @property
    def docs_root(self) -> str:
        """Where the RULES and REFERENCES this envelope routes actually live.

        `root` is the PROJECT — the tree holding `plans/`, what the run is about.
        The documents are not in it. Under a per-project install the two trees
        coincide and nothing notices; under a global install (one shared binary
        serving many projects) they are different directories, and an agent
        resolving a routed document under `root` opens nothing. MEASURED on a
        real `install.py --global` layout: 0 of 5 routed paths resolved under the
        declared root, 5 of 5 were present in the bin.

        Declared as a SECOND field rather than by redefining `root`, because
        `root` is load-bearing for plan resolution, artifact paths and the state
        directory — repointing it to fix a document path would move the breakage
        into three quieter places instead of closing it."""
        import harness_paths
        return str(harness_paths.bin_root())

    def as_extra(self) -> dict:
        """The `extra=` mapping the dispatcher merges into the envelope."""
        return {"registry_sources": list(self.registry_sources),
                "root": self.root, "root_source": self.root_source,
                "docs_root": self.docs_root}


@_attrs.define(frozen=True, kw_only=True)
class StepResult:
    """One verb's answer, as a value rather than a hand-built dict.

    Frozen: a result a later stage can edit is not a result, it is a
    scratchpad. kw_only: 96 sites spell their fields, and positional
    construction across six-plus fields is how `artifacts` and `warnings`
    end up swapped.

    The cross-field rule is the one dataclasses cannot express at the
    declaration: exit 11 PROMISES one deterministic runnable step, so a
    prose `next_command` there strands every driver that dispatches on the
    rung. `__attrs_post_init__` is still a method, but it sits four lines
    under the field it constrains rather than in another file."""
    state: str = _attrs.field()
    next_action: str = _attrs.field()
    exit_code: Exit = _attrs.field(default=Exit.DONE)
    next_command = _attrs.field(default=None)
    artifacts = _attrs.field(default=(), converter=_convert_artifacts)
    warnings = _attrs.field(default=(), converter=_convert_warnings)
    extra: dict = _attrs.field(factory=dict)

    @exit_code.validator
    def _closed_ladder(self, _attribute, value):
        # Checked by VALUE against the closed set, never `isinstance(value, Exit)`.
        # Running `python3 hs_run.py` loads this file as `__main__` while
        # `hs_run_cook` separately `import hs_run` — two live copies of the
        # module, so two distinct `Exit` classes. Measured: an isinstance check
        # rejects its own rung with "must be an Exit rung, got <Exit.DONE: 0>".
        # A bool is excluded explicitly because `True == 1` and `isinstance(True,
        # int)` both hold, so `exit_code=True` would otherwise pass as a rung.
        if isinstance(value, bool) or value not in _VALID_EXIT_CODES:
            raise TypeError(
                "exit_code must be one of the four rungs %s, got %r — the "
                "ladder is closed"
                % (sorted(int(e) for e in Exit), value))

    def __attrs_post_init__(self):
        if self.exit_code is Exit.NEEDS_STEP and not self.next_command:
            raise ValueError(
                "exit %d promises one verbatim-runnable step, but "
                "next_command is empty (next_action was %r) — a driver "
                "looping on this rung has nothing to run"
                % (Exit.NEEDS_STEP.value, self.next_action))

    @classmethod
    def from_verb(cls, mapping, label: str):
        """A verb's raw dict -> `(StepResult, warnings)`, with every contract rule
        applied ONCE, here.

        This is the seam that makes this class reachable. Before it, all three rules
        below were re-implemented as inline `if` blocks in `main()` and this class was
        constructed by nothing — written, tested, and orphan
        (`harness/rules/no-orphan-code.md`). Converting at the ONE point that already
        sees every verb's result gives all 20 current verbs and every future one the
        same enforcement, instead of rewriting 127 return statements for no extra
        guarantee.

        DEGRADES, never raises. `json.loads(stdout)` must never raise on this CLI, so
        a verb that violates the contract yields a named warning plus a forced
        EXIT_BROKEN — the behaviour the inline blocks had, with the messages verbatim.

        Order is load-bearing and preserved from those blocks: the ladder check runs
        first, then the exit-11 prose check, then `next_command` — which reads the
        exit code the two checks above may already have degraded. Reordering would
        report a `next_command` violation against a rung that is no longer live.

        `label` is the "<domain> <verb>" prefix an operator needs to find the culprit;
        it is passed in rather than derived, because this class knows nothing about
        registries."""
        body = dict(mapping or {})
        # Presence read BEFORE the pop, for the same reason `next_command` does it
        # twenty lines down: on this ladder DONE is the strongest CLAIM a verb can
        # make ("nothing left to do"), so defaulting a MISSING key to it turns
        # silence into the loudest possible statement. Four states shipped that
        # way — each printed a message about being stuck and exited 0.
        rung_stated = "exit_code" in body
        exit_code = body.pop("exit_code", Exit.DONE)
        state = body.pop("state", "unknown")
        next_action = body.pop("next_action", "")
        artifacts = body.pop("artifacts", [])
        warnings = list(body.pop("warnings", []) or [])

        if not rung_stated:
            warnings.append(
                "%s returned no exit_code — on this ladder an omitted rung used to "
                "inherit 0 (\"nothing left to do\"), which is a claim about the work "
                "rather than a default; forcing EXIT_BROKEN. State the rung, "
                "including EXIT_DONE when the work really is finished" % label)
            exit_code = Exit.BROKEN
        elif (not isinstance(exit_code, int) or isinstance(exit_code, bool)
                or exit_code not in _VALID_EXIT_CODES):
            warnings.append(
                "%s returned exit_code %r outside the documented ladder %s — forcing "
                "EXIT_BROKEN" % (label, exit_code, sorted(_VALID_EXIT_CODES)))
            exit_code = Exit.BROKEN

        if exit_code == Exit.NEEDS_STEP and not _looks_runnable(next_action):
            warnings.append(
                "%s returned exit_code 11 (one more deterministic step) with a "
                "next_action that is not a runnable `hs-run ...` command (%r) — forcing "
                "EXIT_BROKEN; an 11 promises next_action can be run as-is"
                % (label, next_action))
            exit_code = Exit.BROKEN

        # The state must be a name the vocabulary declares. Checked HERE, at the one
        # seam every verb result passes through, rather than at each of the 20 call
        # sites: a per-site assertion guards the sites that exist today and leaves
        # the next one open. The AST sweep in the conformance suite cannot cover
        # this — it reads literal `state="..."` values, so a state COMPUTED at run
        # time presents nothing to read. `cook status` returned the plan's own
        # frontmatter status straight through, and two of that vocabulary's five
        # values are not `State` members at all; they shipped live and every
        # coverage gate reported the domain fully covered.
        if state not in _STATE_VALUES:
            warnings.append(
                "%s returned the undeclared state %r — forcing EXIT_BROKEN; a "
                "state outside the `State` enum is invisible to the state map, "
                "the routing table and the never-done set, so it reads as "
                "covered while nothing covers it" % (label, state))
            exit_code = Exit.BROKEN

        # Presence is read BEFORE the pop so an ABSENT key stays distinguishable from
        # an explicit null — the two claim different things (see
        # `_next_command_violation`), and defaulting first erases the difference.
        nc_present = "next_command" in body
        next_command = body.pop("next_command", None)
        violation = _next_command_violation(exit_code, nc_present, next_command)
        if violation:
            warnings.append("%s returned %s — forcing EXIT_BROKEN" % (label, violation))
            exit_code = Exit.BROKEN

        return cls(state=state, next_action=next_action, exit_code=exit_code,
                   next_command=next_command, artifacts=artifacts,
                   warnings=warnings, extra=body), warnings

    def as_dict(self) -> dict:
        """The envelope shape the dispatcher already consumes. Lists, not
        tuples, because that is what every existing consumer and every
        golden-file test reads.

        `extra` is merged LAST and only for keys the contract does not define,
        the same rule `Envelope.as_dict` follows: verb results carry a long tail
        of per-verb keys (`summary_numbers`, `phases`, `checklist`, ~20 of them)
        that have to survive the round trip, while a verb must not be able to
        rewrite the state or the rung by smuggling one through the tail."""
        blob = {
            "state": str(self.state),
            "next_action": self.next_action,
            "next_command": self.next_command,
            "artifacts": list(self.artifacts),
            "warnings": list(self.warnings),
            "exit_code": int(self.exit_code),
        }
        for key, value in (self.extra or {}).items():
            if key not in blob:
                blob[key] = value
        return blob



# --------------------------------------------------------------------- registry

class RegistryError(Exception):
    """Base for a registry load failure. `main()` maps every subclass to EXIT_BROKEN
    + a valid JSON error envelope — never a raw traceback."""


class RegistryParseError(RegistryError):
    """A registry file (base or fragment) failed to parse. Fatal, not skippable: a
    silently-skipped fragment makes its verbs vanish and the eventual "unknown
    domain/verb" error points the user at the wrong cause entirely."""

    def __init__(self, path: Path, cause: Exception):
        self.path = path
        self.cause = cause
        super().__init__("could not parse registry file %s: %s" % (path, cause))


class RegistryMissingError(RegistryError):
    """A registry file (an explicit `HARNESS_HS_RUN_REGISTRY` override, or a fragment
    listed by an earlier glob that vanished before it could be read) does not exist at
    all. Kept DISTINCT from RegistryParseError: a
    missing file is not a syntax problem, and reporting it as "could not parse" sends
    the reader hunting for a YAML error that is not there. (The default base file and
    fragments directory being ABSENT is not an error at all — see load_registry()'s
    own `is_file()`/`is_dir()` guards; this class only fires when a path was
    EXPLICITLY named and then turned out not to exist.)"""

    def __init__(self, path: Path):
        self.path = path
        super().__init__("registry file does not exist: %s" % path)


class RegistryConflictError(RegistryError):
    """Two sources (base file and/or fragments) both declare the same (domain, verb).
    Decision: hard error, not last-wins. Silent last-wins means a typo'd or
    alphabetically-late fragment filename can silently hijack an already-registered
    verb — nothing would shout. One-file-per-domain only pays off if a genuine
    collision is treated as the authoring mistake it is."""

    def __init__(self, domain: str, verb: str, first: Path, second: Path):
        self.domain, self.verb, self.first, self.second = domain, verb, first, second
        super().__init__(
            "%s.%s is declared in BOTH %s and %s — a fragment can never silently "
            "override another; rename the verb or delete the duplicate row"
            % (domain, verb, first, second))


class RegistryDuplicateKeyError(RegistryError):
    """A SINGLE registry file (base or fragment) declares the same mapping key twice
    at the same level — two `next:` rows under one `plan:` block, or `plan:` declared
    twice at the top level. This is a DIFFERENT hazard than
    RegistryConflictError above: plain PyYAML's default loader (`yaml.safe_load`)
    treats a repeated mapping key as perfectly legal and silently keeps only the LAST
    one — the duplicate is already gone by the time this module's own cross-file
    conflict detection runs, so a verb (or an entire domain block) vanishes with zero
    trace, and the eventual failure is "unknown verb" — the exact misdirection this
    module's own docstring promises never happens. The shared `yaml_io` loader turns
    this into a loud, path+key-naming error at parse time instead."""

    def __init__(self, path: Path, key):
        self.path = path
        self.key = key
        super().__init__(
            "%s declares the key %r more than once at the same mapping level — a "
            "last-wins loader would silently keep only the LAST one (a verb or an "
            "entire domain block vanishing without a trace); remove the "
            "duplicate row" % (path, key))


class RegistryExtensionError(RegistryError):
    """A `.yml`-suffixed fragment under `hs-run-registry.d/`.
    Decision: REJECT loudly, do not silently accept it as a second valid extension.
    Every other file under `harness/data/` is `.yaml` already (verified: zero `.yml`
    files exist in that tree) — silently accepting `.yml` too would let two files
    (`plan.yaml` + `plan.yml`) both claim the same domain with no documented rule for
    which wins, which is a worse hazard than the one being fixed. Between "accept
    both" and "reject", reject matches the existing one-extension convention and
    costs nothing (rename is a one-line fix); silently ignoring it — the previous
    behaviour, `*.yaml`-only glob with no complaint — is the one option ruled out."""

    def __init__(self, path: Path):
        self.path = path
        super().__init__(
            "%s uses the '.yml' extension — hs-run registry fragments must use "
            "'.yaml' (matching every other file under harness/data/); rename it, "
            "do not add a second accepted extension" % path)


# `ProjectRootError` and the root-resolution functions below now live in
# harness_root.py (imported after the sys.path insert, further down) — hs-cli
# needs the SAME rules for its own catalog lookups, and a private,
# underscore-prefixed function in this sibling module is not an API hs-cli may
# import (this module's own docstring, lines 3-6: hs-cli and hs-run are two
# independent siblings, neither imports the other). `ProjectRootError` is
# re-bound to the name this module's own `except ProjectRootError` clauses
# already use, so both raise sites and both catch sites keep working unchanged —
# see `_resolve_project_root`/`_best_effort_root` below and `main()`'s two
# `except ProjectRootError` blocks.


# Anchored on the trailing ` with value ` and GREEDY, because ruamel does not escape a
# quote inside the key it reports. A non-greedy `"(.*?)"` stops at the first inner quote,
# so a key spelled `say "hi"` came back as `say ` — a key that does not exist in the file,
# handed to the operator with full confidence. DOTALL because a key may contain a newline,
# which otherwise fails to match at all and dumps ruamel's whole multi-line message
# (documentation URL included) into the middle of a sentence.
_DUP_KEY_RE = re.compile(r'found duplicate key "(?P<key>.*)" with value ', re.DOTALL)


def _duplicate_key_name(exc: DuplicateKeyError) -> str:
    """Pull the offending key out of ruamel's DuplicateKeyError for the error message.

    ruamel reports the key inside prose (`found duplicate key "plan" with value ...`)
    rather than as an attribute, so this reads it back out. If that wording ever changes
    the regex stops matching and the fallback hands over the FULL message — less precise,
    but never a confidently wrong key name. The failure mode that shape does NOT cover is
    a regex that matches the wrong SPAN, which is why the pattern is anchored on both
    sides rather than trusting a lazy quantifier to stop in the right place.
    """
    m = _DUP_KEY_RE.search(str(getattr(exc, "problem", "") or exc))
    return m.group("key") if m else str(exc).strip()


def _registry_path():
    """`HARNESS_HS_RUN_REGISTRY` — a single-file override that REPLACES the whole
    base+fragments pipeline below, base file and `.d/` directory both ignored. This is
    deliberately NOT a merge: a fixture test injecting one throwaway registry must see
    EXACTLY what it wrote, never that overlaid on the real plan/cook rows (which could
    silently collide with a fixture verb name, or leak real state into a test that
    assumes it's hermetic). Mirrors hook_dispatch.py's HARNESS_HOOK_DISPATCH_CONFIG
    override, same rationale — proves the router is data-driven with zero code change."""
    return os.environ.get("HARNESS_HS_RUN_REGISTRY")


def _base_registry_path() -> Path:
    """The base file's path in the normal (non-override) pipeline.
    HARNESS_HS_RUN_REGISTRY_BASE points a test at a scratch file instead."""
    raw = os.environ.get("HARNESS_HS_RUN_REGISTRY_BASE")
    return Path(raw) if raw else _ROOT / "harness" / "data" / _REGISTRY_NAME


def _registry_frag_dir() -> Path:
    """The fragments directory in the normal (non-override) pipeline.
    HARNESS_HS_RUN_REGISTRY_DIR points a test at a scratch dir (or a deliberately
    missing one, to prove graceful base-only degradation) instead."""
    raw = os.environ.get("HARNESS_HS_RUN_REGISTRY_DIR")
    return Path(raw) if raw else _ROOT / "harness" / "data" / _REGISTRY_DIR_NAME


@lru_cache(maxsize=None)
def _read_registry_file(path: Path) -> dict:
    """Read one registry file whole. Callers pick the block they want.

    Reading whole and selecting AFTERWARDS is the point: the previous shape read
    the file and returned `.get("domains")` in one step, so any sibling block —
    `step_routing:` being the first — was dropped inside the reader with no
    caller able to observe it had been there.

    Cached per path for the process's lifetime: `_load_registry_impl` calls the
    three block readers (`domains`, `step_routing`, `rules_not_routed`) against
    every source file, and each used to re-open and re-parse it from scratch —
    3 YAML parses per file for 1 file's worth of content. A registry file never
    changes mid-process, so the second and third read of the same path are pure
    waste; measured at ~49ms of a ~58ms `main()` on the real registry. lru_cache
    also means a raised error (missing/duplicate-key/parse failure) is never
    cached — only a successful read is, which is the read worth reusing.
    """
    if not path.is_file():
        raise RegistryMissingError(path)
    try:
        raw = yaml_io.yaml_load(path.read_text(encoding="utf-8"))
    except DuplicateKeyError as e:
        raise RegistryDuplicateKeyError(path, _duplicate_key_name(e)) from e
    except Exception as e:  # noqa: BLE001 — re-raised as a named, path-carrying error
        raise RegistryParseError(path, e) from e
    return raw or {}


def _load_domains_block(path: Path) -> dict:
    """Read one registry file's `domains:` block. An empty/comment-only file is a
    legal no-op ({} back); a MISSING file raises RegistryMissingError (a distinct,
    correctly-named cause — never reported as a parse failure, which sends the
    reader hunting for a YAML syntax problem that does not exist); a
    file that exists but fails to parse (bad syntax, OR a repeated mapping key) raises
    RegistryParseError / RegistryDuplicateKeyError naming THIS path — never swallowed.
    Reads through the shared `yaml_io` loader, whose ruamel safe loader raises
    DuplicateKeyError for a repeated key instead of PyYAML's silent last-wins. The
    ordering of the two excepts matters: DuplicateKeyError is a subclass of the YAML
    error family, so catching it FIRST is what keeps a duplicate key reported as a
    duplicate rather than as a generic parse failure."""
    return _read_registry_file(path).get("domains") or {}


def _load_unrouted_block(path: Path) -> dict:
    """Read one registry file's `rules_not_routed:` block — {rule name: reason}.

    The routing table's own record of what it deliberately does NOT route, kept in
    the same file as the routing so the answer sits next to the question. A rule
    that fires before any verb runs (skill selection, entry routing) has no state
    to hang on; saying so in writing is what keeps it distinguishable from a rule
    somebody simply forgot."""
    return _read_registry_file(path).get("rules_not_routed") or {}


def _load_routing_block(path: Path) -> dict:
    """Read one registry file's `step_routing:` block — {domain: {skill, covers_skill,
    always, states}}. Same file, same errors, read through the same loader as
    `domains:`; a fragment carrying neither block is still a legal no-op.

    Named for the STEP, not for rules: the table carries a step's rules, its reference
    pointers, and its one advisory line, because all three answer the same question.
    A name describing less than its contents teaches the next reader a shape that is
    already wrong."""
    return _read_registry_file(path).get("step_routing") or {}


def _normalize(domains: dict) -> dict:
    return {str(d): {str(v): spec for v, spec in (verbs or {}).items()}
            for d, verbs in domains.items()}


def _normalize_state(entry: dict) -> dict:
    """One state's row as the wire mapping every consumer already indexes."""
    return StateRouting.from_entry(entry).as_dict()


def _normalize_routing(routing: dict) -> dict:
    """Coerce a `step_routing:` block to a fully-populated {domain: {...}} shape."""
    return {str(dom): DomainRouting.from_block(dom, blk).as_dict()
            for dom, blk in (routing or {}).items()}


def _normalize_unrouted(unrouted: dict) -> dict:
    return {str(rule): str(why or "") for rule, why in (unrouted or {}).items()}


@_attrs.define(frozen=True, kw_only=True)
class Registry:
    """Everything one registry read produces, as a value rather than a tuple.

    It grew from `(domains, sources)` to four fields, and a four-tuple is how
    `sources` and `routing` end up swapped at a call site with no error anywhere
    — both are truthy containers. Named fields make a miscount a typo instead of
    a silently wrong table. Same `frozen=True, kw_only=True` discipline as
    `StepResult` above, for the same reasons."""
    domains: dict = _attrs.field()
    sources: list = _attrs.field()
    routing: dict = _attrs.field(factory=dict)
    unrouted: dict = _attrs.field(factory=dict)


def load_step_routing(path=None) -> dict:
    """Resolve {domain: {skill, covers_skill, always, states}} — what each step needs,
    owned by the registry rather than hand-copied into skill prose. See `rules_for()`
    and `refs_for()` for how one step's lists are selected."""
    return _load_registry_impl(path).routing


def load_unrouted_rules(path=None) -> dict:
    """Resolve {rule name: why it is not routed} — the deliberately-unrouted
    ledger. A rule that fires before any verb runs has no state to bind to; this
    is where that gets said out loud instead of read off an absence."""
    return _load_registry_impl(path).unrouted


def _state_row(routing: dict, domain: str, state: str):
    blk = (routing or {}).get(domain)
    if not blk:
        return None, None
    return blk, (blk.get("states") or {}).get(state)


def rules_for(routing: dict, domain: str, state: str, flags=()) -> list:
    """The repo-relative rule paths THIS step needs — the domain's `always` rules plus
    this one state's, plus any `when_flag:` block the verb turned on, and nothing else.

    Selecting on state rather than on domain is the whole mechanism. A domain-wide list
    is what the skill bodies already were: every rule named at the top of every run,
    whether the step at hand touches it or not — and read thousands of tokens before
    the step that needs it arrives.

    `flags` reads the SAME conditional blocks `refs_for` reads. It used to read none:
    a `when_flag:` block could name references and get them, name rules and lose them
    silently, with no warning anywhere and every gate green. Measured when this was
    fixed: 3 conditional blocks existed and 0 of them declared `rules:`, so nothing had
    hit it yet — the first block that needed one would have been the first to find out,
    by not getting it."""
    blk, row = _state_row(routing, domain, state)
    if blk is None:
        return []
    names = list((blk.get("always") or {}).get("rules") or [])
    conditional: list = []
    for flag in flags or ():
        sub = ((row or {}).get("when_flag") or {}).get(flag) or {}
        conditional.extend(sub.get("rules") or [])
    for name in list((row or {}).get("rules") or []) + conditional:
        if name not in names:
            names.append(name)
    return ["harness/rules/%s.md" % n for n in names]


def refs_for(routing: dict, domain: str, state: str, flags=()) -> list:
    """The repo-relative reference paths THIS step needs.

    Two sources, one list. `refs:` resolve under the owning skill's directory; `docs:`
    are repo-relative, for a document a step must READ that is not the skill's own —
    `docs/code-standards.md`, `harness/LESSONS.md`. The hooks that name the standards
    are NUDGES for the missing case: fed a tree where they are present, both emit
    `{"continue": true}`, so nothing but prose ever said to read them.

    PATHS, never the text. An envelope carrying the reference bodies is a second copy
    of files that already exist, and a second copy drifts from the first with nothing
    to notice; the pointer costs ~60 characters and the file stays the one source.

    `flags` gates the conditional block. Not every condition is a state: `--grid` is a
    flag the plan frontmatter carries, and its four references are worthless on a run
    without it — hanging them on the state unconditionally would load four files on
    every plan ever made."""
    blk, row = _state_row(routing, domain, state)
    if not row:
        return []
    skill = blk.get("skill") or domain
    names = list(row.get("refs") or [])
    for flag in flags or ():
        for name in (row.get("when_flag") or {}).get(str(flag), {}).get("refs") or []:
            if name not in names:
                names.append(name)
    out = ["harness/plugins/hs/skills/%s/%s" % (skill, n) for n in names]
    # Repo documents last, and in the same list: a consumer wants "what do I read at
    # this step", not two lists it has to remember to check both of.
    #
    # The merge is deliberate and stays; what it hides is that the two halves are
    # relative to DIFFERENT trees. `refs:` ship with the harness (bin); `docs:` are
    # the CONSUMING project's own standards. Under a per-project install the trees
    # coincide and nothing notices. Under a global install a project standard
    # resolved against the bin finds a REAL, READABLE file — the bin is itself a
    # harness checkout — so the agent silently plans against another repository's
    # architecture while the warning beside it correctly says the project has none.
    # `reference_roots` (built by `reference_roots_for` below) is what makes the
    # halves separable without unmerging the list.
    #
    # Conditional `docs:` merge here for the same reason conditional `refs:` merge
    # above: a `when_flag:` block carries all three pointer kinds, and reading only
    # one of them is the defect this loop used to have on the other two.
    conditional_docs: list = []
    for flag in flags or ():
        conditional_docs.extend(
            (row.get("when_flag") or {}).get(str(flag), {}).get("docs") or [])
    for doc in list(row.get("docs") or []) + conditional_docs:
        if doc not in out:
            out.append(doc)
    return out


def reference_roots_for(references, project_root, bin_root=None) -> dict:
    """`{path: root}` — which tree each routed reference is relative to.

    Keyed by the SHAPE the router itself produced, not by a re-derivation: a
    `harness/`-prefixed path is one the harness ships (a skill reference under
    `harness/plugins/`, a rule under `harness/rules/`); anything else came from a
    `docs:` row and belongs to the consuming project.

    `harness/LESSONS.md` is the case worth stating: it is routed in a `docs:` row
    and it IS a harness file, so the prefix — not the row it came from — decides.
    Reading the row instead would send it to the project, where it does not exist.

    Absent project standards keep pointing at the project. That is the honest
    answer — the `no_plan` warning already says they are missing, and silently
    redirecting them to a same-named file in the bin is the defect this closes."""
    import harness_paths
    base = str(bin_root or harness_paths.bin_root())
    project = str(project_root)
    return {path: (base if path.startswith("harness/") else project)
            for path in references or ()}


def advisory_for(routing: dict, domain: str, state: str):
    """The one line THIS step needs said out loud, or None.

    It exists for guidance the CLI cannot turn into a state because it cannot DETECT
    it from disk — "an architecture decision was just finalized" is a model judgment,
    and a state keyed on it would never fire while every gate stayed green."""
    _, row = _state_row(routing, domain, state)
    return (row or {}).get("advisory")


def load_registry(path=None) -> dict:
    """Resolve {domain: {verb: {module, entry}}}. Thin wrapper over
    `_load_registry_impl()` kept for backward compatibility (existing callers/tests
    only want the merged table, not the sources list) — see that function for the
    full contract, including the `.yaml`-only / duplicate-key / conflict rules."""
    return _load_registry_impl(path).domains


def _load_registry_impl(path=None):
    """Resolve one `Registry`: verb table, source paths, rule routing, exemptions.

    `path` (or HARNESS_HS_RUN_REGISTRY) short-circuits to a single file, full stop —
    a MISSING override file is now a named RegistryMissingError, not a confusing
    "could not parse". Otherwise: the base file (if present) merges
    with every `*.yaml` fragment under the registry dir (if the dir exists at all —
    its total absence degrades to base-only, never a crash), fragments visited in
    SORTED FILENAME order (never directory iteration order — that order is not part
    of the OS's contract, so a merge that depended on it would be a latent,
    filesystem-dependent bug). A `.yml`-suffixed fragment is REJECTED loudly
    (RegistryExtensionError — see that class's docstring for why reject
    over silent-accept). A `(domain, verb)` declared by more than one source raises
    RegistryConflictError; a duplicate key WITHIN one source raises
    RegistryDuplicateKeyError — both loud, both naming the file(s).

    The returned sources list is what `main()` surfaces as the envelope's
    `registry_sources` field — the self-declared provenance of which
    files actually won, so a redirected/overridden registry never acts invisibly."""
    override = path if path is not None else _registry_path()
    if override:
        p = Path(override)
        return Registry(domains=_normalize(_load_domains_block(p)), sources=[str(p)],
                        routing=_normalize_routing(_load_routing_block(p)),
                        unrouted=_normalize_unrouted(_load_unrouted_block(p)))

    sources = []
    base = _base_registry_path()
    if base.is_file():
        sources.append(base)
    frag_dir = _registry_frag_dir()
    if frag_dir.is_dir():
        strays = sorted(frag_dir.glob("*.yml"))
        if strays:
            raise RegistryExtensionError(strays[0])
        sources.extend(sorted(frag_dir.glob("*.yaml")))

    merged: dict = {}
    origin: dict = {}  # (domain, verb) -> the file that first declared it
    routing: dict = {}
    routing_origin: dict = {}  # domain -> the file that first routed it
    unrouted: dict = {}
    unrouted_origin: dict = {}  # rule -> the file that first exempted it
    for src in sources:
        for domain, verbs in _load_domains_block(src).items():
            domain = str(domain)
            for verb, spec in (verbs or {}).items():
                verb = str(verb)
                key = (domain, verb)
                if key in origin:
                    raise RegistryConflictError(domain, verb, origin[key], src)
                origin[key] = src
                merged.setdefault(domain, {})[verb] = spec
        # Routing collides at DOMAIN granularity, not (domain, verb): a domain's
        # rule table is one object, so two fragments both declaring it is the same
        # authoring mistake a duplicate verb is — and last-wins would hide it
        # behind alphabetical filename order.
        for domain, blk in _load_routing_block(src).items():
            domain = str(domain)
            if domain in routing_origin:
                raise RegistryConflictError(domain, "step_routing",
                                            routing_origin[domain], src)
            routing_origin[domain] = src
            routing[domain] = blk
        # Same last-wins hazard, one level finer: an exemption is a rule's licence
        # to be unreachable, and a second file quietly re-granting it under a
        # different reason is how a stale licence outlives the reason it was given.
        for rule, why in _load_unrouted_block(src).items():
            rule = str(rule)
            if rule in unrouted_origin:
                raise RegistryConflictError(rule, "rules_not_routed",
                                            unrouted_origin[rule], src)
            unrouted_origin[rule] = src
            unrouted[rule] = why
    return Registry(domains=merged, sources=[str(s) for s in sources],
                    routing=_normalize_routing(routing),
                    unrouted=_normalize_unrouted(unrouted))


def _resolve(domain: str, verb: str, registry: dict):
    """Return the callable for (domain, verb), or None if either is unregistered.
    Import happens HERE, at dispatch time, not at registry-load time — a domain
    nobody calls this run never pays an import cost (mirrors hook_dispatch.py's
    _resolve_core lazy-import discipline)."""
    spec = (registry.get(domain) or {}).get(verb)
    if spec is None:
        return None
    module_name = str(spec["module"])
    entry_name = str(spec.get("entry") or ("cmd_" + verb.replace("-", "_")))
    mod = importlib.import_module(module_name)
    return getattr(mod, entry_name, None)


# ------------------------------------------------------------------- root resolve
#
# The algorithm itself (red-team-reproduced, measured — not
# assumed — against the live Bash-tool env, where CLAUDE_PROJECT_DIR is UNSET)
# now lives in harness_root.py, this module's shared sibling — hs-cli needs
# the SAME rules for its own catalog lookups, and a private, underscore-
# prefixed function here is not an API hs-cli may import.
# This is a thin, behaviour-preserving call-through: same function name, same
# signature, same return shape — the extraction moved the code, it did not
# change it (verified against harness_root.py directly, byte-for-byte root +
# source across every branch: fresh CWD, CLAUDE_PROJECT_DIR set/stale/at-a-
# subdirectory, HARNESS_DATA_ROOT, and the bin-root cross-tenant guard).


def _resolve_project_root():
    return harness_root.resolve_project_root()


# ---------------------------------------------------------------- name suggestion

SUGGEST_CUTOFF = 70
# MEASURED against the real vocabularies, not chosen: `fuzz.ratio` scores genuine
# typos 75-94 (`plna`->`plan` 75, `cok`->`cook` 86, `preflght`->`preflight` 94) and
# the nearest unrelated word 40 (`deploy`->`plan`), with `zzzzzzzz` at 0. 70 sits in
# that 35-point gap, and test_hs_run_unknown_name_suggestion.py re-measures the gap so
# a rapidfuzz upgrade that shifts scoring reddens with the numbers rather than quietly
# suggesting `plan` for `deploy`.


def suggest_name(typed: str, known):
    """The nearest known name to `typed`, or None when nothing is near enough.

    None is the important return. A suggester that always suggests is noise the
    reader learns to skip, and `hs-run deploy` -- a real command in other tools,
    absent here -- must get the list, not a guess.

    `fuzz.ratio`, not the `token_set_ratio` `catalog.py` uses for skill descriptions:
    that scorer measures multi-word overlap and rates two short identifiers sharing a
    token as identical, which is the wrong question for a one-word command name.
    Imported lazily, matching catalog.py's discipline of keeping module import cheap
    for the paths that never need it -- and this path only runs when a name is
    already wrong."""
    names = [str(n) for n in (known or [])]
    if not typed or not names:
        return None
    from rapidfuzz import fuzz, process
    hit = process.extractOne(str(typed), names, scorer=fuzz.ratio,
                             score_cutoff=SUGGEST_CUTOFF)
    return hit[0] if hit else None


def _did_you_mean(typed: str, known) -> str:
    """The suffix to append to an "unknown X" message: ` (did you mean 'y'?)`, or ""
    when nothing is near. A suffix rather than a replacement -- the full known list
    stays, because a reader with no near-match still needs it."""
    hit = suggest_name(typed, known)
    return " (did you mean %r?)" % hit if hit else ""


# ------------------------------------------------------------------- envelope/io

def _opt_seq(value):
    """`None`/empty -> (), any other sequence -> a tuple with its ELEMENTS UNTOUCHED.

    Two deliberate differences from `_seq_of_str`, both measured:

    None IS accepted -- the help and error paths genuinely have no rules or artifacts
    to name, and every call site would otherwise spell `()` for the same meaning.

    Elements are NOT coerced to `str`. `artifacts` is not a list of paths on every
    domain: `hs-run review next` puts a structured dict there (scope, rule_count,
    risk), and stringifying it turned `blob["artifacts"][0]["scope"]` into a character
    index -- 9 tests, caught on the first run after this converter was introduced. The
    container is normalised; what the domain chose to put in it is the domain's.

    The bare-string guard stays, because that failure is silent instead of loud:
    `tuple("plan.md")` is eight one-character entries, not one path."""
    if not value:
        return ()
    if isinstance(value, str):
        raise TypeError("expected a sequence, got a single string: %r "
                        "— wrap it in a tuple" % value)
    return tuple(value)


@_attrs.define(frozen=True, kw_only=True)
class Envelope:
    """The wire contract, as a value object rather than a dict literal.

    MEASURED (2026-08-06): `rules`/`references`/`advisory` were added here, wired end
    to end, covered by 31 tests — and rendered by NEITHER human render path, because
    `hs_cli_render.py` walks a hand-written sequence of `.get()` calls and nothing
    could ask the envelope what its fields were. A dict literal cannot answer that
    question; this class can, and `test_hs_run_envelope_contract.py` asks it.

    `metadata={"render": ...}` is the declaration that gate reads. `render: True`
    means the human path owes the reader this field; `render: False` marks machine
    metadata (`schema`, and `run_id`, which `_write` stamps after the fact). A field
    added with `render: True` reddens EVERY human render path until they show it —
    which is the only arrangement that catches the NEXT field rather than this one.

    "Every" rather than a number, deliberately. This said "both renderers", and
    there were three: the plain and rich paths behind `hs render`, plus
    `_human_line`, the stderr summary that prints on every single invocation and
    is therefore the one most readers see. It was outside the count and showing 2
    of 9 fields. A scope stated as a tally goes stale silently and then reads as
    verified; the gate now enumerates the paths and fails when the list changes,
    so the count lives somewhere a test can check rather than in this sentence.

    `pending` is the road AHEAD, and it is derived on every call like everything else
    here — never a stored cursor. A flat `state` names exactly one thing; when two
    legs are unresolved at once a caller that can only see the first has to run the
    loop to discover the second. A cursor file would answer the same question and
    would also be able to LIE (delete the artifact, the cursor still claims step 4);
    `pending` regresses with the disk, the way `state` does.

    `next_command` is a FIELD, not something read out of `extra`: `extra` fills only
    keys the contract does not define, so a core field routed through it would be
    dropped the moment it gained a default. `rules`/`references`/`advisory` sit high
    on purpose — they are what a model acts on before the rest — and self-declare
    (`[]`, `[]`, `None`) on help/error paths, so an unrouted step stays
    distinguishable from a build with no routing at all. `references` are PATHS: an
    envelope carrying the reference text would be a second copy of files that
    already exist."""
    schema: str = _attrs.field(default=_SCHEMA, metadata={"render": False})
    state: str = _attrs.field(metadata={"render": True})
    next_action: str = _attrs.field(metadata={"render": True})
    next_command = _attrs.field(default=None, metadata={"render": True})
    rules = _attrs.field(default=(), converter=_opt_seq, metadata={"render": True})
    references = _attrs.field(default=(), converter=_opt_seq, metadata={"render": True})
    advisory = _attrs.field(default=None, metadata={"render": True})
    pending = _attrs.field(default=(), converter=_opt_seq, metadata={"render": True})
    artifacts = _attrs.field(default=(), converter=_opt_seq, metadata={"render": True})
    warnings = _attrs.field(default=(), converter=_opt_seq, metadata={"render": True})
    # The rung this run exited on, stated where a machine reads the rest of the
    # answer. It lived ONLY in the process status, so the same run reported it on
    # one channel and stayed silent on the other depending on how it was called:
    # measured on one tree, one verb, one state — CLI exit 10 with no field, the
    # module path a field of 10 with exit 0. Since the number is the one thing a
    # caller BRANCHES on, leaving it out made the machine-readable surface
    # incomplete by exactly the field that decides what happens next. The process
    # status stays authoritative for shells; this is the same number, said aloud.
    exit_code = _attrs.field(default=None, metadata={"render": False})
    extra: dict = _attrs.field(factory=dict, metadata={"render": False})

    def as_dict(self) -> dict:
        """The wire form. Lists, not tuples, because that is what `json.dumps` and
        every golden-file test already read.

        Key order follows the declaration above, so reordering the class reorders
        what a human sees — and `extra` is applied LAST and only for keys the
        contract does not define, so a verb returning its own `state` cannot
        overwrite the dispatcher's."""
        blob = {}
        for field in _attrs.fields(type(self)):
            if field.name == "extra":
                continue
            value = getattr(self, field.name)
            blob[field.name] = list(value) if isinstance(value, tuple) else value
        blob["advisory"] = self.advisory or None
        for key, value in (self.extra or {}).items():
            if key not in blob:
                blob[key] = value
        return blob


def _envelope(state, next_action, artifacts=None, warnings=None, extra=None,
              next_command=None, rules=None, references=None, advisory=None,
              pending=None, exit_code=None) -> dict:
    """Kept as the call-shaped front door for ~40 existing sites; the contract itself
    now lives in `Envelope` above."""
    return Envelope(
        state=state, next_action=next_action, next_command=next_command,
        rules=rules, references=references, advisory=advisory, pending=pending,
        artifacts=artifacts, warnings=warnings, exit_code=exit_code,
        extra=dict(extra or {}),
    ).as_dict()


def _human_line(blob: dict, rerun_cmd: str) -> str:
    """The stderr summary every invocation prints, whether or not anyone pipes
    the JSON through `hs render`.

    So this is the DEFAULT human view, not a lesser one — and it was showing 2 of
    the envelope's 9 rendered fields. The seven it dropped included `advisory`
    (the only channel that separates a grounded step from an invented one) and
    `warnings`. A reader who never learned about `hs render` — which is every
    reader by default — saw none of them, on every run.

    Which fields belong here is read off the DECLARATION, not typed out below:
    a field added to `Envelope` with `render: True` appears here automatically,
    which is the only arrangement that catches the NEXT field. Empty ones are
    skipped, so the ordinary case stays as short as it was.

    Still one line. `\\n` in a value would split it into what looks like two
    envelopes to anything reading line-wise, so values are flattened."""
    def flat(value):
        if isinstance(value, (list, tuple)):
            return ", ".join(flat(v) for v in value)
        return " ".join(str(value).split())

    action = flat(blob.get("next_action", "?"))
    parts = ["state=%s" % flat(blob.get("state", "?"))]
    numbers = blob.get("summary_numbers") or ""
    if numbers:
        parts.append(flat(numbers))
    parts.append(action)
    for field in _attrs.fields(Envelope):
        if field.metadata.get("render") is not True:
            continue
        if field.name in ("state", "next_action"):
            continue  # already positioned above, where a reader looks first
        value = blob.get(field.name)
        if not value:
            continue
        rendered = flat(value)
        # `_error` deliberately puts the same sentence in `next_action` and
        # `warnings`, so an error line printed both halves of a repetition and
        # made the second one look like a separate finding. Dropped only when it
        # is the WHOLE value, never when a warning merely contains the action —
        # that one is a second, real warning.
        if rendered == action:
            continue
        parts.append("%s=%s" % (field.name, rendered))
    parts.append("re-run: %s" % rerun_cmd)
    return " · ".join(parts)


def _write(blob: dict, rerun_cmd: str, domain=None, verb=None) -> None:
    """The single chokepoint every path leaves through — help, error, and verb
    alike. Stamping `run_id` HERE rather than in `_envelope` is deliberate: an
    envelope can be built and discarded (a help level that falls through to a
    deeper one), and an id minted for a run that never emitted would sit in the
    ledger with no envelope to match it, which reads downstream as a spawn
    attributable to a call that produced nothing.

    `domain`/`verb` are recorded for the reader's benefit only — the match is on
    `run_id`. They make a ledger line legible to a human without a join."""
    run_id = _mint_run_id()
    blob["run_id"] = run_id
    # The state rides along from the blob this same call is about to print, so
    # the ledger and the envelope cannot disagree — they are one value read once.
    _record_run(run_id, _resolve_session(), domain, verb,
                state=blob.get("state", ""))
    sys.stdout.write(json.dumps(blob, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    sys.stderr.write(_human_line(blob, rerun_cmd) + "\n")
    sys.stderr.flush()


def _apply_escalation(result: dict, domain: str, *, forced: bool) -> dict:
    """Rewrite a repeated answer into `stuck` — the ONE seam, not six copies.

    Applied here rather than inside each domain module because the trigger is a
    property of the RUN, not of any domain's subject: every module would compute the
    same streak from the same ledger, and six copies of one rule drift as soon as one
    of them is edited.

    The domain's own answer is not discarded. It rides as `domain_state`, because the
    escalation changes what to do NEXT and changes nothing about what was found — a
    reader who cannot still see the finding cannot judge whether the counsel is even
    about the right problem.

    `--advice` forces it with no history. Someone who already knows they are stuck
    should not have to fail twice more before the engine will say so.
    """
    state = str(result.get("state") or "")
    if not state or state == "stuck":
        return result
    policy = escalation_policy()
    if domain not in policy["domains"]:
        return result
    if not forced:
        # This run has not been recorded yet, so the streak on disk is the count
        # BEFORE it. Reaching the threshold means this call is the Nth.
        prior = stuck_streak(session=_resolve_session(), domain=domain, state=state)
        if prior + 1 < policy["repeat_threshold"]:
            return result
    out = dict(result)
    out["state"] = "stuck"
    out["domain_state"] = state
    out["exit_code"] = int(Exit.NEEDS_MODEL)
    out["next_action"] = (
        "%s has answered `%s` %s. Stop re-running it and spawn the "
        "`escalation-consultant` agent for counsel: hand it the task, the evidence "
        "gathered so far as file:line, what has already been tried, and the specific "
        "question. It advises only — the decision and the implementation stay here. "
        "Previous answer: %s"
        % (domain, state,
           "and --advice was passed" if forced
           else "%d times in a row" % policy["repeat_threshold"],
           result.get("next_action") or "(none)"))
    return out


def _error(state: str, message: str, rerun_cmd: str, extra=None) -> int:
    # The rung goes in the envelope and is RETURNED from the same constant, so
    # the two can never be edited apart. Error paths leave through this seam
    # rather than the verb-result one, which is why the field has to be set in
    # both places rather than once at the bottom.
    blob = _envelope(state, message, artifacts=[], warnings=[message], extra=extra,
                     exit_code=int(EXIT_BROKEN))
    _write(blob, rerun_cmd)
    return EXIT_BROKEN


# --------------------------------------------------------------------------- help
#
# `hs-run` with no args, and `hs-run <domain>` with no verb, used
# to `print()` plain prose here — a downstream `json.loads(stdout)` raised on
# BOTH, directly contradicting this module's own output-contract promise ("a downstream
# `json.loads(...)` must never raise on this CLI, full stop"). Measured:
# `hs-run <domain> <verb> --help` was not handled at ALL at this level — the
# `-h`/`--help` token fell straight through to the wrapped verb's own argv,
# which then RAN FOR REAL (`cook open --help` opened a plan; `cook close --help`
# closed one). Fixed by making every help level below build the SAME JSON
# envelope every other path returns (`state="help"`, full three-tier contract,
# routed through `main()`'s single `_write()` call), and by intercepting
# `-h`/`--help` for the VERB level in `main()` itself — BEFORE `fn(verb_args,
# root)` is ever called, so asking for help can never again mutate state.


def _top_help_lines(registry: dict) -> list:
    lines = [
        "usage: hs-run <domain> <verb> [args...]",
        "",
        "hs-run wraps the harness's existing scripts behind a deterministic,",
        "data-driven <domain> <verb> dispatch table (harness/data/%s)." % _REGISTRY_NAME,
        "",
        "domains:",
    ]
    for domain in sorted(registry):
        verbs = ", ".join(sorted(registry[domain]))
        lines.append("  %-8s  %s" % (domain, verbs))
    lines += [
        "",
        "exit codes: 0 done  ·  10 a model turn is required  ·  11 one more "
        "deterministic step  ·  2 broken",
        "run `hs-run <domain> --help` for that domain's verbs.",
    ]
    return lines


def _domain_help_lines(domain: str, registry: dict) -> list:
    verbs = registry.get(domain) or {}
    lines = ["usage: hs-run %s <verb> [args...]" % domain, "", "verbs:"]
    for verb in sorted(verbs):
        lines.append("  %s" % verb)
    lines.append("")
    lines.append("run `hs-run %s <verb> --help` for that verb's wrapped script." % domain)
    return lines


def _verb_help_lines(domain: str, verb: str, spec: dict) -> list:
    module = spec.get("module")
    entry = spec.get("entry") or ("cmd_" + verb.replace("-", "_"))
    return [
        "usage: hs-run %s %s [args...]" % (domain, verb),
        "",
        "wraps: %s.%s" % (module, entry),
        "",
        "exit codes: 0 done  ·  10 a model turn is required  ·  11 one more "
        "deterministic step  ·  2 broken",
        "this help text short-circuits BEFORE %s.%s runs — no state is ever "
        "mutated by --help." % (module, entry),
    ]


def _best_effort_root():
    """Root resolution for a path where NOTHING is about to be read or written —
    a registry-load failure, an unknown domain/verb, or a --help request. None of
    those run a verb, so there is nothing to protect by raising: turning
    `hs-run --help` (or a typo'd domain name) into an EXIT_BROKEN crash over a
    stale `CLAUDE_PROJECT_DIR` the caller was not even relying on for THIS call
    would be its own bug. Falls back to CWD, naming the failure in the source
    string instead of raising, so `root`/`root_source` stay present on EVERY
    envelope (provenance on every path, including errors and
    help). The real, STRICT `_resolve_project_root()` still gates the one path
    that actually matters: calling into a verb that can read/write project
    state (see the try/except around it further down in `main()`)."""
    try:
        return _resolve_project_root()
    except ProjectRootError as e:
        return Path.cwd(), "unresolved:%s" % e


# A verb legitimately points `next_action` at either another `hs-run ...`
# invocation (the common case) or a DIFFERENT wrapped script quoted in
# backticks (e.g. cook's phase-grid gate: "run `grid_engine.py emit --phase
# <id>` for each" — a real, copy-pasteable command, just not hs-run's own).
# Both shapes commonly appear as a SENTENCE with the command embedded, not
# only as the very first token ("preflight clear — open the plan: hs-run
# cook open <dir>") — so this is a containment check, not a prefix check.
_RUNNABLE_HINT_RE = re.compile(r"hs-run\b|`[^`]+`")


def _next_command_violation(exit_code, present: bool, value):
    """`next_command` is a string a driver runs VERBATIM,
    or `null`. The invariant, enforced here for every current and future
    domain: **exit 11 => next_command is a real command; exit 10 =>
    next_command is null.** Returns the violation text, or None.

    Why a SEPARATE field rather than tightening `_looks_runnable` above: that
    check is a CONTAINS check by design (see its docstring — real `11`
    responses embed the command inside an explanatory sentence), and its own
    documented hole is that `"preflight clear — open the plan: hs-run cook
    open <dir>"` passes it while `while exit==11: run(next_action)` still
    cannot run the string literally. Tightening it would force `next_action`
    to become a bare command and destroy the human sentence. Two readers, two
    fields: this one enforces the machine half without touching the prose.

    The two tiers are deliberately NOT symmetric about an ABSENT key:

      - at 11 the tier itself promises a runnable step, so silence breaks a
        promise the caller is entitled to act on — absent and explicit-null
        are both violations (they differ in what they CLAIM, not in whether
        they leave the driver with something to run).
      - at 10 the tier promises the opposite. An absent key claims nothing a
        driver could be misled by, so only a NON-null value is a violation —
        it would offer a command that contradicts the "a model turn is
        required" the verb just reported.

    Emptiness and type are checked, not just `is not None`: a `""` or a
    `["hs-run", ...]` argv list would satisfy a bare null-check and still
    leave `subprocess.run(...)` with nothing runnable — the same class of
    hole this field exists to close, one layer in.
    """
    if exit_code == EXIT_STEP_REMAINING:
        if not present:
            return ("exit_code 11 (one more deterministic step) with NO "
                    "`next_command` key at all — an absent field claims this verb "
                    "never considered it; an 11 promises a command a driver can "
                    "run verbatim")
        if value is None:
            return ("exit_code 11 (one more deterministic step) with "
                    "`next_command: null` — null means 'no verbatim-runnable step "
                    "exists', which contradicts the tier itself")
        if not isinstance(value, str):
            return ("exit_code 11 with a non-string `next_command` (%r) — the field "
                    "is a single string a driver runs verbatim, never an argv list"
                    % (value,))
        if not value.strip():
            return ("exit_code 11 with a blank `next_command` (%r) — whitespace is "
                    "not a command" % (value,))
        return None
    if exit_code == EXIT_NEEDS_MODEL and present and value is not None:
        return ("exit_code 10 (a model turn is required) with a non-null "
                "`next_command` (%r) — a driver looping only on 11 would run it and "
                "skip the model turn this verb just said was needed"
                % (value,))
    return None


def _looks_runnable(next_action) -> bool:
    """The dispatcher's share of the exit-11 promise: `11` says "one more
    DETERMINISTIC step remains — run `next_action`, then call again".
    A `next_action` that is pure prose with no invocable command anywhere in it
    (e.g. "plan-graph declares no phases") breaks that promise outright — the
    caller has nothing to run. This is intentionally a CONTAINS check, not an
    exact-match one: real, already-shipped `11` responses embed the command
    inside a sentence rather than lead with it (see _RUNNABLE_HINT_RE's
    docstring above) — an exact "next_action == 'hs-run ...'" check would
    reject those as false positives, which is worse than under-catching a
    genuinely bad case."""
    if not isinstance(next_action, str):
        return False
    stripped = next_action.strip()
    if not stripped:
        return False
    return bool(_RUNNABLE_HINT_RE.search(stripped))


def _emit_help(lines: list, rerun_cmd: str, root, root_source: str, registry_sources: list) -> int:
    # Asking for help is not an error and owes no further step, so it rides rung
    # 0 — stated, like every other path, from the same constant it returns.
    blob = _envelope("help", "\n".join(lines), artifacts=[], warnings=[],
                     exit_code=int(EXIT_DONE),
                     extra=RunContext(registry_sources=registry_sources, root=root,
                                      root_source=root_source).as_extra())
    _write(blob, rerun_cmd)
    return EXIT_DONE


# --------------------------------------------------------------------------- main

def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Best-effort, NEVER-raising root guess — used only to keep `registry_sources`
    # /`root`/`root_source` present on every early-return envelope below (goal
    # provenance on EVERY path, including errors and help). The verb
    # dispatch path further down re-resolves STRICTLY (and can still raise) right
    # before it would actually call into a verb.
    be_root, be_source = _best_effort_root()

    try:
        _reg = _load_registry_impl()
        registry, registry_sources, step_routing = _reg.domains, _reg.sources, _reg.routing
    except RegistryError as e:  # conflict/parse/duplicate/extension/missing — already
        # names the file(s); every envelope (even this one) self-
        # declares which sources it managed to resolve (empty here — the load itself
        # failed, so there is no trustworthy partial list to report).
        return _error("error", str(e), "hs-run --help",
                       extra=RunContext(registry_sources=[], root=be_root, root_source=be_source).as_extra())
    except Exception as e:  # noqa: BLE001 — an unreadable registry is broken, not a crash
        return _error("error", "registry unreadable: %s" % e, "hs-run --help",
                       extra=RunContext(registry_sources=[], root=be_root, root_source=be_source).as_extra())

    if not registry:
        # F16: an empty registry (fragments dir missing/empty AND an empty/missing
        # base) used to make `--help` print a domain-less list and exit 0 — a smoke
        # test that only checks "`--help` exits 0" would pass on a dead CLI. This is
        # now a named, loud failure instead of a quiet empty list.
        return _error(
            "error",
            "registry loaded 0 domains from sources=%s — check harness/data/%s and "
            "harness/data/%s/*.yaml are present" % (registry_sources, _REGISTRY_NAME, _REGISTRY_DIR_NAME),
            "hs-run --help",
            extra=RunContext(registry_sources=registry_sources, root=be_root, root_source=be_source).as_extra())

    if not argv or argv[0] in ("-h", "--help"):
        return _emit_help(_top_help_lines(registry), "hs-run --help", be_root, be_source, registry_sources)

    domain, rest = argv[0], argv[1:]
    if domain not in registry:
        return _error("error", "unknown domain %r%s (known: %s)"
                       % (domain, _did_you_mean(domain, registry),
                          ", ".join(sorted(registry)) or "(none registered)"),
                       "hs-run --help",
                       extra=RunContext(registry_sources=registry_sources, root=be_root, root_source=be_source).as_extra())

    if not rest or rest[0] in ("-h", "--help"):
        return _emit_help(_domain_help_lines(domain, registry), "hs-run %s --help" % domain,
                           be_root, be_source, registry_sources)

    verb, verb_args = rest[0], rest[1:]
    if verb not in registry[domain]:
        return _error("error", "unknown verb %r for domain %r%s (known: %s)"
                       % (verb, domain, _did_you_mean(verb, registry[domain]),
                          ", ".join(sorted(registry[domain])) or "(none)"),
                       "hs-run %s --help" % domain,
                       extra=RunContext(registry_sources=registry_sources, root=be_root, root_source=be_source).as_extra())

    rerun_cmd = "hs-run %s %s%s" % (domain, verb, (" " + " ".join(verb_args)) if verb_args else "")

    # `hs-run <domain> <verb> --help` used to fall straight
    # through to `fn(verb_args, root)` — the verb itself had no idea `--help` is
    # special, so asking "how do I use this?" ran the verb for real (`cook open
    # --help` opened a plan; `cook close --help` closed one). Intercepted HERE,
    # before `fn` is even resolved — checked ANYWHERE in verb_args, not just the
    # first token, since a flag can precede it (`cook open --plan foo --help`).
    if any(a in ("-h", "--help") for a in verb_args):
        spec = (registry.get(domain) or {}).get(verb) or {}
        return _emit_help(_verb_help_lines(domain, verb, spec), rerun_cmd, be_root, be_source, registry_sources)

    try:
        fn = _resolve(domain, verb, registry)
    except Exception as e:  # noqa: BLE001 — a broken module/entry is broken, not a crash
        return _error("error", "could not load %s.%s: %s" % (domain, verb, e), rerun_cmd,
                       extra=RunContext(registry_sources=registry_sources, root=be_root, root_source=be_source).as_extra())
    if fn is None:
        return _error("error", "%s.%s: entry point missing" % (domain, verb), rerun_cmd,
                       extra=RunContext(registry_sources=registry_sources, root=be_root, root_source=be_source).as_extra())

    try:
        root, root_source = _resolve_project_root()
    except ProjectRootError as e:
        return _error("error", str(e), rerun_cmd,
                       extra=RunContext(registry_sources=registry_sources, root=be_root, root_source=be_source).as_extra())

    common_extra = RunContext(registry_sources=registry_sources, root=root, root_source=root_source).as_extra()

    # Stripped BEFORE the verb sees it. These are the ENGINE's flags, not any
    # domain's, and every domain parser would otherwise have to learn a word that
    # changes nothing about what it computes — the per-skill copy this seam replaces.
    typed = set(verb_args) & set(engine_flags())
    if typed:
        verb_args = [a for a in verb_args if a not in typed]
    forced_advice = "--advice" in typed
    yagni = "--yagni" in typed
    # The publish rung implies the page: publishing markdown would hand back a link
    # to the thing the user did not ask for.
    rung = "wiki" if "--wiki" in typed else ("html" if "--html" in typed else None)

    try:
        result = fn(verb_args, root)
    except Exception as e:  # noqa: BLE001 — stdout stays valid JSON either way
        # Malformed argv is the CALLER's mistake; a fault inside the verb is
        # OURS. Both end at EXIT_BROKEN, but the sentence a human reads must not
        # say "crashed" for a typo'd flag — that sends them debugging the
        # harness instead of re-reading their command line.
        #
        # Matched by NAME, not `except VerbArgError`. Running `python3
        # hs_run.py` loads this file as `__main__` while `hs_run_cook` separately
        # `import hs_run`, so two live copies of this module exist and their
        # `VerbArgError` classes are not identical — measured: the class-based
        # except never fired for an error raised through the imported copy.
        if type(e).__name__ == "VerbArgError":
            return _error("error", _name_the_flag_layer(str(e), domain, verb_args),
                          rerun_cmd, extra=common_extra)
        return _error("error", "%s %s crashed: %s: %s"
                       % (domain, verb, type(e).__name__, e), rerun_cmd, extra=common_extra)

    if not isinstance(result, dict):
        return _error("error", "%s %s returned a non-dict result (%r)"
                       % (domain, verb, type(result).__name__), rerun_cmd, extra=common_extra)

    result = _apply_escalation(result, domain, forced=forced_advice)
    result = _apply_scope_posture(result, domain, yagni=yagni)
    result = _apply_output_rung(result, domain, rung=rung)
    result = _note_inapplicable_flags(result, domain, typed)

    # The closed ladder, the exit-11
    # runnable-step promise, and the `next_command` tiers used to live here as three
    # inline `if` blocks — while `StepResult`, an attrs value object declaring those
    # same rules, was constructed by nothing. One seam, one copy of the rules, every
    # current and future verb covered; see `StepResult.from_verb`.
    step, warnings = StepResult.from_verb(result, "%s %s" % (domain, verb))
    result = dict(step.extra)
    exit_code = step.exit_code
    state = step.state
    next_action = step.next_action
    artifacts = list(step.artifacts)
    next_command = step.next_command

    # A `no_plan` projection with an empty `artifacts` list and no hint
    # of where the CLI looked is an unverifiable answer — name the searched directory
    # (both domains search `<root>/plans`, per _plan_dirs()'s own convention) unless
    # the verb already supplied a more specific `searched_dirs` itself.
    if state == "no_plan" and "searched_dirs" not in result:
        result["searched_dirs"] = [str(root / "plans")]

    # Built from `RunContext`, not spelled out again. This site listed the
    # provenance fields by hand while the ten early-return paths went through the
    # value object — so `docs_root`, added to the object, reached every error and
    # help envelope and NONE of the successful ones. Two spellings of one shape is
    # the failure the class was declared to end; this was the eleventh copy,
    # hiding behind `setdefault` instead of a constructor call.
    for key, value in RunContext(registry_sources=registry_sources, root=str(root),
                                 root_source=root_source).as_extra().items():
        result.setdefault(key, value)

    # The one seam that knows both the domain and the state the verb actually
    # landed on — which is exactly the pair rule selection keys on. Doing it here,
    # once, rather than inside each of the ~20 verbs, is what keeps a new verb from
    # having to remember to route at all.
    # `route_flags` is the verb's own answer to "which conditional blocks apply" —
    # popped like `state`, because only the verb can read a plan's frontmatter. A verb
    # that declares none simply gets no conditional pointers.
    route_flags = result.pop("route_flags", ())

    # `pending` is POPPED and passed explicitly, never left to ride `extra`. `extra`
    # fills only keys the contract does not define, so once `pending` became a field a
    # verb's own value would be silently dropped — the same shape as the advisory that
    # reached the envelope as `None` for a full round of work. A verb that computes
    # nothing simply gets `[]`.
    pending = result.pop("pending", ())

    # The one seam that knows the domain, the state the verb landed on, and its flags —
    # exactly the key step routing selects on. Done here, once, rather than inside each
    # of the ~20 verbs, so a new verb cannot forget to route at all.
    references = refs_for(step_routing, domain, state, route_flags)
    rules = rules_for(step_routing, domain, state, route_flags)
    for _key in ("scope_posture_rule", "output_rung_rule"):
        _extra = result.pop(_key, None)
        if _extra and _extra not in rules:
            rules = list(rules) + [_extra]
    # Both lists, because `rules:` are shipped documents too and a consumer
    # resolving them under the project root has the same problem in miniature.
    result.setdefault("reference_roots",
                      reference_roots_for(list(references) + list(rules), root))
    blob = _envelope(state, next_action, artifacts, warnings, extra=result,
                     next_command=next_command, pending=pending,
                     exit_code=int(exit_code),
                     rules=rules,
                     references=references,
                     advisory=advisory_for(step_routing, domain, state))
    _write(blob, rerun_cmd, domain=domain, verb=verb)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
