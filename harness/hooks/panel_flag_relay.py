#!/usr/bin/env python3
"""panel_flag_relay.py — mechanical `--ultra`/`--debate` panel-flag detector
(UserPromptSubmit, telemetry-class, `kind: additionalContext`).

The 13 skills that carry `--ultra`/`--debate` (`argument-hint` + a Panel-mode
paragraph ordering a call to `hs:workflow-orchestrate`) rely on the model
reading that paragraph — the only dispatch mechanism a Claude Code skill has.
This hook adds a SECOND, independent layer above the skill body: a regex over
the raw prompt just submitted, so the panel directive reaches the model even
if a future edit strips the Panel-mode paragraph from the skill's own prose,
or the model's attention drifts past it in a long SKILL.md. Detection here is
mechanical (a compiled pattern match on `data["prompt"]`), not model judgment —
the injected text still has to be read and acted on (there is no channel in
Claude Code that executes a tool call without the model in the loop), but the
TRIGGER for surfacing it no longer depends solely on the skill body surviving
intact.

Fires only when BOTH a `/hs:<panel-skill>` reference AND an `--ultra`/`--debate`
token appear in the same submitted prompt. `hs:cook` is deliberately excluded
(never carried the flag upstream; code-mutating, not the advisory panel shape)
— same exclusion as `test_ultra_debate_panel_routing.py`, kept as one fact in
one place rather than two lists that can drift.

Telemetry-class + fail-open (mirrors nudge_context_inject / disabled_ref_nudge):
advisory only, never blocks. Any error or malformed/missing prompt -> None
(silent no-op), never a raised exception past `core`.
"""
import os
import re
import sys
from pathlib import Path

try:
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 — older/detached streams; never fatal
    pass

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HOOKS_DIR, "..", "scripts"))
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import hook_runtime  # noqa: E402

HOOK_CLASS = "telemetry"
_NAME = Path(__file__).stem

# The 13 upstream skills that carry the flag (mirrors
# test_ultra_debate_panel_routing.py's _PANEL_SKILLS). `cook` stays excluded —
# see module docstring.
_PANEL_SKILLS = (
    "advise", "plan", "code-review", "brainstorm", "debug", "fix", "research",
    "scout", "review-pr", "test", "problem-solving", "agentize", "bootstrap",
)

# Negative lookbehind keeps this from matching inside a longer token or a URL
# (mirrors disabled_ref_nudge._REF_RE).
_SKILL_RE = re.compile(r"(?<![\w./-])/?hs:(%s)\b" % "|".join(_PANEL_SKILLS))
_FLAG_RE = re.compile(r"(?<![\w-])--(ultra|debate)\b")


def core(data: dict):
    """Return one additionalContext string iff the prompt names a panel-flag
    skill AND carries the flag; else None."""
    prompt = data.get("prompt") if isinstance(data, dict) else None
    if not isinstance(prompt, str) or not prompt:
        return None
    skill_hit = _SKILL_RE.search(prompt)
    flag_hit = _FLAG_RE.search(prompt)
    if not (skill_hit and flag_hit):
        return None
    skill = skill_hit.group(1)
    flag = "--" + flag_hit.group(1)
    # `--ultra` takes an optional panel size; `--debate` is store_true and exits 2
    # on `unrecognized arguments` if handed one. The directive is prose the model
    # retypes, so one template for both flags would hand it a command that dies.
    spelling = "--ultra [N]" if flag == "--ultra" else "--debate"
    return (
        "[panel-flag] mechanical detector matched `%s` with `/hs:%s` in the prompt "
        "just submitted (regex, independent of the skill body). Per hs:%s's own "
        "Panel-mode section: do not run %s's normal single pass — call "
        "`hs:workflow-orchestrate %s --run-id <slug>` to size + drive the panel, "
        "present it for approval, and let `hs:escalation-consultant` synthesize "
        "before %s proceeds."
        % (flag, skill, skill, skill, spelling, skill)
    )


def main() -> int:
    hook_runtime.run_nudge_hook(_NAME, core)
    return 0


if __name__ == "__main__":
    sys.exit(main())
