#!/usr/bin/env python3
"""decision_capture_nudge — opt-in decision-capture nudge (nudge-class).

The A-leg of memory-v2. A thin, deterministic wrapper around the
`decision_capture` detector: it owns NO detection logic. On turn-end it asks the
detector "did this session ship a decision-shaped change (a NEW hook/script/rule/
agent/skill module, or a gate-config posture change) without the decision ledger
moving?". If so it surfaces a ONE-line advisory pointing at /hs:remember and
records one observation in the audit trace — then ALWAYS allows. It never blocks,
never writes memory or the ledger; the human (or /hs:remember) does the writing.

Class is `nudge` (default OFF): the capture funnel is advisory, so the hook stays
asleep until an operator enables it in harness-hooks.yaml. When enabled it warns +
records; it cannot be escalated to blocking by config.

Two events, one file:
  - default          → `Stop`. Runs the detector behind the touched-flag no-op
    guard, surfaces a signal, records an observation.
  - `--post-tool-use`→ `PostToolUse`. Sets an EPHEMERAL, session-keyed touched-flag
    in $TMPDIR (never committed) — the no-op guard's "did this session write?" cue.

Visible-degradation guarantee: if the detector cannot be imported, the hook emits
a `decision_capture_degraded` audit event first, then allows — a silent no-op
becomes a visible one (a wired hook that looks alive while never firing is the
failure mode this closes).
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import hook_runtime  # noqa: E402
import trace_log     # noqa: E402

HOOK_CLASS = "nudge"
NAME = "decision_capture_nudge"
ALLOW_EXIT = 0


# ---------------------------------------------------------------------------
# Detector import (DRY: reuse decision_capture, never re-implement). Named so a
# test can simulate a broken chain and exercise the degraded path.
# ---------------------------------------------------------------------------

def _import_detector():
    """Insert the sibling scripts dir and import the detector. Hook + detector ship
    together (hooks/ <-> scripts/), so the file-relative sibling is the durable
    anchor. Raises ImportError when the chain is incomplete."""
    sd = str(Path(__file__).resolve().parent.parent / "scripts")
    if sd not in sys.path:
        sys.path.insert(0, sd)
    import decision_capture  # noqa: E402 — resolved only after the path insert
    return decision_capture


def _project_dir(stdin_cwd: Optional[str] = None) -> Optional[str]:
    """The project root to scan. CLAUDE_PROJECT_DIR (set by the host) wins; the
    Stop/PostToolUse stdin `cwd` is the fallback. None if neither is usable."""
    return hook_runtime.project_dir(stdin_cwd)


def _enabled() -> bool:
    """Is the hook enabled? A config-read failure falls to the SAFE nudge default:
    OFF (do nothing) — never warn on an ambiguous config."""
    try:
        return hook_runtime.hook_enabled(NAME, HOOK_CLASS)
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Ephemeral, session-keyed touched-flag ($TMPDIR — not committed).
# ---------------------------------------------------------------------------

def _temp_dir() -> Path:
    """Read $TMPDIR fresh each call (tempfile caches its first read, which breaks
    per-test TMPDIR isolation). Falls back to the stdlib default."""
    return Path(os.environ.get("TMPDIR") or tempfile.gettempdir())


def safe_id(session_id: str) -> str:
    return hook_runtime.safe_session_id(session_id)


def _flag_path(session_id: str) -> Path:
    return _temp_dir() / ("harness-deccap-touched-%s" % safe_id(session_id))


def set_touched_flag(session_id: str) -> Path:
    """Mark "this session wrote something". Ephemeral; best-effort (a write failure
    must never break the turn — the flag is an optimization)."""
    path = _flag_path(session_id)
    try:
        path.write_text("1", encoding="utf-8")
    except OSError:
        pass
    return path


def touched_flag_set(session_id: str) -> bool:
    return _flag_path(session_id).exists()


# ---------------------------------------------------------------------------
# Advisory text + observation note
# ---------------------------------------------------------------------------

def _advisory_text(signal: Dict[str, Any]) -> str:
    """One plain-language advisory line naming the unrecorded change(s) and the
    capture path. Advisory only — never blocks."""
    subjects = signal.get("subjects") or []
    total = signal.get("total", len(subjects))
    shown = ", ".join(subjects)
    if total > len(subjects):
        shown += " (+%d more)" % (total - len(subjects))
    return ("decision-capture: %d decision-shaped change(s) shipped without a "
            "ledger entry: %s. Run /hs:remember to draft a DEC/memory, or record it "
            "by hand. Advisory only." % (total, shown))


def _observation_note(signal: Dict[str, Any]) -> str:
    subjects = signal.get("subjects") or []
    total = signal.get("total", len(subjects))
    return "unrecorded_decision×%d — %s" % (total, ", ".join(subjects))


def _trace_degraded(actor: str, session_id: str, exc: Exception) -> None:
    """Visible no-op: the detector chain is broken, so record it instead of
    pretending the hook ran. Fail-open — the audit write never breaks the turn."""
    try:
        trace_log.append_event(hook=NAME, event="decision_capture_degraded",
                               actor=actor, session=session_id,
                               status="degraded", note=str(exc)[:200])
    except Exception:  # noqa: BLE001
        pass


def _record_observation(actor: str, session_id: str, signal: Dict[str, Any]) -> None:
    try:
        trace_log.append_event(hook=NAME, event="decision_capture_observation",
                               actor=actor, session=session_id,
                               status="observed", note=_observation_note(signal))
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def handle_stop(payload: Dict[str, Any], project_dir: Optional[str] = None) -> int:
    """Run the Stop policy: surface a signal as an advisory + record an observation.
    Always returns ALLOW_EXIT (nudge never blocks)."""
    if not _enabled():
        return ALLOW_EXIT
    project_dir = project_dir or _project_dir(payload.get("cwd"))
    if not project_dir:
        return ALLOW_EXIT

    # No-op guard: only run the detector when this session actually wrote something.
    session_id = payload.get("session_id") or ""
    if not touched_flag_set(session_id):
        return ALLOW_EXIT

    actor = hook_runtime.resolve_actor(session_id)

    try:
        detector = _import_detector()
    except ImportError as exc:
        # the detector chain is incomplete — degrade VISIBLY, then allow.
        _trace_degraded(actor, session_id, exc)
        return ALLOW_EXIT

    try:
        signal = detector.collect(project_dir)
    except Exception as e:  # noqa: BLE001 — advisory: a hook must never break turn-end
        hook_runtime.log_hook_error(NAME, e)
        return ALLOW_EXIT

    if signal:
        hook_runtime.route_relay_nudge(
            NAME, _advisory_text(signal),
            lambda: _record_observation(actor, session_id, signal))
    return ALLOW_EXIT


def handle_post_tool_use(payload: Dict[str, Any],
                         project_dir: Optional[str] = None) -> int:
    """Set the touched-flag when a Write/Edit/MultiEdit landed a file_path. Always
    allows — this handler only records state."""
    if not _enabled():
        return ALLOW_EXIT
    tool_input = payload.get("tool_input")
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if isinstance(file_path, str) and file_path:
        set_touched_flag(payload.get("session_id") or "")
    return ALLOW_EXIT


# ---------------------------------------------------------------------------
# CLI entry (the host invokes this file with stdin)
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    post_mode = "--post-tool-use" in argv
    payload = hook_runtime.read_stdin_json()
    project_dir = _project_dir(payload.get("cwd"))
    try:
        rc = (handle_post_tool_use if post_mode else handle_stop)(payload, project_dir)
    except Exception as e:  # noqa: BLE001 — a hook crash must never break the turn
        try:
            hook_runtime.log_hook_error(NAME, e)
        except Exception:
            pass
        rc = ALLOW_EXIT
    hook_runtime.drain_or_continue()
    return rc


if __name__ == "__main__":
    sys.exit(main())
