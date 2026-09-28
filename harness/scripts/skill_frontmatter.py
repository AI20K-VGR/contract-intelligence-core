#!/usr/bin/env python3
"""skill_frontmatter.py — the one tolerant SKILL.md frontmatter reader.

Eight scripts had each re-derived the same `---` fence scan; this is the single
source. `split` returns the raw block + body (writers/regex callers), `frontmatter`
parses the block to a dict, `description`/`body` pull the two fields most callers
want. All accept the raw markdown TEXT (read the file first) and are fail-soft: no
leading fence, no closing fence, or unparseable YAML yields {} / "".

Close markers: both the `---` fence and YAML's `...` document-end marker are honored,
whichever comes first — so body prose after a `...` close never folds into the block.
Folded/literal scalars (`description: >`) survive via PyYAML; a regex fallback covers
a yaml-less environment (single-line values only, folded values collapse to `>`).
"""
from __future__ import annotations

import re

try:
    import yaml_io as _yaml
    _YAML = True
except ImportError:  # PyYAML is a hard dep in practice; fallback pins the degraded shape
    _YAML = False

_DESC_RE = re.compile(r"(?m)^description:\s*(.+?)\s*$")


def split(md: str):
    """(block_text, body_text). (None, md) when there is no leading `---` or no
    closing fence — the two cases where there is no valid frontmatter block.

    block_text is the raw text between the fences (leading newline included);
    body_text is everything after the closing fence line."""
    if not md.startswith("---"):
        return None, md
    ends = [e for e in (md.find("\n---", 3), md.find("\n...", 3)) if e != -1]
    if not ends:
        return None, md
    end = min(ends)
    nl = md.find("\n", end + 1)
    return md[3:end], (md[nl + 1:] if nl != -1 else "")


def frontmatter(md: str) -> dict:
    """The leading YAML frontmatter as a dict; {} when absent/unparseable (fail-soft)."""
    block, _ = split(md)
    if block is None:
        return {}
    if _YAML:
        try:
            data = _yaml.safe_load(block)
            return data if isinstance(data, dict) else {}
        except Exception:  # noqa: BLE001 — malformed block degrades to the regex scan
            pass
    out: dict = {}
    for line in block.splitlines():
        if not line or line[:1].isspace() or line.startswith("#"):
            continue  # skip blanks + nested/indented + comment lines
        if ":" in line:
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip().strip("\"'")
    return out


def description(md: str) -> str:
    """The `description` field, stripped; "" when absent. Folded scalars survive via
    the parsed dict; the regex fallback covers the yaml-less path (single-line only)."""
    val = frontmatter(md).get("description")
    if val is not None:
        return str(val).strip()
    block, _ = split(md)
    if block:
        m = _DESC_RE.search(block)
        if m:
            return m.group(1).strip().strip("\"'")
    return ""


def body(md: str) -> str:
    """Everything after the leading frontmatter block; the whole text when there is
    no valid block. Fail-soft."""
    return split(md)[1]
