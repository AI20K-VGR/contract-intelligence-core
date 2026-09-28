#!/usr/bin/env python3
"""discover_isolation_nudge.py — advisory /clear-before-plan reminder (nudge class).

Nudge the user to isolate context between discovery and planning. hs:discover
explores wide — research, divergent options, debate — and that carryover biases
planning toward a pre-baked solution. The handoff into hs:plan is the discovery
BRIEF, not the raw exploration, so a /clear between the two keeps planning honest.

This hook fires on the hs:plan invocation (PreToolUse:Skill) and, best-effort,
warns when hs:discover ran earlier in the SAME session_id — a signal the
discovery context was NOT cleared before planning. Sibling of
cook_isolation_nudge (same shape, next handoff up the SDLC chain).

Nudge posture: default OFF (config-gated), advisory, fail-open — it only writes a
reminder to stderr and ALWAYS continues (never exit 2). Best-effort by design:
session_id semantics across /clear are not empirically pinned for this host, so a
stale same-session match at worst prints one harmless advisory; a miss stays
silent. The binding HOOK_CLASS lives here in code, never in config.
"""

import os
import sys
from pathlib import Path

# Diagnostic text carries Vietnamese; guard stderr encoding so a non-UTF-8 locale
# degrades to replacement chars instead of raising mid-write (fail-open).
try:
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 — older streams / already-detached; never fatal
    pass

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HOOKS_DIR, "..", "scripts"))
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import hook_runtime  # noqa: E402

HOOK_CLASS = "nudge"
_NAME = Path(__file__).stem

_PLAN_SKILLS = {"hs:plan", "plan"}
_DISCOVER_SKILLS = {"hs:discover", "discover"}


def _incoming_skill(data: dict) -> str:
    """The skill the Skill tool is about to run (PreToolUse:Skill payload)."""
    if data.get("tool_name") == "Skill":
        inp = data.get("tool_input") or {}
        return str(inp.get("skill") or inp.get("name") or "")
    return ""


def _discover_in_session(session: str) -> bool:
    """Best-effort: was hs:discover logged for this session_id? Reads the
    telemetry invocations ledger read-only; any error → False (fail-open)."""
    if not session:
        return False
    try:
        import json

        from telemetry_paths import telemetry_dir, sink_read_files
        # Union legacy sink + per-session shards (P2) via the SSOT resolver.
        for ledger in sink_read_files(telemetry_dir(), "invocations.jsonl"):
            for line in ledger.read_text(encoding="utf-8").splitlines():
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("session") == session and rec.get("skill") in _DISCOVER_SKILLS:
                    return True
    except Exception:  # noqa: BLE001 — nudge is fail-open
        return False
    return False


def core(data: dict):
    """Return the advisory iff the incoming skill is hs:plan AND hs:discover ran in
    the same session (discovery context likely not cleared), else None. Routing is
    the caller's job via emit_nudge — never blocks."""
    if _incoming_skill(data) not in _PLAN_SKILLS:
        return None
    session = data.get("session_id") or os.environ.get("HARNESS_SESSION_ID") or ""
    if not _discover_in_session(session):
        return None
    return (
        "[nudge] discover_isolation: hs:discover already ran in this session — "
        "recommend /clear then /hs:plan with the locked BRIEF to isolate context "
        "(discovery-carryover biases the plan toward a predetermined solution). Advisory, non-blocking.\n"
    )


def main() -> int:
    # Nudge structure mirrors cook_isolation_nudge: honor the config gate, run the
    # detector fail-open, then route via emit_nudge (config sink) + ALWAYS
    # continue. A disabled hook is fully inert.
    if not hook_runtime.hook_enabled(_NAME, HOOK_CLASS):
        hook_runtime.emit_continue()
        return 0
    data = hook_runtime.read_stdin_json()
    d = data if isinstance(data, dict) else {}
    try:
        msg = core(d)
        if msg:
            hook_runtime.emit_nudge_and_continue(_NAME, msg, d)
            return 0
    except Exception as e:  # noqa: BLE001 — fail-open: a nudge never blocks the tool
        hook_runtime.log_hook_error(_NAME, e)
    hook_runtime.emit_continue()
    return 0


if __name__ == "__main__":
    sys.exit(main())
