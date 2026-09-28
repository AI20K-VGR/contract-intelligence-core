#!/usr/bin/env python3
"""descriptive_name.py — advise against generic file names (nudge class).

PreToolUse:Write nudge. Fires when a NEW file is about to be written with a
low-information name (report.md / utils.js / temp.py) and suggests a descriptive
name plus the language naming convention. Default OFF (opt-in), advisory,
fail-open — it routes one advisory through the nudge sink (systemMessage per
nudge-channels.yaml) and ALWAYS continues, never blocks.

Why a detector, not CK's unconditional reminder: by PreToolUse the file_path is
already chosen, so a blanket naming reminder cannot influence THIS write. Flagging
the lazy name before it lands is the only PreToolUse-actionable form. Its real
value is the autonomous /goal path, where UserPromptSubmit context injection (the
usual home of the naming guidance) never fires — a PreToolUse hook still reaches.

Only Write is gated: Edit/MultiEdit touch an existing file whose name is already
settled. Exact-stem matching keeps false positives near zero — a descriptive name
that merely CONTAINS a generic word (security-report, data_pipeline) passes.
"""

import os
import sys
from pathlib import Path

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import hook_runtime  # noqa: E402

HOOK_CLASS = "nudge"
_NAME = Path(__file__).stem

# Low-information stems that almost always want a more descriptive name. Matched
# EXACTLY against the lowercased stem (no substring), so `report` is flagged but
# `triage-...-report` is not.
_GENERIC = frozenset({
    "report", "reports", "note", "notes", "data", "info", "output", "outputs",
    "result", "results", "temp", "tmp", "misc", "stuff", "untitled", "file",
    "files", "foo", "bar", "baz", "thing", "things", "script", "scripts",
    "doc", "docs", "test", "tests", "util", "utils", "helper", "helpers",
    "common", "sample", "samples", "demo", "final", "copy", "backup", "new",
    "code", "stuff2", "change", "changes", "update", "updates", "old",
})

# Conventional names that are CORRECT despite being short / generic-looking.
_ALLOW = frozenset({
    "index", "main", "__init__", "__main__", "conftest", "setup", "readme",
    "license", "licence", "changelog", "contributing", "makefile", "dockerfile",
    "manifest", "package", "tsconfig", "pyproject", "requirements", "gemfile",
    "rakefile", "mod", "go", "cargo", "build", "schema", "app", "server",
    "client", "cli", "types", "constants", "config",
})


def core(data):
    """Return an advisory message for a generic NEW-file name, else None."""
    if not isinstance(data, dict) or data.get("tool_name") != "Write":
        return None
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path.strip():
        return None

    basename = Path(file_path).name
    stem = Path(basename).stem.lower()
    if not stem or stem in _ALLOW:
        return None
    if stem not in _GENERIC:
        return None

    return (
        "%r is a generic file name — prefer a descriptive <type>-<topic> name "
        "(e.g. %s). Conventions: kebab-case (JS/TS/shell), snake_case "
        "(Python/Go/Rust), PascalCase (C#/Java)."
        % (basename, _suggestion(basename))
    )


def _suggestion(basename):
    """A concrete rename hint that keeps the original extension."""
    suffix = Path(basename).suffix
    return "auth-token-rotation%s" % (suffix or ".md")


def main():
    hook_runtime.run_nudge_hook(_NAME, core)
    return 0


if __name__ == "__main__":
    sys.exit(main())
