#!/usr/bin/env python3
"""spawn_provenance_workflow_guard.py — PreToolUse(Workflow) gate: enforce
the spawn-provenance budget against the Workflow tool's OWN declared
fan-out width (Ask-3 Layer-2, the P8 phase).

Unlike the Agent|Task lane (`spawn_provenance_guard.py`, a cumulative
session count with no per-call width), a single `Workflow` call declares
its own fan-out in ONE call — WP1-verified (CC emits a PreToolUse event for
`Workflow` and `tool_input.script` carries the FULL script text,
plans/260715-0021-subagent-spawn-guards-and-reinject/probes/
WP1-workflow-pretooluse.md). `spawn_provenance.workflow_width()` reads that
width via a STATIC PARSE of the script — never an execution.

Ships to its OWN `PreToolUse:Workflow` group (not the Agent|Task group —
different tool, different matcher) but reads the SAME token/budget reader
as the Agent|Task lane (`spawn_provenance.budget`/`has_orchestrate_token`):
no separate counter, no `record_spawn` call here — a Workflow call is
self-contained per invocation, not cumulative across calls, so there is
nothing to accumulate.

Default OFF (`spawn_provenance.block_enabled()` — the SAME Layer-1b flip
switch the Agent|Task guard reads, opt-in like `secret_scan_before_ship`).
BLOCK iff the declared width exceeds the session's resolved budget:

    width = spawn_provenance.workflow_width(tool_input.script)
    b     = spawn_provenance.budget(session)
    BLOCK iff width > b

`budget()` already folds the token in (`min(token.sub_count,
sub_count_cap())` when an active token is on record, else `threshold()`) —
so this is symmetric with the Agent|Task lane: an approved wide token
raises the ceiling to its own `sub_count` (a width within it passes), but a
Workflow whose declared width exceeds even that budget still blocks. There
is no separate "any active token bypasses the check" clause — an earlier
revision had one and it let an approved token wave through an arbitrarily
wide Workflow regardless of its declared `sub_count` (asymmetric with the
Agent|Task lane, which always enforces the token's `sub_count`).

Honest ceiling (unchanged even when blocking, and stronger here than the
Agent|Task lane's): this checks provenance + a STATIC-ESTIMATE width +
budget/shape ONLY — never strategy quality, and the width itself is a
heuristic (a dynamic loop `for (...) agent()` cannot be counted exactly;
see `spawn_provenance.workflow_width`'s docstring).

HOOK_CLASS = compliance: mirrors `spawn_provenance_guard.py`'s F4 skeleton
VERBATIM — an INTERNAL ERROR fails OPEN (exit 0) so a bug in this gate
never wedges a Workflow call; only a genuine block decision exits 2. The
block path sits OUTSIDE the fail-open try and the `except` re-raises
SystemExit, so a broad except can never swallow the exit-2 and turn the
gate dark. The dispatch row additionally carries `fail_open: true` as
defense in depth (hook-dispatch.yaml) — the in-process dispatcher calls
`core()` directly, bypassing this file's own `main()` gating, so that
registry flag is what actually protects production; `main()`'s own try
exists for the rarer direct-spawn path.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(os.path.dirname(_HERE), "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hook_runtime  # noqa: E402
import spawn_provenance  # noqa: E402

HOOK_CLASS = "compliance"
_HOOK = "spawn_provenance_workflow_guard"


def _block_reason(width: int, budget: int, session: str) -> str:
    has_token = spawn_provenance.has_orchestrate_token(session)
    source = ("an active orchestrate token" if has_token
              else "no recorded orchestrate strategy")
    return (
        "spawn_provenance: this Workflow call declares a fan-out width of "
        "~%d against a budget of %d (%s). The width is a STATIC estimate — "
        "a script-parse of agent()/parallel()/pipeline() calls (a dynamic "
        "loop cannot be counted exactly, see spawn_provenance.workflow_width) "
        "— and this checks PROVENANCE, COUNT, and SHAPE only, never strategy "
        "quality. Size and group the fan-out through hs:workflow-orchestrate "
        "and get the strategy approved (that mints a wider, disk-backed "
        "budget) before running this Workflow, or narrow the script. If "
        "hs:workflow-orchestrate is off/not installed, run it via /hs:use "
        "workflow-orchestrate (hs:use is always available)."
        % (width, budget, source)
    )


def core(data: dict):
    """Return a BLOCK reason string when this Workflow's declared width
    exceeds the session's resolved budget with no covering orchestrate
    token, else None. Stdout-free (dispatcher-callable).

    Every reader this calls (`workflow_width`/`budget`/
    `has_orchestrate_token`) is fail-open by its own contract
    (spawn_provenance module docstring), so `core()` carries no try/except
    of its own — an unexpected crash surfaces to the caller (main()'s
    fail-open try, or the dispatcher's `fail_open: true` row) rather than
    being silently absorbed here (F4)."""
    if not spawn_provenance.block_enabled():
        return None  # the Layer-1b flip switch — opt-in, default off
    if not isinstance(data, dict) or data.get("tool_name") != "Workflow":
        return None  # not a Workflow call — free
    session = data.get("session_id") or ""
    tool_input = data.get("tool_input")
    script = tool_input.get("script") if isinstance(tool_input, dict) else None
    width = spawn_provenance.workflow_width(script)
    b = spawn_provenance.budget(session)
    # budget() already returns min(token.sub_count, sub_count_cap()) when an
    # active token is on record, else threshold() — so a plain width > b
    # check is symmetric with the Agent|Task lane: an approved wide token
    # raises the ceiling to its OWN sub_count (a width within it passes),
    # but a Workflow exceeding even that budget still blocks. No separate
    # "any active token bypasses the check" clause (N3 — that was
    # asymmetric and let an approved token wave through an arbitrarily wide
    # Workflow regardless of its declared sub_count).
    if width > b:
        return _block_reason(width, b, session)
    return None


def main() -> None:
    # 1. Registration toggle is the ONLY switch. A broken enabled read fails OPEN.
    try:
        if not hook_runtime.hook_enabled(_HOOK, HOOK_CLASS):
            hook_runtime.emit_continue()
            sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001 — a broken enabled read must not wedge a spawn
        hook_runtime.log_hook_error(_HOOK, e)
        hook_runtime.emit_continue()
        sys.exit(0)

    # Every internal error from here fails OPEN (documented deviation, F4 — mirrors
    # spawn_provenance_guard / model_guard).
    try:
        reason = core(hook_runtime.read_stdin_json())  # {} on empty/malformed
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001 — FAIL-OPEN: a gate crash never wedges a spawn
        hook_runtime.log_hook_error(_HOOK, e)
        reason = None
    if reason:
        # The only exit-2 path — deliberate block, kept outside the fail-open try (F4).
        sys.stderr.write("[%s] BLOCKED: %s\n" % (_HOOK, reason))
        sys.exit(2)
    hook_runtime.emit_continue()
    sys.exit(0)


if __name__ == "__main__":
    main()
