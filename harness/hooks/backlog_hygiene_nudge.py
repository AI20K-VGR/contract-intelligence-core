#!/usr/bin/env python3
"""backlog_hygiene_nudge.py — advisory reminder to close stale open backlog items
before a publish stage (nudge class).

The failure mode: the backlog SSOT accrues `open` items that are actually done,
because closing them (`done`/`archive`) is a manual step easy to skip. They never
block anything, but they make the run-scoped bell query and the rendered view
noisy. This hook fires on a publish-adjacent skill (hs:ship / hs:git) and, when
there are open items, points at `backlog_register.py done|archive` to tidy them.

Nudge posture: advisory, fail-open — stderr only, ALWAYS continues (never exit
2). The binding HOOK_CLASS lives here in code, never in config; default OFF.
"""
import os
import sys
from pathlib import Path

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

# Publish-adjacent skills: the moments stale open items actually matter (the next
# bell query / rendered view will carry them). Cook is excluded — a mid-cook
# backlog legitimately holds open items for later.
_PUBLISH_SKILLS = {"hs:ship", "ship", "hs:git", "git"}


def _root() -> Path:
    # The project being worked on — under a global install HARNESS_ROOT
    # points at the shared bin, so prefer the project-dir resolver; keep the
    # HARNESS_ROOT/cwd fallback so the nudge never resolves to None.
    return Path(hook_runtime.project_dir() or os.environ.get("HARNESS_ROOT") or ".")


def _incoming_skill(data: dict) -> str:
    if data.get("tool_name") == "Skill":
        inp = data.get("tool_input") or {}
        return str(inp.get("skill") or inp.get("name") or "")
    return ""


def open_items(root=None):
    """Open backlog records, or [] on any read error (fail-open — a nudge never
    raises). Empty when the SSOT does not exist yet (pre-migration)."""
    root = Path(root) if root is not None else _root()
    try:
        import backlog_register
        return backlog_register.query(root, status="open")
    except Exception:  # noqa: BLE001 — nudge is fail-open
        return []


def core(data: dict):
    """Return the advisory iff a publish-adjacent skill is starting AND open
    backlog items exist, else None. Routing (stderr/systemMessage/relay/off) is
    the caller's job via emit_nudge — never blocks."""
    if _incoming_skill(data) not in _PUBLISH_SKILLS:
        return None
    items = open_items()
    if not items:
        return None
    return (
        "[nudge] backlog_hygiene: %d open backlog item(s) — close the ones now "
        "done before they clutter the next bell scan / rendered view:\n"
        "    python3 harness/scripts/backlog_register.py done --id <BL-NNN>\n"
        "    python3 harness/scripts/backlog_register.py archive --id <BL-NNN>\n"
        "Advisory, non-blocking.\n" % len(items)
    )


def main() -> int:
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
