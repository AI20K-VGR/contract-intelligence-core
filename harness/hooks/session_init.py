#!/usr/bin/env python3
"""session_init.py — SessionStart hook (telemetry-class).

Resolves the acting identity once per session and caches it in
state/sessions/<session_id>.json so later hooks in the same session resolve
the SAME actor through resolve_actor(session_id=...) instead of re-reading a
possibly-changed environment. The cache is an optimization, never a
prerequisite: hooks fall back to the env chain when this never ran.

Also garbage-collects leaked rule_nudge dedup markers (see
_gc_stale_nudge_markers). Emits a session_start audit event.
"""

import json
import os
import shlex
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "install"))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "scripts"))
import hook_runtime  # noqa: E402
import trace_log     # noqa: E402
import harness_paths  # noqa: E402

HOOK_CLASS = "telemetry"

# rule_nudge_hook (and ten sibling nudge hooks: nudge_dedupe, memory_gap_hook,
# standards_drift_nudge, decision_capture_nudge, glossary_capture_nudge,
# backlog_capture_nudge, goal_cycle_nudge, auto_decision_review_nudge /
# auto_decision_log, decision_reconcile_nudge, engine_skew_nudge) each write
# their own $TMPDIR/harness-<family>-* dedup/touch flag but never unlink it, so
# every family leaks until a reboot. GC them here by mtime TTL: orphans from
# dead sessions are the bulk of the rot, and only a TTL sweep reclaims them (a
# delete-my-own-session pass cannot). Sweeps the SHARED "harness-" prefix — not
# one hard-coded family glob — so a newly added marker family is covered
# automatically instead of silently re-leaking.
_NUDGE_MARKER_GLOB = "harness-*"

# HARNESS_* vars that are normal plumbing (identity, test seams for state &
# log placement), not posture overrides worth an audit event.
_BASELINE_ENV = frozenset({
    "HARNESS_USER", "HARNESS_AGENT", "HARNESS_STATE_DIR",
    "HARNESS_HOOK_LOG_DIR", "HARNESS_ROOT",
    # Where the rule conflict audit caches its record. Placement, not posture:
    # the record is derived from committed rule files and changing its location
    # changes no decision. The test suite sets it per run so the 17s cold audit
    # is paid once rather than per test.
    "HARNESS_RULE_AUDIT_CACHE_DIR",
})


def _gc_stale_nudge_markers(now=None, ttl_hours: float = 24) -> int:
    """Unlink rule_nudge dedup markers older than ttl_hours; return the count
    removed. Telemetry-class: never raises — a missing TMPDIR, an unreadable
    stat, or a permission-denied unlink is swallowed per-file and the sweep
    continues. `now`/`ttl_hours` are injectable for deterministic tests."""
    removed = 0
    try:
        tmp = Path(os.environ.get("TMPDIR") or tempfile.gettempdir())
        cutoff = (now if now is not None else time.time()) - ttl_hours * 3600
        for marker in tmp.glob(_NUDGE_MARKER_GLOB):
            try:
                if marker.stat().st_mtime < cutoff:
                    marker.unlink()
                    removed += 1
            except OSError:
                continue  # vanished, unreadable, or denied — skip, keep sweeping
    except OSError:
        pass  # TMPDIR itself unreadable — no-op
    return removed


def _override_names() -> list:
    """Names (never values — values can carry paths/secrets; the audit
    question is only WHICH knobs were set) of HARNESS_* posture overrides
    present at session start. Snapshot semantics: an override exported
    mid-session is not seen — this is start-of-session visibility, not
    continuous monitoring."""
    return sorted(k for k in os.environ
                  if k.startswith("HARNESS_") and k not in _BASELINE_ENV)


def _seed_env_file() -> bool:
    """Append 'export HARNESS_DATA_ROOT=<data_root>' to $CLAUDE_ENV_FILE so a
    later Bash-tool subprocess (whose env carries no CLAUDE_PROJECT_DIR) can
    resolve the project data home. Migration net for a project installed before
    the installer wired this env; fail-soft when CLAUDE_ENV_FILE is absent
    (older Claude Code) and never seeds the fail-closed sentinel. Idempotent:
    skips the append when the export line is already present (a resume/clear/
    compact re-fires SessionStart against the same file). Returns True when it
    appended, False on any no-op. Seeds ONLY HARNESS_DATA_ROOT — never
    CLAUDE_PROJECT_DIR. Uses the STRICT data_root() (a hook is a trust
    boundary; the tool-context resolver is banned here)."""
    env_file = os.environ.get("CLAUDE_ENV_FILE")
    if not env_file:
        return False
    dr = harness_paths.data_root()
    if harness_paths.data_root_unresolved(dr):
        return False
    line = "export HARNESS_DATA_ROOT=%s" % shlex.quote(str(dr))
    # guard-read: skip if this export is already present (idempotent on resume)
    try:
        existing = Path(env_file).read_text(encoding="utf-8")
    except OSError:
        existing = ""
    if "export HARNESS_DATA_ROOT=" in existing:
        return False
    with open(env_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return True


def core(data: dict) -> None:
    session_id = data.get("session_id")
    actor = hook_runtime.resolve_actor()  # env chain — this IS the cache fill
    if session_id:
        d = hook_runtime._state_dir() / "sessions"
        d.mkdir(parents=True, exist_ok=True)
        (d / ("%s.json" % hook_runtime._safe_session_id(session_id))).write_text(
            json.dumps({
                "actor": actor,
                "ts": datetime.now(timezone.utc).isoformat(),
            }, ensure_ascii=False),
            encoding="utf-8",
        )
    trace_log.append_event(hook="session_init", event="session_start",
                           actor=actor, session=session_id)
    overrides = _override_names()
    if overrides:
        # Audit-class posture data → trace (never rotates); telemetry's 8MB
        # rotation would eventually erase the evidence.
        trace_log.append_event(hook="session_init", event="env_override_seen",
                               actor=actor, session=session_id,
                               note=", ".join(overrides))
    # Reclaim leaked nudge markers (telemetry, fail-open — never blocks start).
    _gc_stale_nudge_markers()
    # Reclaim stale per-session state (sessions/, nudge-inject/, skip-marks/) by
    # mtime TTL, throttled to once a day. Fail-open telemetry — a GC error, a
    # missing script, or an unresolved state dir must never block session start.
    try:
        sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
        import session_gc
        session_gc.gc_if_due()
    except Exception:
        pass
    # First-run data-home safety net: seed the project .harness/ skeleton when a
    # fresh clone never bootstrapped it (the installer seeds it at install time;
    # this covers a project cloned onto a new machine where the gitignored
    # .harness/ never came along). Fail-open telemetry — a write error, an
    # unresolved root, or a missing install module must never block session start.
    try:
        import bootstrap
        bootstrap.ensure_current_project()
    except Exception:
        pass
    # Migration net for a project installed before HARNESS_DATA_ROOT env-wiring
    # existed: seed it into $CLAUDE_ENV_FILE so a later Bash-tool subprocess
    # (whose env carries no CLAUDE_PROJECT_DIR) can still resolve the project
    # data home. Fail-open telemetry — never blocks session start.
    try:
        _seed_env_file()
    except Exception:
        pass


def main(raw=None) -> None:
    hook_runtime.run_telemetry_hook("session_init", core, raw=raw)


if __name__ == "__main__":
    main()
