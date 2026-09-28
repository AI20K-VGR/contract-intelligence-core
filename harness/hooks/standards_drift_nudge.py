#!/usr/bin/env python3
"""standards_drift_nudge — keep the auto-loaded prose standards from drifting.

`hs:plan` / `hs:cook` READ docs/system-architecture.md + docs/code-standards.md into
context before working. If the code they describe changes but those docs don't, the
loaded context silently drifts from reality → plans and code build on a stale map.
This is the event-triggered twin of decision_capture_nudge: a thin, deterministic
wrapper around the `standards_drift` detector (owns NO judgment).

Three events, one file — two complementary layers:

  EARLY WARNING (turn-end, session flag):
  - `--post-tool-use` → PostToolUse(Write|Edit|MultiEdit). Appends each edited
    file_path to an EPHEMERAL, session-keyed flag in $TMPDIR (never committed).
  - default          → Stop. Reads the edited paths, asks the detector "arch/standards
    code touched without a context doc?", surfaces a one-line advisory + records a
    `standards_drift_observation`, then CLEARS the flag (one nudge per batch of edits,
    quiet on idle turns).

  FINAL NET (commit, git truth):
  - `--commit`       → PreToolUse(Bash). When the command is a `git commit`, reads the
    STAGED diff (`git diff --cached`) and asks the same detector. This is the precise
    checkpoint: it judges exactly what this commit ships, from git rather than a
    session flag, so an unrelated doc edit earlier in the session cannot mask it. Records
    a `standards_drift_commit_observation`.

All legs are nudge-class, fail-open, NEVER block. Enable resolution (precedence):
HARNESS_STANDARDS_DRIFT_NUDGE env (truthy on / falsey off) when set, else
harness-hooks.yaml. Shipped default ON; nudge class default stays OFF so a clean
install is silent until the entry opts it in. A broken detector chain records a
`standards_drift_degraded` audit event instead of silently looking alive.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import hook_runtime  # noqa: E402
import trace_log     # noqa: E402

HOOK_CLASS = "nudge"
NAME = "standards_drift_nudge"
_ENV = "HARNESS_STANDARDS_DRIFT_NUDGE"
ALLOW_EXIT = 0


def _scripts_dir() -> str:
    return str(Path(__file__).resolve().parent.parent / "scripts")


def _import_detector():
    """Insert the sibling scripts dir and import the detector. Hook + detector ship
    together; raises ImportError when the chain is incomplete (degraded-path test)."""
    sd = _scripts_dir()
    if sd not in sys.path:
        sys.path.insert(0, sd)
    import standards_drift  # noqa: E402 — resolved only after the path insert
    return standards_drift


def _detect_stage(command: str) -> Optional[str]:
    """Stage of a Bash command via the shared stage_detector, or None on any failure
    (the commit leg degrades to 'not a commit').

    The literal-word prefilter below exists because this sits on the path of EVERY
    Bash command while its only caller asks one question — "is this a commit?".
    Importing the detector costs 6.99 ms cold against 0.0012 ms for the detection
    itself, so `ls` was paying seven milliseconds to be told no.

    Safe because the detector's commit pattern requires the literal word
    (stage_detector.py:95). Verified by running both paths over a command corpus
    rather than by asserting it — see test_standards_drift_nudge_prefilter.py.
    The compare is lowercased so the cheap side ERRS TOWARD importing: an extra
    import costs milliseconds, a missed detection costs a gate."""
    if not isinstance(command, str) or "commit" not in command.lower():
        return None
    try:
        sd = _scripts_dir()
        if sd not in sys.path:
            sys.path.insert(0, sd)
        import stage_detector  # noqa: E402
        return stage_detector.detect_stage(command)
    except Exception:  # noqa: BLE001 — a detection failure must never break the turn
        return None


def _enabled() -> bool:
    """HARNESS_STANDARDS_DRIFT_NUDGE override (truthy on / falsey off) when set, else
    harness-hooks.yaml. Any config-read failure falls to the SAFE nudge default OFF."""
    raw = os.environ.get(_ENV, "").strip().lower()
    if raw:
        return raw in ("1", "true", "yes", "on")
    try:
        return hook_runtime.hook_enabled(NAME, HOOK_CLASS)
    except Exception:  # noqa: BLE001
        return False


# --- Ephemeral, session-keyed path flag ($TMPDIR — not committed) -------------

def _temp_dir() -> Path:
    """Read $TMPDIR fresh each call (tempfile caches its first read, breaking
    per-test TMPDIR isolation)."""
    return Path(os.environ.get("TMPDIR") or tempfile.gettempdir())


def _flag_path(session_id: str) -> Path:
    return _temp_dir() / ("harness-stddrift-%s" % hook_runtime.safe_session_id(session_id))


def append_touched_path(session_id: str, file_path: str) -> None:
    """Record one edited path for this session. Best-effort — a write failure must
    never break the turn (the flag is an optimization, not a contract)."""
    try:
        with _flag_path(session_id).open("a", encoding="utf-8") as fh:
            fh.write(file_path + "\n")
    except OSError:
        pass


def read_touched_paths(session_id: str) -> List[str]:
    try:
        return [ln for ln in _flag_path(session_id).read_text(
            encoding="utf-8").splitlines() if ln.strip()]
    except OSError:
        return []


def clear_touched(session_id: str) -> None:
    """Drop the flag after a turn's judgment so the nudge re-fires only on NEW edits,
    not every idle turn-end. Best-effort."""
    try:
        _flag_path(session_id).unlink()
    except OSError:
        pass


# --- Staged-diff read (commit leg) -------------------------------------------

def staged_paths(project_dir: Optional[str]) -> List[str]:
    """Repo-relative paths in the staged index (`git diff --cached --name-only -z`).
    Degrades to [] (never raises) outside a git work tree or on any git failure —
    advisory is not an error."""
    if not project_dir:
        return []
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "-z"],
            cwd=project_dir, capture_output=True, text=True, timeout=5, check=False)
        if out.returncode != 0:
            return []
        return [p for p in out.stdout.split("\0") if p.strip()]
    except Exception:  # noqa: BLE001 — git missing/slow/not-a-repo → no signal
        return []


# --- Advisory + trace ---------------------------------------------------------

def _advisory_text(signal: Dict[str, Any], *, at_commit: bool = False) -> str:
    subjects = signal.get("subjects") or []
    total = signal.get("total", len(subjects))
    shown = ", ".join(subjects)
    if total > len(subjects):
        shown += " (+%d more)" % (total - len(subjects))
    lead = "this commit changes" if at_commit else "shipped"
    return ("standards-drift: %d architecture/standards code change(s) %s "
            "without touching docs/system-architecture.md or docs/code-standards.md "
            "(auto-loaded by hs:plan/hs:cook): %s. If this changed the architecture "
            "or a standard, run /hs:docs to resync. Advisory only." % (total, lead, shown))


def _trace(event: str, actor: str, session_id: str, **kw) -> None:
    try:
        trace_log.append_event(hook=NAME, event=event, actor=actor,
                               session=session_id, **kw)
    except Exception:  # noqa: BLE001 — audit write never breaks the turn
        pass


def _note(signal: Dict[str, Any]) -> str:
    return "%s — %s" % (signal.get("total"), ", ".join(signal.get("subjects", [])))


# --- Handlers -----------------------------------------------------------------

def handle_post_tool_use(payload: Dict[str, Any]) -> int:
    """Append the edited file_path to the session flag. Records state only."""
    if not _enabled():
        return ALLOW_EXIT
    tool_input = payload.get("tool_input")
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if isinstance(file_path, str) and file_path:
        append_touched_path(payload.get("session_id") or "", file_path)
    return ALLOW_EXIT


def handle_stop(payload: Dict[str, Any]) -> int:
    """Judge this turn's edited paths; surface + record on drift, then clear the flag.
    Always allows."""
    if not _enabled():
        return ALLOW_EXIT
    session_id = payload.get("session_id") or ""
    paths = read_touched_paths(session_id)
    if not paths:  # no-op guard: nothing edited since the last turn-end
        return ALLOW_EXIT

    actor = hook_runtime.resolve_actor(session_id)
    try:
        detector = _import_detector()
    except ImportError as exc:
        _trace("standards_drift_degraded", actor, session_id,
               status="degraded", note=str(exc)[:200])
        return ALLOW_EXIT

    try:
        signal = detector.assess(paths)
    except Exception as e:  # noqa: BLE001 — advisory must never break turn-end
        hook_runtime.log_hook_error(NAME, e)
        return ALLOW_EXIT

    if signal:
        # The observation trace records EVERY occurrence (full audit, per
        # nudge_dedupe.py:5-7's stated contract); the human-facing stderr/
        # systemMessage nudge is deduped per (session, subject) so a repeated
        # breach nudges ONCE. Mirrors memory_gap_hook.handle_stop:243-246 — the
        # trace call must NOT sit inside the dedupe branch, or a repeat drift on
        # an already-nudged subject records zero new audit observations.
        _trace("standards_drift_observation", actor, session_id,
               status="observed", note=_note(signal))
        import nudge_dedupe
        subs = signal.get("subjects") or []
        fresh = [x for x in subs if not nudge_dedupe.already_nudged(
            session_id, "standards_drift", x)]
        if fresh or not subs:
            # record_obs is a no-op here: the observation is already recorded
            # above, unconditionally — route_relay_nudge is used ONLY for its
            # {model,user} axis routing of the human-facing text.
            hook_runtime.route_relay_nudge(NAME, _advisory_text(signal), lambda: None)
            for x in subs:
                nudge_dedupe.mark_nudged(session_id, "standards_drift", x)
    clear_touched(session_id)
    return ALLOW_EXIT


def handle_commit(payload: Dict[str, Any]) -> int:
    """FINAL NET: at a `git commit`, judge the STAGED diff (git truth) so an unrelated
    earlier doc edit cannot mask a real drift. Advisory; never blocks the commit."""
    if not _enabled():
        return ALLOW_EXIT
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or _detect_stage(command) != "commit":
        return ALLOW_EXIT

    project_dir = hook_runtime.project_dir(payload.get("cwd"))
    paths = staged_paths(project_dir)
    if not paths:
        return ALLOW_EXIT

    session_id = payload.get("session_id") or ""
    actor = hook_runtime.resolve_actor(session_id)
    try:
        detector = _import_detector()
    except ImportError as exc:
        _trace("standards_drift_degraded", actor, session_id,
               status="degraded", note=str(exc)[:200])
        return ALLOW_EXIT

    try:
        signal = detector.assess(paths)
    except Exception as e:  # noqa: BLE001 — advisory must never block a commit
        hook_runtime.log_hook_error(NAME, e)
        return ALLOW_EXIT

    if signal:
        hook_runtime.route_relay_nudge(
            NAME, _advisory_text(signal, at_commit=True),
            lambda: _trace("standards_drift_commit_observation", actor, session_id,
                           status="observed", note=_note(signal)))
    return ALLOW_EXIT


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    payload = hook_runtime.read_stdin_json()
    if "--commit" in argv:
        handler = handle_commit
    elif "--post-tool-use" in argv:
        handler = handle_post_tool_use
    else:
        handler = handle_stop
    try:
        rc = handler(payload)
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
