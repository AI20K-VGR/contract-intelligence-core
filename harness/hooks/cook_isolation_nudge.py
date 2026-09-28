#!/usr/bin/env python3
"""cook_isolation_nudge.py — advisory /clear-before-cook reminder (nudge class).

Nudge the user to
isolate context between planning and implementation. The source fires on the Plan
SUBAGENT Stop and prints the absolute plan path so a post-/clear session can find
it. The harness runs hs:plan in the MAIN session (no plan subagent), so this hook
fires on the hs:cook invocation (PreToolUse:Skill) and, best-effort, warns when
hs:plan ran earlier in the SAME session_id — a signal the planning context was
NOT cleared before cooking.

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

_COOK_SKILLS = {"hs:cook", "cook"}
_PLAN_SKILLS = {"hs:plan", "plan"}


def _incoming_skill(data: dict) -> str:
    """The skill the Skill tool is about to run (PreToolUse:Skill payload)."""
    if data.get("tool_name") == "Skill":
        inp = data.get("tool_input") or {}
        return str(inp.get("skill") or inp.get("name") or "")
    return ""


def _plan_in_session(session: str) -> bool:
    """Best-effort: was hs:plan logged for this session_id? Reads the telemetry
    invocations ledger read-only; any error → False (fail-open, never raises)."""
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
                if rec.get("session") == session and rec.get("skill") in _PLAN_SKILLS:
                    return True
    except Exception:  # noqa: BLE001 — nudge is fail-open
        return False
    return False


def core(data: dict):
    """Return the advisory iff the incoming skill is hs:cook AND hs:plan ran in the
    same session (planning context likely not cleared), else None. Routing is the
    caller's job via emit_nudge — never blocks."""
    if _incoming_skill(data) not in _COOK_SKILLS:
        return None
    session = data.get("session_id") or os.environ.get("HARNESS_SESSION_ID") or ""
    if not _plan_in_session(session):
        return None
    return (
        "[nudge] cook_isolation: hs:plan already ran in this session — recommend "
        "/clear then /hs:cook <absolute-path> to isolate context "
        "(planning-carryover pulls cook off-focus). Advisory, non-blocking.\n"
    )


def main() -> int:
    # Nudge structure mirrors memory_gap_hook: honor the config gate, run the
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
