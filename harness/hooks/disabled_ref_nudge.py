#!/usr/bin/env python3
"""disabled_ref_nudge.py — advisory pointer for a ref to an install-disabled skill (nudge class).

After the 2.0.0 collapse every skill lives in one `hs` plugin and a fresh install can
omit skills at the dir level (the only disable that works for plugin skills). A handoff
that names `hs:<skill>` while that skill was omitted at install is NOT a broken
reference — the contract still stands. This nudge spots such a reference in the session
context and suggests the three ways forward: run it through the `/hs:use` proxy, read it
inline from the stash, or re-enable the skill.

Detection needs only the install-recorded omit list (harness/state/install-omitted-skills.json)
— never a skill->group map. The 13-skill spine is never omittable, so a spine ref never
trips this; a still-installed skill is silent too.

Nudge posture: advisory, fail-open, ALWAYS exit 0 — it writes at most one reminder line
to stderr and never blocks. The binding HOOK_CLASS lives here in code, not in config.
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

HOOK_CLASS = "nudge"
_NAME = Path(__file__).stem

# hs:<skill> — the single-plugin invoke form (optional leading '/'). The negative
# lookbehind (no word-char, '.', '/' or '-' before) keeps it from matching inside a
# longer token or a URL/domain (www.hs:x, //hs:x). hs-<group>: no longer exists.
_REF_RE = re.compile(r"(?<![\w./-])/?hs:([a-z][\w-]*)")


def _project_dir() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())


def _omitted_skills() -> set:
    """Skills this install deliberately omitted (the dir-omit disable for the single
    hs plugin), read from harness/state/install-omitted-skills.json under the project
    dir. Missing/invalid -> empty set: nothing omitted, a harmless silent pass
    (fail-open). A dogfood/dev tree carries no omit record and never nudges."""
    import omit_record
    return omit_record.read_omitted(_project_dir())


def _scan_refs(data) -> set:
    """Every hs:<skill> reference anywhere in the payload (recursive)."""
    found: set = set()

    def walk(v):
        if isinstance(v, str):
            found.update(_REF_RE.findall(v))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)

    walk(data)
    return found


def core(data: dict):
    """Return one advisory line iff the context references an install-disabled
    (omitted) skill. The spine and every still-installed skill stay silent."""
    refs = _scan_refs(data if isinstance(data, dict) else {})
    if not refs:
        return None
    omitted = _omitted_skills()
    off = sorted(s for s in refs if s in omitted)
    if not off:
        return None
    examples = "; ".join(f"hs:{s}" for s in off[:3])
    use_list = "; ".join(f"/hs:use {s}" for s in off[:3])
    enable_list = " ".join(f"--enable {s}" for s in off[:3])
    return (
        f"disabled-skill ref: {examples} — skill(s) are install-disabled (omitted). "
        f"Three ways forward: run the proxy `{use_list}` (loads + runs it from stash); "
        f"or read harness/plugins/hs/disabled-skills/<skill>/SKILL.md and perform it inline; "
        f"or re-enable with `hs-cli skills {enable_list}`. "
        f"The handoff still stands — do not drop it."
    )


def main() -> int:
    hook_runtime.run_nudge_hook(_NAME, core)
    return 0


if __name__ == "__main__":
    sys.exit(main())
