#!/usr/bin/env python3
"""goal_cycle_nudge.py — advisory reminder to drop a cycle-memory breadcrumb at a
tick boundary (nudge class).

A built-in autonomous loop (/goal, /loop) is memory-blind between ticks: context
resets and UserPromptSubmit does not fire mid-loop. The `cycle_N.md` convention
(see hs:goal/references/cycle-convention.md) bridges that — each tick writes a
breadcrumb the next reads. This hook fires at the tick/Stop boundary and, when
enabled, reminds the run to append that breadcrumb. It NEVER writes the file
itself — the run owns the content.

Class is `nudge` (default OFF): advisory only, opt-in, can never be escalated to
blocking by config. Fail-open: any internal error degrades to a silent exit 0.
"""
import json
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


def advisory_text() -> str:
    """The one-line breadcrumb reminder. Names the cycle_N.md convention; the run
    writes the file, this hook only reminds."""
    return (
        "[nudge] goal_cycle: tick ending — drop a cycle_N.md breadcrumb "
        "(## Done / ## Next / ## Blocker / ## Decisions) so the next tick reads "
        "state instead of guessing. The loop is memory-blind between ticks. "
        "Convention: hs:goal/references/cycle-convention.md. Advisory, non-blocking."
    )


# Bounded tail read — a few dozen goal_status markers fit well within this; never
# slurp a multi-MB transcript. Mirrors reinject_stop_context._last_goal_status
# (kept self-contained — hooks do not cross-import each other).
_TAIL_BYTES = 256 * 1024


def _last_goal_status(transcript_path):
    """Return the `attachment` of the LAST transcript record whose
    attachment.type == "goal_status", else None. This is the goal-active gate: a
    built-in /goal tick stamps this marker, a plain interactive Stop does NOT.
    Tail-read bounded; any error -> None (fail-safe silent). Marker pinned from
    CC v2.1.195 (real transcript 6da86acc)."""
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


def _temp_dir() -> Path:
    """Read $TMPDIR fresh each call (tempfile caches its first read, which breaks
    per-test TMPDIR isolation)."""
    return Path(os.environ.get("TMPDIR") or tempfile.gettempdir())


def _safe_id(session_id: str) -> str:
    return hook_runtime.safe_session_id(session_id)


def _flag_path(session_id: str) -> Path:
    return _temp_dir() / ("harness-goal-cycle-%s" % _safe_id(session_id))


def _record_observation(session_id: str) -> None:
    """Audit trace so nudge_context_inject can re-surface this at the NEXT
    UserPromptSubmit (H2-resolved: this is a MODEL-aimed nudge -> additionalContext
    relay, not systemMessage). Fail-open — a trace write never breaks the turn."""
    try:
        actor = hook_runtime.resolve_actor(session_id)
        trace_log.append_event(hook=_NAME, event="goal_cycle_observation",
                               actor=actor, session=session_id, status="observed",
                               note="cycle_N.md breadcrumb reminder surfaced")
    except Exception:  # noqa: BLE001
        pass


def core(data: dict) -> None:
    """Emit the breadcrumb reminder ONCE per session boundary. stderr + a trace
    observation (relayed to the model at the next turn) — never writes the cycle
    file itself."""
    # Goal-active gate: this breadcrumb reminder is for a built-in /goal tick, NOT
    # every interactive Stop. Without a goal_status marker in the transcript we are
    # not in a goal run — stay silent (fixes fire-on-every-session false-positive).
    # LIMITATION: built-in /loop that does not stamp goal_status is not covered here;
    # a loop-specific marker is future work.
    if _last_goal_status(data.get("transcript_path")) is None:
        return
    session_id = str(data.get("session_id") or "")
    flag = _flag_path(session_id)
    if flag.exists():
        return
    hook_runtime.route_relay_nudge(
        _NAME, advisory_text(), lambda: _record_observation(session_id))
    try:
        flag.write_text("1", encoding="utf-8")
    except OSError:
        pass  # best-effort once-guard; never break the turn


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
