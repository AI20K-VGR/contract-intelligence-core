#!/usr/bin/env python3
"""backlog_migrate — one-time migration of the hand-written BACKLOG.md into the
tool-written `docs/backlog.yaml` SSOT.

The single destructive write in the backlog work is the moment `render`
overwrites BACKLOG.md with the generated view. The archive guard makes that write safe: the
current BACKLOG.md is copied BYTE-EQUAL into `docs/BACKLOG-archive.md` BEFORE any
parse, and `apply_migration` REFUSES to flip unless that archive is still
byte-equal to the live file — so a parser bug or a mid-migration edit can never
lose the curated prose. Closed history (`- [x]`) stays in the archive verbatim;
only currently-open items (`- [ ]`) become records.

The migration is SEMI-automatic: `parse_open_items` proposes candidate records
(text/type/priority best-effort) for a human to review BEFORE `apply_migration`
adds them. The CLI prints the candidates and waits for an explicit `--apply`.

CLI:
    backlog_migrate.py --root <dir> --archive           # cp + assert byte-equal
    backlog_migrate.py --root <dir> --candidates        # print parsed open items
    backlog_migrate.py --root <dir> --apply             # archive(if needed)+flip
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import fs_guard  # noqa: E402
import backlog_register as br  # noqa: E402


class MigrationError(RuntimeError):
    """Raised when the byte-equal archive guard is not satisfied."""


def _backlog_path(root) -> Path:
    return Path(root) / "BACKLOG.md"


def _archive_path(root) -> Path:
    return Path(root) / "docs" / "BACKLOG-archive.md"


# An open backlog item is a top-level GFM unchecked task line: `- [ ] ...`.
# A `- [x]`/`- [X]` line is closed and stays only in the archive.
_OPEN_RE = re.compile(r"^\s*-\s*\[ \]\s+(?P<text>.+?)\s*$")

# A `## ` / `### ` section heading; its text becomes the provenance source_ref so
# the cluster context (date + title) is preserved as data, not lost in the flip.
_SECTION_RE = re.compile(r"^#{2,3}\s+(?P<title>.+?)\s*$")

# Best-effort priority hint from a leading severity glyph the human backlog uses.
_PRIORITY_GLYPH = {"🔴": "P1", "🟠": "P2", "🟡": "P3", "🟢": "P3"}

# Best-effort type inference from item content (longest/most-specific first).
# Keys are lowercased substrings; first match wins. Default falls through to debt.
_TYPE_KEYWORDS = [
    ("kiến trúc", "architecture"),
    ("architecture", "architecture"),
    ("waterfall", "architecture"),
    ("skill", "feature"),
    ("bundle", "feature"),
    ("vsf:", "feature"),
    ("sync", "feature"),
    ("bug", "bug"),
    ("gate", "debt"),
    ("test", "debt"),
]


def _infer_type(text: str) -> str:
    low = text.lower()
    for needle, type_ in _TYPE_KEYWORDS:
        if needle in low:
            return type_
    return "debt"


def archive_backlog(root) -> Path:
    """Copy BACKLOG.md byte-equal into docs/BACKLOG-archive.md (through the docs
    fence) and ASSERT equality. Raises MigrationError if the copy is not
    byte-equal. Idempotent: re-archiving an identical file is a no-op rewrite."""
    src = _backlog_path(root)
    try:
        data = src.read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise MigrationError("cannot read %s: %s" % (src, exc))
    dst = _archive_path(root)
    fs_guard.assert_under(dst, "docs", root=root)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    if dst.read_bytes() != data:
        raise MigrationError(
            "archive %s is not byte-equal to %s — refusing to proceed" % (dst, src))
    return dst


def _archive_is_byte_equal(root) -> bool:
    src, dst = _backlog_path(root), _archive_path(root)
    try:
        return dst.is_file() and dst.read_bytes() == src.read_bytes()
    except OSError:
        return False


def parse_open_items(text: str) -> List[Dict[str, Any]]:
    """Open (`- [ ]`) items as best-effort candidate records. For each item:
    text = the line after the checkbox; `source_ref` = the enclosing `## ` / `###`
    section heading (preserves the date+title cluster context as data); `priority`
    from a leading severity glyph when present (🔴→P1, 🟠→P2, 🟡/🟢→P3) else P2;
    `type` inferred from content keywords, else 'debt'. The human reviews and
    adjusts these before apply_migration writes them."""
    out: List[Dict[str, Any]] = []
    section = ""
    for line in text.splitlines():
        sm = _SECTION_RE.match(line)
        if sm:
            section = sm.group("title").strip()
            continue
        m = _OPEN_RE.match(line)
        if not m:
            continue
        body = m.group("text").strip()
        priority = "P2"
        for glyph, prio in _PRIORITY_GLYPH.items():
            if glyph in body:
                priority = prio
                break
        out.append({"text": body, "type": _infer_type(body),
                    "priority": priority, "source_ref": section})
    return out


def apply_migration(root, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Add each approved candidate to the SSOT, then let render flip BACKLOG.md.

    Archive guard: refuse unless docs/BACKLOG-archive.md exists AND is byte-equal to
    the live BACKLOG.md. This runs BEFORE any add/render, so a missing or
    tampered archive aborts with the source prose untouched."""
    if not _archive_is_byte_equal(root):
        raise MigrationError(
            "refusing to migrate: docs/BACKLOG-archive.md is missing or not "
            "byte-equal to BACKLOG.md — archive it first. The flip would "
            "otherwise risk losing prose.")
    # Build (validate) the new content FIRST, publish (the destructive unlink
    # below) only once every candidate is known-good — a hand-tweaked
    # --candidates output with one bad type/priority must abort HERE, before
    # the live file is gone, not mid-loop with BACKLOG.md already unlinked and
    # only some candidates added (no live file + a half-populated SSOT).
    for cand in candidates:
        br._validate(cand.get("text", "") or "", cand.get("type", "debt") or "debt",
                     cand.get("priority", "P2") or "P2", "open")
    # The byte-equal archive now holds the original prose verbatim, so the live
    # BACKLOG.md is safe to replace. Remove it BEFORE the first add() re-render —
    # render's marker-guard (H2) refuses to overwrite an un-migrated file, and
    # this un-marked hand-written file is exactly that. The archive is the
    # sanctioned "archive it first" the guard's message points at.
    _backlog_path(root).unlink()
    for cand in candidates:
        br.add(root, text=cand["text"], type=cand.get("type", "debt"),
               priority=cand.get("priority", "P2"),
               source_ref=cand.get("source_ref", "migrate"))
    # The flip: render overwrites BACKLOG.md from the SSOT. backlog_register's
    # add() already re-rendered after each record, but render() here is the
    # explicit, marker-guarded flip the migration is responsible for.
    path = br.render(root)
    return {"migrated": len(candidates), "backlog": str(path),
            "archive": str(_archive_path(root))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--archive", action="store_true",
                      help="cp BACKLOG.md -> docs/BACKLOG-archive.md + assert byte-equal")
    mode.add_argument("--candidates", action="store_true",
                      help="print parsed open items (for human review)")
    mode.add_argument("--apply", action="store_true",
                      help="archive (if needed) then add candidates + flip BACKLOG.md")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    try:
        if args.archive:
            path = archive_backlog(root)
            print(json.dumps({"archived": str(path)}, ensure_ascii=False))
            return 0
        text = _backlog_path(root).read_text(encoding="utf-8")
        candidates = parse_open_items(text)
        if args.candidates:
            print(json.dumps({"candidates": candidates}, indent=2,
                             ensure_ascii=False))
            return 0
        if not _archive_is_byte_equal(root):
            archive_backlog(root)
        result = apply_migration(root, candidates)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001 — surface as a JSON finding
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)},
                         ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
