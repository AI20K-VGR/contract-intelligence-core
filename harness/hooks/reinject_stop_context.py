#!/usr/bin/env python3
"""reinject_stop_context.py — Stop-event hook: re-inject working context on a
/goal continuation.

A /goal loop continues via the Stop event, NOT a user prompt, so UserPromptSubmit
never fires and the within-window refresh block is never re-injected — it decays over a
long autonomous run (measured 0/30 inject-rate on STOP_HOOK_FEEDBACK). This hook
re-emits build_slim_context() — the SLIM refresh block carrying the live voice register,
active plan/branch, naming stamp, and the rule/CLAUDE.md pointer — via the shared
co-emit chokepoint on each continuation (stop_hook_active), keeping the loop on-voice
and rule-aware. (It deliberately re-injects SLIM, not the heavy diet-B block: the loop
needs the register refreshed, not the full paths/plan sections re-sent every tick.)

NOTE: This hook gates on goal_status met:false (goal-specific). An AFK loop that does
NOT use /goal (e.g., native loop_controller) is NOT covered — it runs through a
different continuation path. If AFK context injection is needed, wire the AFK runner
to call build_context() directly or set up a separate Stop hook.

A Stop hook's `decision: block` re-invokes the model with `reason` as its context
(documented Stop channel; probe-verified CC 2.1.201) — there is no passive inject
channel on Stop — so an ungated re-inject
self-sustains the loop and keeps firing after the goal is met (observed ~88 extra
turns past goal_status met:true). Therefore emission is GATED: emit only while a /goal
is live-and-unmet (transcript's last goal_status is met:false); on met:true / no
marker / any error we stay silent and ride no turn of our own. Default ON; disable
with HARNESS_REINJECT_STOP=0. Telemetry-class + fail-open: never blocks the loop.
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(_HERE)
sys.path.append(os.path.join(os.path.dirname(_HERE), "scripts"))

import hook_runtime  # noqa: E402

HOOK_CLASS = "telemetry"
_STEM = "reinject_stop_context"

# Bounded tail read — a few dozen goal_status markers fit well within this;
# we never slurp a multi-MB transcript. Mirrors emit_session_summary.read_tail's
# pattern without a cross-import (keep the hook self-contained).
_TAIL_BYTES = 256 * 1024


def _last_goal_status(transcript_path):
    """Read the transcript jsonl, return the `attachment` of the LAST record whose
    attachment.type == "goal_status", else None. Tail-read bounded; any error -> None
    (fail-safe silent). Marker pinned from CC v2.1.195 (real transcript 6da86acc)."""
    if not transcript_path:
        return None
    try:
        with open(transcript_path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - _TAIL_BYTES))
            chunk = fh.read()
        last = None
        for line in chunk.splitlines():
            try:
                rec = json.loads(line)
            except Exception:  # noqa: BLE001 — a torn/partial tail line is non-fatal
                continue
            if (isinstance(rec, dict)
                    and isinstance(rec.get("attachment"), dict)
                    and rec["attachment"].get("type") == "goal_status"):
                last = rec["attachment"]
        return last
    except Exception:  # noqa: BLE001 — missing/huge/corrupt transcript -> silent
        return None


def _emit_context(text: str) -> None:
    # Route through the shared co-emit chokepoint (context_surface_config): it picks
    # the Stop model channel (reason default | additionalContext) and adds the optional
    # human systemMessage double-render, on the SAME config surface as UPS/SessionStart.
    # Fail-open to the documented Stop `reason` channel so a config hiccup never stalls
    # the loop (the model must still be re-invoked with context).
    try:
        import context_surface_config as _cs
        _cs.emit("stop", text)
        return
    except Exception as e:  # noqa: BLE001 — surface config never breaks the loop
        hook_runtime.log_hook_error(_STEM, e)
    sys.stdout.write(json.dumps({"decision": "block", "reason": text}))
    sys.stdout.flush()


def core(data: dict):
    """The Stop re-inject text (slim context + folded pending nudge observations), or
    None. Pure — no emit/exit — so the in-process dispatcher can call it; the caller
    owns the enabled-check + terminal write (context_surface_config routes it to Stop's
    decision:block model channel). Fail-open: any error yields None."""
    try:
        # Goal-active gate (runaway guard): a Stop model channel ALWAYS re-invokes the
        # model, so an ungated re-inject self-sustains the loop even after the goal is
        # met. Emit ONLY while a /goal is live-and-unmet (last goal_status met:false);
        # `is False` (identity) so a missing/None met never reads as "alive".
        gs = _last_goal_status(data.get("transcript_path"))
        goal_alive = bool(gs) and gs.get("met") is False
        # DEFAULT-ON (opt-out): "0" hard-disables; anything else enables. goal_alive is a
        # necessary condition, so ON does NOT mean "emit on every Stop".
        _enabled_env = (os.environ.get("HARNESS_REINJECT_STOP") or "").strip() != "0"
        if _enabled_env and data.get("stop_hook_active") and goal_alive:
            import harness_paths
            import inject_prompt_context
            # SLIM: carries the voice register + rule/CLAUDE.md pointer so a /goal loop
            # stays ON-VOICE across ticks (a within-window refresh, not the heavy block).
            # project_root() (NOT root()/bin_root()): the emitted Reports:/Plans: write
            # targets are project-scoped, same reasoning as inject_prompt_context.core()
            # — a root()-based path lands in the shared read-only bin under a global
            # install. No-op under self-host (bin == project).
            text = inject_prompt_context.build_slim_context(harness_paths.project_root())
            # A /goal loop carries no UserPromptSubmit, so nudge_context_inject's model
            # channel is dead. Fold pending nudge observations into the reason so the
            # model receives them too. Fail-open: a nudge miss must never break the loop.
            try:
                import nudge_context_inject
                nudge_ctx = nudge_context_inject.core(data)
                if nudge_ctx:
                    text = (text + "\n\n" + nudge_ctx) if (text and text.strip()) else nudge_ctx
            except Exception as _e:  # noqa: BLE001
                hook_runtime.log_hook_error(_STEM, _e)
            if text and text.strip():
                return text
    except Exception as e:  # noqa: BLE001 — re-injection must never break the loop
        hook_runtime.log_hook_error(_STEM, e)
    return None


def run(raw=None) -> None:
    """Re-inject the slim context as the Stop model channel only on a continuation
    (stop_hook_active) while a goal is live; plain-continue otherwise. Disabled / any
    error -> continue."""
    data = hook_runtime.read_stdin_json() if raw is None else hook_runtime._parse(raw)
    try:
        if hook_runtime.hook_enabled(_STEM, "telemetry"):
            text = core(data)
            if text:
                _emit_context(text)
                return
    except Exception as e:  # noqa: BLE001 — re-injection must never break the loop
        hook_runtime.log_hook_error(_STEM, e)
    hook_runtime.emit_continue()


def main(raw=None) -> None:
    run(raw=raw)


if __name__ == "__main__":
    main()
