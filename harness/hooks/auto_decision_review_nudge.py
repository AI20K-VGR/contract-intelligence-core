#!/usr/bin/env python3
"""auto_decision_review_nudge — Stop nudge for unreviewed must-review auto-decisions.

The B-leg of the auto-decision ledger. On turn-end it counts the must_review-basket
decisions (ARCH/DEC-FLIP/SCOPE/SECURITY) still unreviewed in the active plan's ledger (+
the session reports fallback); if >0 it surfaces ONE advisory pointing at the view and the
mark-reviewed command, then ALWAYS allows. It owns no detection logic — it folds the
JSONL via auto_decision_log and reads the closed-vocab basket map.

Class is `nudge` (default OFF): stays asleep until an operator enables it in
harness-hooks.yaml. It surfaces via route_relay_nudge (stderr/systemMessage) and NEVER emits
hookSpecificOutput.additionalContext on Stop — that re-invokes the model and runs the loop
away (LESSONS.md). Fail-open; a broken fold chain degrades VISIBLY (a trace event), never a
silent no-op.

Two ephemeral $TMPDIR flags kill the noise:
  - touched  (set by the sink on a real append, keyed on the STORE PATH — the sink runs in
    the Bash-tool env with no session id, so a session-keyed marker would never match this
    reader's hook-env session): count only a ledger an auto-mode actually wrote.
  - surfaced (set here after one surface, keyed on the session — safe, both ends are hook
    env): at most once per session.
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
NAME = "auto_decision_review_nudge"
ALLOW_EXIT = 0

_MUST_REVIEW_LABELS = ("ARCH", "DEC-FLIP", "SCOPE", "SECURITY")  # advisory-text hint only


# --------------------------------------------------------------------------- imports / config
def _import_log():
    """Insert the sibling scripts dir and import the sink lib (fold_state + basket map).
    Raises ImportError when the chain is incomplete — the caller degrades visibly."""
    sd = str(Path(__file__).resolve().parent.parent / "scripts")
    if sd not in sys.path:
        sys.path.insert(0, sd)
    import auto_decision_log
    return auto_decision_log


def _enabled() -> bool:
    """A config-read failure falls to the SAFE nudge default: OFF (do nothing)."""
    try:
        return hook_runtime.hook_enabled(NAME, HOOK_CLASS)
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------------- ephemeral flags
def _temp_dir() -> Path:
    return Path(os.environ.get("TMPDIR") or tempfile.gettempdir())


def _safe(session: str) -> str:
    return hook_runtime.safe_session_id(session)


def _surfaced_flag(session: str) -> Path:
    # Set AND read by the nudge, both in the hook env (a real session id on both sides), so
    # unlike the sink's touched-flag this one may safely key on the session.
    return _temp_dir() / ("harness-adl-surfaced-%s" % _safe(session))


def _set_surfaced(session: str) -> None:
    try:
        _surfaced_flag(session).write_text("1", encoding="utf-8")
    except OSError:
        pass


# --------------------------------------------------------------------------- ledger resolve + count
def _resolve_stores(adl) -> List[Path]:
    """The JSONL stores to count, resolved the SAME way the sink resolves what it writes
    (git-common-dir → main tree, via auto_decision_log.resolve_ledger_stores). Sharing the
    resolver is what keeps the reader (hook env) and the writer (Bash-tool env) pointed at the
    same paths. Any resolve hiccup yields [] (fail-open), never raises."""
    try:
        return adl.resolve_ledger_stores()
    except Exception:  # noqa: BLE001
        return []


def count_unreviewed_must_review(stores: List[Path], adl) -> int:
    """Total must_review-basket decisions still unreviewed across the given stores. A store
    that is missing/unreadable folds to nothing (fail-open)."""
    must = {name for name, basket in adl.load_labels().items() if basket == "must_review"}
    total = 0
    for store in stores:
        for d in adl.fold_state(adl.load_events(store)):
            if not d.get("reviewed") and d.get("label") in must:
                total += 1
    return total


def _view_hint(stores: List[Path]) -> str:
    for store in stores:
        try:
            import auto_decision_render
            return str(auto_decision_render.md_path_for(store))
        except Exception:  # noqa: BLE001
            continue
    return "auto-decisions.md"


def _advisory_text(n: int, view_hint: str) -> str:
    return ("auto-decision ledger: %d quyết-định PHẢI-SOÁT chưa xem (%s). Soi: %s; "
            "đánh-dấu đã-soát: auto_decision_log.py --mark-reviewed <id>. Advisory only."
            % (n, "/".join(_MUST_REVIEW_LABELS), view_hint))


# --------------------------------------------------------------------------- trace
def _trace_degraded(actor: str, session: str, exc: Exception) -> None:
    try:
        trace_log.append_event(hook=NAME, event="auto_decision_review_degraded",
                               actor=actor, session=session,
                               status="degraded", note=str(exc)[:200])
    except Exception:  # noqa: BLE001
        pass


def _record_observation(actor: str, session: str, n: int) -> None:
    try:
        trace_log.append_event(hook=NAME, event="auto_decision_review_observation",
                               actor=actor, session=session,
                               status="observed", note="unreviewed_must_review×%d" % n)
    except Exception:  # noqa: BLE001
        pass


# --------------------------------------------------------------------------- handler
def handle_stop(payload: Dict[str, Any], project_dir: Optional[str] = None) -> int:
    """Surface the unreviewed must-review count as an advisory, at most once per session and
    only for a ledger that was actually written (its touched-flag is set). Always returns
    ALLOW_EXIT (nudge never blocks)."""
    if not _enabled():
        return ALLOW_EXIT
    session = payload.get("session_id") or ""
    # once per session (both set and read here, in the hook env → session key is safe).
    if _surfaced_flag(session).exists():
        return ALLOW_EXIT

    actor = hook_runtime.resolve_actor(session)
    try:
        adl = _import_log()
    except ImportError as exc:
        _trace_degraded(actor, session, exc)
        return ALLOW_EXIT

    try:
        stores = _resolve_stores(adl)
        # count only stores an auto-mode actually WROTE (touched, store-path-keyed) — an
        # interactive session over an old ledger it never touched must not nudge.
        touched = [s for s in stores if adl.touched_flag_set(s)]
        n = count_unreviewed_must_review(touched, adl)
    except Exception as e:  # noqa: BLE001 — advisory must never break turn-end
        hook_runtime.log_hook_error(NAME, e)
        return ALLOW_EXIT

    if n > 0:
        hook_runtime.route_relay_nudge(
            NAME, _advisory_text(n, _view_hint(touched)),
            lambda: _record_observation(actor, session, n))
        _set_surfaced(session)
    return ALLOW_EXIT


# --------------------------------------------------------------------------- CLI entry
def main(argv: Optional[List[str]] = None) -> int:
    payload = hook_runtime.read_stdin_json()
    project_dir = hook_runtime.project_dir(payload.get("cwd"))
    try:
        rc = handle_stop(payload, project_dir)
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
