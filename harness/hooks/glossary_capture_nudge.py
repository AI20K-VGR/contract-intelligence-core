#!/usr/bin/env python3
"""glossary_capture_nudge — opt-in glossary-capture nudge (nudge-class).

A thin, deterministic wrapper around the `glossary_capture` detector: it owns NO
detection logic. On turn-end it asks the detector "did this session register a
DEC that coins a load-bearing term the glossary does not yet hold?". If so it
surfaces a ONE-line advisory pointing at /hs:remember and records one observation
in the audit trace — then ALWAYS allows. It never blocks, never writes the
glossary; the human (or /hs:remember) does the writing.

Class is `nudge` (default OFF): the capture funnel is advisory, so the hook stays
asleep until an operator enables it in harness-hooks.yaml. It cannot be escalated
to blocking by config.

Two events, one file:
  - default          → `Stop`. Runs the detector behind the touched-flag no-op
    guard, throttled to one advisory per session, records an observation.
  - `--post-tool-use`→ `PostToolUse`. Sets an EPHEMERAL, session-keyed touched-flag
    in $TMPDIR (never committed) — the no-op guard's "did this session write?" cue.

Visible-degradation guarantee: if the detector cannot be imported, the hook emits
a `glossary_capture_degraded` audit event first, then allows — a silent no-op
becomes a visible one.
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
NAME = "glossary_capture_nudge"
ALLOW_EXIT = 0


def _import_detector():
    """Insert the sibling scripts dir and import the detector. Raises ImportError
    when the chain is incomplete (handled by the degraded path)."""
    sd = str(Path(__file__).resolve().parent.parent / "scripts")
    if sd not in sys.path:
        sys.path.insert(0, sd)
    import glossary_capture  # noqa: E402 — resolved only after the path insert
    return glossary_capture


def _project_dir(stdin_cwd: Optional[str] = None) -> Optional[str]:
    return hook_runtime.project_dir(stdin_cwd)


def _enabled() -> bool:
    """A config-read failure falls to the SAFE nudge default: OFF."""
    try:
        return hook_runtime.hook_enabled(NAME, HOOK_CLASS)
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Ephemeral, session-keyed flags ($TMPDIR — not committed).
# ---------------------------------------------------------------------------

def _temp_dir() -> Path:
    """Read $TMPDIR fresh each call (tempfile caches its first read, which breaks
    per-test TMPDIR isolation)."""
    return Path(os.environ.get("TMPDIR") or tempfile.gettempdir())


def safe_id(session_id: str) -> str:
    return hook_runtime.safe_session_id(session_id)


def _flag_path(session_id: str) -> Path:
    return _temp_dir() / ("harness-glosscap-touched-%s" % safe_id(session_id))


def _throttle_path(session_id: str) -> Path:
    return _temp_dir() / ("harness-glosscap-nudged-%s" % safe_id(session_id))


def set_touched_flag(session_id: str) -> Path:
    """Mark "this session wrote something". Ephemeral; best-effort."""
    path = _flag_path(session_id)
    try:
        path.write_text("1", encoding="utf-8")
    except OSError:
        pass
    return path


def touched_flag_set(session_id: str) -> bool:
    return _flag_path(session_id).exists()


def _already_nudged(session_id: str) -> bool:
    return _throttle_path(session_id).exists()


def _mark_nudged(session_id: str) -> None:
    try:
        _throttle_path(session_id).write_text("1", encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Advisory text + observation note
# ---------------------------------------------------------------------------

def _advisory_text(signal: Dict[str, Any]) -> str:
    terms = signal.get("terms") or []
    total = signal.get("total", len(terms))
    shown = ", ".join(terms)
    if total > len(terms):
        shown += " (+%d more)" % (total - len(terms))
    dec = signal.get("dec") or "a DEC"
    return ("glossary-capture: %s coins term(s) not yet in the glossary: %s. "
            "Run /hs:remember (or glossary_register.py --add) to gloss them. "
            "Advisory only." % (dec, shown))


def _observation_note(signal: Dict[str, Any]) -> str:
    terms = signal.get("terms") or []
    return "uncaptured_term×%d (%s) — %s" % (
        signal.get("total", len(terms)), signal.get("dec", ""), ", ".join(terms))


def _trace_degraded(actor: str, session_id: str, exc: Exception) -> None:
    try:
        trace_log.append_event(hook=NAME, event="glossary_capture_degraded",
                               actor=actor, session=session_id,
                               status="degraded", note=str(exc)[:200])
    except Exception:  # noqa: BLE001
        pass


def _record_observation(actor: str, session_id: str, signal: Dict[str, Any]) -> None:
    try:
        # The event name MUST be `NAME + "_observation"`. This hook is not one of the
        # five bespoke families in nudge_context_inject, so the reader derives the name it
        # looks for from this hook's channel key in nudge-channels.yaml — i.e. NAME. It
        # used to write "glossary_capture_observation" (no `_nudge`), which nothing ever
        # read: the advisory fired, recorded, throttled, and reached nobody, silently.
        # Trace records already on disk under the old name stay unread, which is exactly
        # what they always were — no migration needed.
        # Do not shorten this literal. test_nudge_observation_names_are_read.py sweeps
        # every hook for this class of mismatch.
        trace_log.append_event(hook=NAME, event="glossary_capture_nudge_observation",
                               actor=actor, session=session_id,
                               status="observed", note=_observation_note(signal))
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def handle_stop(payload: Dict[str, Any], project_dir: Optional[str] = None) -> int:
    """Run the Stop policy: surface a signal as an advisory + record an observation,
    once per session. Always returns ALLOW_EXIT (nudge never blocks)."""
    if not _enabled():
        return ALLOW_EXIT
    project_dir = project_dir or _project_dir(payload.get("cwd"))
    if not project_dir:
        return ALLOW_EXIT

    session_id = payload.get("session_id") or ""
    # No-op guard: only run when this session actually wrote something.
    if not touched_flag_set(session_id):
        return ALLOW_EXIT
    # Throttle: one advisory per session.
    if _already_nudged(session_id):
        return ALLOW_EXIT

    actor = hook_runtime.resolve_actor(session_id)

    try:
        detector = _import_detector()
    except ImportError as exc:
        _trace_degraded(actor, session_id, exc)
        return ALLOW_EXIT

    try:
        signal = detector.collect(project_dir)
    except Exception as e:  # noqa: BLE001 — advisory: never break turn-end
        hook_runtime.log_hook_error(NAME, e)
        return ALLOW_EXIT

    if signal:
        hook_runtime.route_relay_nudge(
            NAME, _advisory_text(signal),
            lambda: _record_observation(actor, session_id, signal))
        _mark_nudged(session_id)
    return ALLOW_EXIT


def handle_post_tool_use(payload: Dict[str, Any],
                         project_dir: Optional[str] = None) -> int:
    """Set the touched-flag when a Write/Edit/MultiEdit landed a file_path."""
    if not _enabled():
        return ALLOW_EXIT
    tool_input = payload.get("tool_input")
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if isinstance(file_path, str) and file_path:
        set_touched_flag(payload.get("session_id") or "")
    return ALLOW_EXIT


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
