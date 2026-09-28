#!/usr/bin/env python3
"""backlog_capture_nudge.py — advisory reminder to record deferred work through
the backlog register instead of hand-editing prose (nudge class).

The funnel: when an unattended or interactive turn ends and the operator has
opted in, surface a ONE-line proposal of the exact `backlog_register.py add`
command. Propose-then-confirm: the nudge NEVER runs the command and NEVER writes
the SSOT — a human (or a later turn) does, after deciding the item is real.
Auto-adding without that confirm step is an explicit red-line.

Class is `nudge` (default OFF): the capture funnel is advisory, so the hook
stays asleep until an operator enables it in harness-hooks.yaml. When enabled it
proposes once per session; it can never be escalated to blocking by config.

Fail-open: any internal error degrades to a silent exit 0 — a nudge must never
break turn-end.
"""
import os
import sys
import tempfile
from pathlib import Path

try:
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 — older streams / already-detached; never fatal
    pass

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HOOKS_DIR, "..", "scripts"))
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import hook_runtime  # noqa: E402
import trace_log     # noqa: E402

HOOK_CLASS = "nudge"
_NAME = Path(__file__).stem


def proposal_text() -> str:
    """The one-line propose-then-confirm advisory. Carries the literal command
    template so the operator can copy-fill-run it — the hook never runs it."""
    return (
        "[nudge] backlog_capture: deferred work this session? Record it as data "
        "instead of editing BACKLOG.md by hand:\n"
        "    python3 harness/scripts/backlog_register.py add "
        '--text "<what>" --type <bug|chore|feature|debt> --priority <P0|P1|P2|P3>\n'
        "Propose-then-confirm: nothing is added until you run it. Advisory, "
        "non-blocking."
    )


def _temp_dir() -> Path:
    """Read $TMPDIR fresh each call (tempfile caches its first read, which breaks
    per-test TMPDIR isolation). Falls back to the stdlib default."""
    return Path(os.environ.get("TMPDIR") or tempfile.gettempdir())


def _safe_id(session_id: str) -> str:
    return hook_runtime.safe_session_id(session_id)


def _flag_path(session_id: str) -> Path:
    return _temp_dir() / ("harness-backlog-cap-%s" % _safe_id(session_id))


def _already_nudged(session_id: str) -> bool:
    return _flag_path(session_id).exists()


def _mark_nudged(session_id: str) -> None:
    """Best-effort once-per-session guard (ephemeral $TMPDIR; never committed).
    A write failure just means the nudge may repeat — it never breaks the turn."""
    try:
        _flag_path(session_id).write_text("1", encoding="utf-8")
    except OSError:
        pass


def _record_observation(session_id: str) -> None:
    """Audit trace so nudge_context_inject can re-surface this at the NEXT
    UserPromptSubmit (H2-resolved: this is a MODEL-aimed nudge -> additionalContext
    relay, not systemMessage). Fail-open — a trace write never breaks the turn."""
    try:
        actor = hook_runtime.resolve_actor(session_id)
        trace_log.append_event(hook=_NAME, event="backlog_capture_observation",
                               actor=actor, session=session_id, status="observed",
                               note="deferred-work proposal surfaced")
    except Exception:  # noqa: BLE001
        pass


def core(data: dict) -> None:
    """Emit the proposal ONCE per session. stderr + a trace observation (relayed
    to the model at the next turn) — never blocks, never writes the SSOT."""
    session_id = str(data.get("session_id") or "")
    if _already_nudged(session_id):
        return
    hook_runtime.route_relay_nudge(
        _NAME, proposal_text(), lambda: _record_observation(session_id))
    _mark_nudged(session_id)


def main() -> int:
    if not hook_runtime.hook_enabled(_NAME, HOOK_CLASS):
        hook_runtime.emit_continue()
        return 0
    data = hook_runtime.read_stdin_json()
    try:
        core(data if isinstance(data, dict) else {})
    except Exception as e:  # noqa: BLE001 — fail-open: a nudge never blocks the turn
        hook_runtime.log_hook_error(_NAME, e)
    hook_runtime.drain_or_continue()
    return 0


if __name__ == "__main__":
    sys.exit(main())
