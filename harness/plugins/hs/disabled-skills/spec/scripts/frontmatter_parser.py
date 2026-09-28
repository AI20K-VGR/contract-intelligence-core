#!/usr/bin/env python3
"""
frontmatter_parser — read a markdown artifact and return its YAML frontmatter,
body, and section map.

Tolerant: on parse failure returns a structured parse_error indicator instead
of raising, so the caller can emit a finding rather than crash.

CLI:
    frontmatter_parser.py <file>            # prints JSON to stdout
"""

import re
import sys
from pathlib import Path
from typing import Any, Dict

# yaml_io (the shared YAML reader/writer, harness/scripts/) is not on sys.path
# by default from a skill's scripts/ dir -- add it before importing. APPEND
# (never insert at 0): this skill directory also has its OWN encoding_utils.py
# / spec_graph.py, distinct modules with the SAME names as the harness/scripts
# copies -- prepending harness/scripts would shadow the local ones and resolve
# imports to the wrong copy (see harness/tests/_spec_skill_import.py's
# docstring for the exact hazard this avoids).
_HARNESS_SCRIPTS = str(Path(__file__).resolve().parents[5] / "scripts")
if _HARNESS_SCRIPTS not in sys.path:
    sys.path.append(_HARNESS_SCRIPTS)
import yaml_io

from encoding_utils import configure_utf8_console, dumps_json, read_text_utf8

configure_utf8_console()


# Mirrors harness/scripts/frontmatter_parser.py — see the reasoning there. Two
# things the earlier expression got wrong: it consumed the block's trailing
# newline (so YAML never saw the last line break of a block scalar), and it did
# not accept `...`, YAML's document-end marker, so a file the standards gate read
# fine was rejected here as malformed.
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?\n)(?:---|\.\.\.)\s*\n?(.*)$", re.DOTALL)
SECTION_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def parse_file(path: Path) -> Dict[str, Any]:
    """Parse a markdown artifact file.

    Returns a dict:
        {
          "ok": bool,
          "file": "<path>",
          "frontmatter": {...} | None,
          "body": "<markdown body>",
          "sections": {<heading>: <section text>, ...},
          "error": "<message>" | None
        }
    """
    p = Path(path)
    result: Dict[str, Any] = {
        "ok": False,
        "file": str(p),
        "frontmatter": None,
        "body": "",
        "sections": {},
        "error": None,
    }
    # A glob match that EXISTS but is not a regular file -- a FIFO, socket, char
    # device, or a symlink pointing at one (a committed `epics/EVIL.md` -> /dev/zero
    # is a valid git object, mode 120000) -- would BLOCK read_text_utf8 forever:
    # /dev/zero never EOFs, a FIFO waits for a writer that never comes. That hangs
    # every gate/visualizer that walks the tree (load_artifacts, strict_gate, ...).
    # is_file() follows the symlink but only stats (never reads), so it flags a
    # non-regular target WITHOUT blocking. Surface it as a parse_error -- the same
    # fail-soft shape a malformed file gets -- rather than handing it to read_text.
    # (A missing path stays FileNotFoundError below: exists() is False for it.)
    if p.exists() and not p.is_file():
        result["error"] = f"not a regular file (FIFO/socket/device excluded): {p}"
        return result
    try:
        text = read_text_utf8(p)
    except FileNotFoundError:
        result["error"] = f"file not found: {p}"
        return result
    except UnicodeDecodeError as exc:
        # A non-UTF-8 file raises UnicodeDecodeError (a ValueError subclass, NOT an
        # OSError); surface it as a parse_error so the graph build stays fail-soft
        # instead of crashing on the first byte that is not valid UTF-8.
        result["error"] = f"encoding error (not valid UTF-8): {exc}"
        return result
    except OSError as exc:
        result["error"] = f"read error: {exc}"
        return result

    return parse_text(text, file_label=str(p))


def parse_text(text: str, file_label: str = "<text>") -> Dict[str, Any]:
    """Parse raw markdown content (frontmatter + body)."""
    result: Dict[str, Any] = {
        "ok": False,
        "file": file_label,
        "frontmatter": None,
        "body": "",
        "sections": {},
        "error": None,
    }

    # Strip a leading UTF-8 BOM if present. Windows text editors (Notepad,
    # older VS Code presets) often save files with U+FEFF prefix, which
    # otherwise prevents the `---` frontmatter sentinel from matching at
    # column 0 and raises a misleading "no YAML frontmatter" error.
    if text.startswith("﻿"):
        text = text.lstrip("﻿")

    if not text.lstrip().startswith("---"):
        result["error"] = "no YAML frontmatter (file does not start with '---')"
        return result

    m = FRONTMATTER_RE.match(text.lstrip())
    if not m:
        # An empty block (`---\n---` or `---\n...`) HAS a closing fence but no
        # inner content, so the content-requiring regex misses it — report that
        # accurately instead of the misleading "missing closing '---'".
        if re.match(r"^---\s*\n(?:---|\.\.\.)\s*\n?", text.lstrip()):
            result["error"] = "frontmatter block is empty"
        else:
            result["error"] = "malformed YAML frontmatter (missing closing '---')"
        return result

    raw_fm, body = m.group(1), m.group(2)
    try:
        fm = yaml_io.safe_load(raw_fm) or {}
        if not isinstance(fm, dict):
            result["error"] = "frontmatter is not a YAML mapping"
            return result
    except Exception as exc:  # noqa: BLE001 — deliberate fail-soft
        # Any malformed frontmatter must degrade to a parse_error finding, never
        # crash the caller. PyYAML raises a whole family here, not just
        # yaml_io.YAMLError: a bare ValueError from the timestamp/int constructors
        # on an out-of-range `date: 2026-13-99`, and a bare AttributeError from
        # `construct_yaml_timestamp` on an explicit-tag `!!timestamp 'not a ts'`.
        # This is the ONE hardened frontmatter reader every other module routes
        # through, so the broad catch lives here (once) instead of a hand-tuned
        # exception list re-rolled at each call site (which kept missing a type).
        result["error"] = f"YAML parse error: {exc}"
        return result

    result["frontmatter"] = fm
    result["body"] = body
    result["sections"] = extract_sections(body)
    result["ok"] = True
    return result


def extract_sections(body: str) -> Dict[str, str]:
    """Map heading-text -> section content (until the next heading of any level).

    Consumed by the CLI (`main()` dumps the full result); the library callers
    (spec_graph etc.) read only frontmatter/body. Duplicate heading texts are
    disambiguated with a numeric suffix so a repeated heading does not silently
    overwrite an earlier section (the map was last-wins / lossy before)."""
    sections: Dict[str, str] = {}
    matches = list(SECTION_RE.finditer(body))
    for i, m in enumerate(matches):
        heading = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        content = body[start:end].strip()
        key = heading
        if key in sections:
            n = 2
            while f"{heading} ({n})" in sections:
                n += 1
            key = f"{heading} ({n})"
        sections[key] = content
    return sections


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: frontmatter_parser.py <file>", file=sys.stderr)
        return 2
    target = Path(sys.argv[1])
    result = parse_file(target)
    # dumps_json serializes YAML-typed values (a `datetime.date` from an ISO
    # date string) via `default=str` and fail-softs every hostile-hand-edit class
    # (exotic dict key, circular anchor, NaN/Inf) so this debug CLI degrades to
    # valid JSON + exit 0 rather than crashing, same as the checker CLIs.
    print(dumps_json(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
