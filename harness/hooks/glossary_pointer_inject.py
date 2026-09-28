#!/usr/bin/env python3
"""glossary_pointer_inject.py — SessionStart hook (telemetry-class) injecting a
one-line pointer at the glossary as additionalContext.

Kept SEPARATE from voice_inject (single responsibility, fail-open): it reads the
glossary SSOT (docs/glossary.yaml), counts the settled terms, and emits a short
additionalContext reminding the session to consult the vocabulary before naming
things. Re-fires on /compact (source=compact) — the right cadence for a
persistent register.

This is SessionStart additionalContext, NOT a Stop re-inject: it decorates the
next turn only and never forces an extra turn, so it cannot trigger the Stop-hook
runaway — safe to default ON.

Telemetry posture: default ON, fail-open. On any error — or when telemetry is
disabled (HARNESS_TELEMETRY_DISABLED), the hook is off, or there is no glossary —
it emits no context (a plain continue), never a block. The emit logic lives here
rather than in the shared hook_runtime so the protected runtime stays untouched.
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
import hook_runtime    # noqa: E402

HOOK_CLASS = "telemetry"
NAME = "glossary_pointer_inject"


def _project_root(data: dict) -> Optional[str]:
    """The project root that holds docs/glossary.yaml. CLAUDE_PROJECT_DIR (set by
    the host) wins; the SessionStart stdin `cwd` is the fallback."""
    return os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or None


def _build(data: dict) -> Optional[str]:
    """Build the pointer line via the sibling script (DRY — the count + wording
    live in glossary_pointer). Returns None when there is nothing to surface."""
    root = _project_root(data)
    if not root:
        return None
    import glossary_pointer  # resolved after the scripts-dir path insert
    return glossary_pointer.build_pointer(root)


def _emit_context(text: str) -> None:
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": text,
        }
    }))
    sys.stdout.flush()


def run(raw=None) -> None:
    """Telemetry-class + fail-open pointer injector. Enabled + a glossary present
    → build + emit; disabled / no glossary / any exception → plain continue."""
    data = hook_runtime.read_stdin_json() if raw is None else hook_runtime._parse(raw)
    try:
        if hook_runtime.hook_enabled(NAME, HOOK_CLASS):
            text = _build(data)
            if text:
                _emit_context(text)
                return
    except Exception as e:  # noqa: BLE001 — injection must never break the session
        hook_runtime.log_hook_error(NAME, e)
    hook_runtime.emit_continue()


def main(raw=None) -> None:
    run(raw=raw)


if __name__ == "__main__":
    main()
