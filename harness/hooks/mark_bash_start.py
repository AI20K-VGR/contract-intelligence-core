#!/usr/bin/env python3
"""mark_bash_start.py — PreToolUse:Bash hook (telemetry-class).

Stamps a monotonic start mark for a harness-script Bash command so its
PostToolUse counterpart (track_script_execution.py) can compute wall-clock `ms`.

Only marks commands that run a harness/scripts/<f>.(py|sh) or harness/e2e/<f>.(py|sh)
in execution position — the same matcher PostToolUse uses (hook_runtime.SCRIPT_RE,
the single home so the Pre/Post pair never drifts) — so plain git/ls/grep never
create markers. If this Pre hook is missed, Post simply records without `ms`
(graceful degrade).

Fail-open + non-blocking + per-hook config gate are owned by the shared
hook_runtime.run_telemetry_hook wrapper (no-op under HARNESS_TELEMETRY_DISABLED /
pytest / config-disabled); this file holds only the mark-specific logic.

Hook stdin protocol: { tool_name, tool_input: { command }, session_id }.
"""

import os
import sys
from pathlib import Path

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_LIB_DIR = os.path.join(_HOOKS_DIR, "..", "scripts")
sys.path.insert(0, _LIB_DIR)
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import hook_runtime  # noqa: E402

HOOK_CLASS = "telemetry"

# Shared matcher (single home in hook_runtime) so the Pre/Post Bash pair can
# never drift out of lockstep.
SCRIPT_RE = hook_runtime.SCRIPT_RE

_STEM = Path(__file__).stem


def core(data: dict) -> None:
    from telemetry_paths import write_bash_start  # lazy: skipped when disabled
    tool_input = data.get("tool_input") or {}
    cmd = tool_input.get("command") or ""
    if SCRIPT_RE.search(cmd):
        session = data.get("session_id") or os.environ.get("HARNESS_SESSION_ID") or ""
        write_bash_start(session, cmd)


def main(raw=None) -> None:
    hook_runtime.run_telemetry_hook(_STEM, core, raw=raw)


if __name__ == "__main__":
    main()
