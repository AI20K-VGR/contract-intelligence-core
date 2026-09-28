#!/usr/bin/env python3
"""engine_root_inject.py — SessionStart engine-root context (telemetry, fail-open).

Under the courier / global layout the engine no longer sits at `./harness` in the
working repo, so a prose read-ref like `harness/rules/output-rendering.md` cannot be
Read relative to the repo. This injects one additionalContext block naming the
resolved engine root so the model prefixes read-refs with it.

Self-host (HARNESS_BIN_ROOT UNSET): NO inject — the relative refs already resolve
from the repo root, exactly as today. A global layout whose root does not resolve
(deleted home / lost env) emits nothing here; engine_skew_nudge raises the advisory.

NUDGE-class (fail-open, never blocks), NOT telemetry: this inject is load-bearing
CONTEXT (it tells the model where the engine lives so read-refs resolve), so it
must survive the HARNESS_TELEMETRY_DISABLED kill-switch — which the DISPATCHER
applies by class (`hook_enabled(name, cls)` where cls comes from the dispatch map).
A telemetry class would be dropped there regardless of any run()-level bypass.
Dispatched via the SessionStart group (kind: additionalContext) — the dispatcher
takes this core's return value as the additionalContext. Default-OFF nudge class
is flipped ON in the shipped harness-hooks.yaml.
"""
import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
import hook_runtime  # noqa: E402

HOOK_CLASS = "nudge"
_NAME = "engine_root_inject"

_MARKERS = ("harness/manifest.json", "harness/hooks")


def _resolved_global_root():
    """The resolved engine root when the layout is global AND the root actually
    carries the harness markers; None for self-host or an unresolved root."""
    raw = os.environ.get("HARNESS_BIN_ROOT")
    if not raw:
        return None  # self-host — relative refs already correct
    try:
        root = Path(raw).resolve()
    except Exception:  # noqa: BLE001
        return None
    if not root.exists():
        return None
    if not any((root / m).exists() for m in _MARKERS):
        return None
    return root


def core(data: dict):
    root = _resolved_global_root()
    if root is None:
        return None
    return (
        "[engine] root=%s\n"
        "Read-refs like `harness/rules/...` and `harness/data/...` resolve against "
        "this engine root — prefix them with it when you Read a rule/data file."
        % root)


def run(raw=None) -> None:
    data = hook_runtime.read_stdin_json() if raw is None else hook_runtime._parse(raw)
    try:
        # nudge class -> the HARNESS_TELEMETRY_DISABLED kill-switch does NOT apply
        # here (it only forces telemetry off), so this context inject survives it.
        if hook_runtime.hook_enabled(_NAME, "nudge"):
            text = core(data if isinstance(data, dict) else {})
            if text:
                sys.stdout.write(_emit_blob(text))
                sys.stdout.flush()
                return
    except Exception as e:  # noqa: BLE001 — a context inject must never break the session
        hook_runtime.log_hook_error(_NAME, e)
    hook_runtime.emit_continue()


def _emit_blob(text: str) -> str:
    import json
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": text,
        }
    })


if __name__ == "__main__":
    run()
