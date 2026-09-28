#!/usr/bin/env python3
"""decision_reconcile_nudge — Stop-event NUDGE for Decision Register drift.

When the register has drifted >= N new DECs or >= M flips since the last reconcile
marker, surface a one-line advisory pointing at /hs:remember -> the
decision-reconciler agent. Advisory ONLY: nudge-class, fail-open, never blocks.

Why Stop and no PostToolUse touched-flag (unlike decision_capture_nudge): the
signal here is a register COUNT, not "this session edited a file". A flip can be
recorded by an agent that touched no tracked file in-session, and the count is the
honest trigger (brief 6.2 reasons 2/3). Throttled once per session so a long
session nudges once, not every turn-end. A broken counter lib records a
decision_reconcile_degraded audit event instead of silently looking alive.

Enable resolution: HARNESS_DECISION_RECONCILE_NUDGE env (truthy on / falsey off)
when set, else harness-hooks.yaml. Nudge class default stays OFF (clean install
silent until the entry opts it in); shipped default ON via harness-hooks.yaml.
"""
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import hook_runtime  # noqa: E402
import trace_log     # noqa: E402

HOOK_CLASS = "nudge"
NAME = "decision_reconcile_nudge"
_ENV = "HARNESS_DECISION_RECONCILE_NUDGE"
ALLOW_EXIT = 0

# HIGH-priority (H2-resolved, INV-3 F-2): stderr-on-exit-0 is spec-invisible, and
# decision governance depends on this reaching a human. handle_stop() routes it through
# the shared systemMessage queue (emit_nudge); main() drains that into the hook's ONE
# terminal blob, so the dispatcher can call handle_stop() in-process without a double write.


def _scripts_dir() -> str:
    return str(Path(__file__).resolve().parent.parent / "scripts")


def _import_counter():
    """Insert the sibling scripts dir and import the counter. Hook + counter ship
    together; raises ImportError when the chain is incomplete (degraded path)."""
    sd = _scripts_dir()
    if sd not in sys.path:
        sys.path.insert(0, sd)
    import decision_reconcile  # noqa: E402 — resolved only after the path insert
    return decision_reconcile


def _enabled() -> bool:
    raw = os.environ.get(_ENV, "").strip().lower()
    if raw:
        return raw in ("1", "true", "yes", "on")
    try:
        return hook_runtime.hook_enabled(NAME, HOOK_CLASS)
    except Exception:  # noqa: BLE001 — config read failure -> SAFE nudge default OFF
        return False


def _temp_dir() -> Path:
    return Path(os.environ.get("TMPDIR") or tempfile.gettempdir())


def _throttle_path(session_id: str) -> Path:
    return _temp_dir() / ("harness-reconcile-nudge-%s"
                          % hook_runtime.safe_session_id(session_id))


def _already_fired(session_id: str) -> bool:
    return _throttle_path(session_id).exists()


def _mark_fired(session_id: str) -> None:
    try:
        _throttle_path(session_id).write_text("1", encoding="utf-8")
    except OSError:
        pass


def _advisory(st: Dict[str, Any]) -> str:
    return ("decision-reconcile: %d new DEC(s) / %d flip(s) since the last "
            "reconcile marker. Consider /hs:remember -> run the decision-reconciler "
            "agent, then `decision_reconcile.py --mark`. Advisory only."
            % (st.get("new_decs", 0), st.get("flips", 0)))


def _trace(event: str, actor: str, session_id: str, **kw) -> None:
    try:
        trace_log.append_event(hook=NAME, event=event, actor=actor,
                               session=session_id, **kw)
    except Exception:  # noqa: BLE001 — audit write never breaks the turn
        pass


def handle_stop(payload: Dict[str, Any]) -> int:
    """Judge register drift; surface + record on over-threshold, once per session.
    Always allows."""
    if not _enabled():
        return ALLOW_EXIT
    session_id = payload.get("session_id") or ""
    if _already_fired(session_id):
        return ALLOW_EXIT  # throttle: one nudge per session
    project_dir = hook_runtime.project_dir(payload.get("cwd"))
    if not project_dir:
        return ALLOW_EXIT
    actor = hook_runtime.resolve_actor(session_id)
    try:
        counter = _import_counter()
    except ImportError as exc:
        _trace("decision_reconcile_degraded", actor, session_id,
               status="degraded", note=str(exc)[:200])
        return ALLOW_EXIT
    try:
        st = counter.status(project_dir)
    except Exception as e:  # noqa: BLE001 — advisory must never break turn-end
        hook_runtime.log_hook_error(NAME, e)
        return ALLOW_EXIT

    if st.get("over"):
        _trace("decision_reconcile_observation", actor, session_id,
               status="observed",
               note="new=%d flips=%d" % (st.get("new_decs", 0), st.get("flips", 0)))
        # Default sink is systemMessage (decision-governance, person-aimed); reroutable
        # via nudge-channels.yaml. Route to the SHARED queue (no terminal write here) so
        # both the standalone main() and the dispatcher own the single stdout blob.
        hook_runtime.emit_nudge(
            NAME, "[advisory] %s" % _advisory(st), session=session_id,
            default_channel="systemMessage")
        _mark_fired(session_id)
    return ALLOW_EXIT


def main(argv=None) -> int:
    payload = hook_runtime.read_stdin_json()
    try:
        rc = handle_stop(payload)
    except Exception as e:  # noqa: BLE001 — a hook crash must never break the turn
        try:
            hook_runtime.log_hook_error(NAME, e)
        except Exception:
            pass
        rc = ALLOW_EXIT
    hook_runtime.drain_or_continue()  # drains a queued advisory into the single blob
    return rc


if __name__ == "__main__":
    sys.exit(main())
