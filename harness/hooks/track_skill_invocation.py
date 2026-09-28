#!/usr/bin/env python3
"""track_skill_invocation.py — records every skill invocation to
state/telemetry/invocations.jsonl (telemetry-class).

Fail-open + non-blocking + config gate are owned by hook_runtime.run_telemetry_hook.
ONE config key (track_skill_invocation) gates BOTH registrations below.

A skill invocation reaches the hook on one of two events (both wired):
  - PreToolUse with tool_name "Skill"   → tool_input.skill | tool_input.name
    (the model invoking a skill via the Skill TOOL).
  - UserPromptExpansion (slash command) → command_name (the user typing /hs:*).
    The live payload carries a structured `command_name` ("hs:test") plus
    `command_args` / `expansion_type` / `command_source`; older hosts used a raw
    `command` string, still read as a fallback. This event fires only for
    skill/command expansion (built-ins like /goal do not fire it).
append_event_once collapses a same (session|skill|minute) double-fire to one
record, so a /hs:* that fires BOTH UserPromptSubmit-adjacent paths is logged once.

ADAPT note: the hook keys on the Skill TOOL NAME (and the command name) — it does
not filter on any skill-tree path-shape (the harness has no such tree; hs-* skills
are prose-only). Only env/import re-homing changed from the source.

Hook stdin protocol (either): { tool_name, tool_input, session_id, command_name,
command, hook_event_name }.
"""

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_LIB_DIR = os.path.join(_HOOKS_DIR, "..", "scripts")
sys.path.insert(0, _LIB_DIR)
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import hook_runtime  # noqa: E402

HOOK_CLASS = "telemetry"

_STEM = Path(__file__).stem


def extract_skill(data: dict):
    """Return (skill_name, via_label) from a hook payload dict."""
    # PreToolUse path: the Skill tool carries the skill name in tool_input.
    if data.get("tool_name") == "Skill":
        inp = data.get("tool_input") or {}
        skill = inp.get("skill") or inp.get("name") or ""
        return str(skill), "PreToolUse:Skill"
    # UserPromptExpansion path: the invoked command/skill name. The live host uses
    # the structured `command_name`; older hosts used a raw `command` string.
    if (data.get("command_name") or data.get("command")
            or data.get("hook_event_name") == "UserPromptExpansion"):
        raw = str(data.get("command_name") or data.get("command") or "").strip().lstrip("/")
        skill = re.split(r"\s+", raw)[0] if raw else ""
        return skill, "UserPromptExpansion"
    return "", ""


def core(data: dict) -> None:
    from telemetry_paths import append_event_once  # lazy: skipped when disabled
    skill, via = extract_skill(data)
    if not skill:
        return
    now = datetime.now(timezone.utc)
    session = data.get("session_id") or os.environ.get("HARNESS_SESSION_ID") or ""
    minute = now.strftime("%Y-%m-%dT%H:%M")  # YYYY-MM-DDTHH:MM dedup bucket
    # Dedup key: same skill in same session+minute → second call increments the
    # count rather than writing a duplicate row. Different skills or sessions never
    # collide (separate keys).
    append_event_once(
        "invocations.jsonl",
        {"ts": now.isoformat(), "skill": skill, "session": session, "via": via},
        "%s|%s|%s" % (session, skill, minute),
    )


def main(raw=None) -> None:
    hook_runtime.run_telemetry_hook(_STEM, core, raw=raw)


if __name__ == "__main__":
    main()
