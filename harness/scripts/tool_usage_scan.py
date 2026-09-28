#!/usr/bin/env python3
"""tool_usage_scan.py — high-confidence tool-usage detection for skills.

Verifies an authored `allowed-tools` does not OMIT a tool the skill clearly needs
(under-declaration silently breaks the skill at runtime). Precision over recall: only
unambiguous signals count, so the check never false-alarms.

Signals:
  Bash       -> the skill ships runnable scripts/ files, OR a ```bash fence, OR `Bash(`
  Task       -> a `Task(` call in the body
  WebSearch  -> a `WebSearch` mention
  WebFetch   -> a `WebFetch` mention

Usage:
  python3 harness/scripts/tool_usage_scan.py <skills-root>        # audit, JSON
"""

import argparse
import json
import re
import sys
from pathlib import Path

_SCRIPT_SUFFIXES = {".py", ".sh", ".js", ".ts", ".mjs", ".cjs", ".rb"}
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _read(skill_dir):
    p = Path(skill_dir) / "SKILL.md"
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def _body(text):
    m = _FM_RE.match(text)
    return text[m.end():] if m else text


def detect_required_tools(skill_dir) -> set:
    """High-confidence tools the skill needs. Precision-first (never guesses Read/Grep)."""
    d = Path(skill_dir)
    text = _read(skill_dir)
    body = _body(text)
    req = set()

    scripts = d / "scripts"
    has_script = scripts.is_dir() and any(
        p.suffix in _SCRIPT_SUFFIXES for p in scripts.rglob("*") if p.is_file())
    if has_script or re.search(r"```bash", body) or "Bash(" in body:
        req.add("Bash")
    if "Task(" in body:
        req.add("Task")
    if "WebSearch" in body:
        req.add("WebSearch")
    if "WebFetch" in body:
        req.add("WebFetch")
    return req


def declared_allowed_tools(skill_dir):
    """The declared allowed-tools as a set, or None when the field is absent."""
    text = _read(skill_dir)
    m = _FM_RE.match(text)
    if not m:
        return None
    try:
        import yaml_io
        fm = yaml_io.safe_load(m.group(1)) or {}
    except Exception:
        return None
    if "allowed-tools" not in fm:
        return None
    val = fm["allowed-tools"]
    if isinstance(val, str):
        return {t.strip() for t in val.split(",") if t.strip()}
    if isinstance(val, list):
        return {str(t).strip() for t in val}
    return set()


def _base_tool(spec) -> str:
    """The bare tool name of an allowed-tools entry: `Bash(git:*)` -> `Bash`."""
    return str(spec).split("(", 1)[0].strip()


def check_allowed_tools(skill_dir) -> list:
    """Findings: a declared allowed-tools that omits a high-confidence required tool."""
    declared = declared_allowed_tools(skill_dir)
    if declared is None:
        return []
    # Scoped entries (Bash(git:*)) satisfy the bare requirement — never false-alarm.
    declared = {_base_tool(t) for t in declared}
    required = detect_required_tools(skill_dir)
    missing = sorted(required - declared)
    return ["allowed-tools omits %s which the skill clearly uses" % t for t in missing]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", help="a skills root holding plugin/skill dirs")
    args = ap.parse_args(argv)
    out = {}
    for skill_md in sorted(Path(args.root).rglob("SKILL.md")):
        if "disabled-skills" in skill_md.parts:
            continue  # off-skill stash — a sibling of skills/, not a live skill
        d = skill_md.parent
        findings = check_allowed_tools(str(d))
        if findings:
            out[str(d)] = findings
    print(json.dumps({"under_declared": out, "count": len(out)}, indent=2))
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main())
