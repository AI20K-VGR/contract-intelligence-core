#!/usr/bin/env python3
"""backlog_register — the Backlog Register: the tool-written home for deferred
work items (`BL-<n>`).

The shape clones decision_register's dual-mode pattern: `docs/backlog.yaml` is
the YAML SSOT (load → mutate → dump); root `BACKLOG.md` is a rendered human
view carrying a generated-marker header. A backlog item is recorded when work
is deferred out of the current scope; the register gives it an id, an actor, a
timestamp, and a machine query so agents stop hand-editing prose.

Fence split: the SSOT `docs/backlog.yaml` write routes through
`fs_guard.assert_under(path, "docs")`. The rendered view at root `BACKLOG.md`
is an explicitly approved root markdown (CLAUDE.md hard-constraint 5) and is
written DIRECTLY — calling `assert_under(BACKLOG.md, "docs")` would raise on a
root path. This is the one divergence from decision_register (whose view lives
inside the docs zone).

Marker guard: `render` refuses to overwrite an existing `BACKLOG.md` that
lacks the generated-marker header (an un-migrated or hand-edited file) — it
aborts rather than clobber manual content.

ID grammar: `^BL-\\d+$`, rendered zero-padded (`BL-001`). Monotonic max+1
regardless of status — a done/archived item still counts, so ids are never
reused. The id scan reads the YAML SSOT's `id:` lines (NOT markdown headings),
so reading the rendered view's `## BL-NNN` headings can never collide an id.

CLI:
    backlog_register.py add --text ... --type ... --priority ... \\
        [--source-ref ...] [--root <dir>]
    backlog_register.py done --id BL-1 [--root <dir>]
    backlog_register.py archive --id BL-1 [--root <dir>]
    backlog_register.py list [--root <dir>]            # open records as JSON
    backlog_register.py query [--status ...] [--type ...] [--priority ...] \\
        [--source-ref ...] [--root <dir>]
    backlog_register.py render [--root <dir>]          # re-render BACKLOG.md
"""

import argparse
import contextlib
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml_io

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import fs_guard  # noqa: E402
from register_store import (  # noqa: E402
    atomic_write, escape_injection, register_lock, sanitize_field,
)

_HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.append(str(_HOOKS_DIR))
import hook_runtime  # noqa: E402

# Windows consoles may default to a legacy codepage; UTF-8 JSON output must not
# crash there. reconfigure exists on 3.7+; guard for exotic stdouts.
if hasattr(sys.stdout, "reconfigure"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")


# ID grammar: BL- + digits, nothing else. Parent-free, globally monotonic.
BACKLOG_ID_RE = re.compile(r"^BL-\d+$")

# A free-text value that is a bare `---` fence or a `## BL-` heading could
# smuggle a fake heading into the rendered markdown view; both are neutralized
# on render. The SSOT stores text as a YAML scalar (structurally inert).
_INJ_BL_HEADING_RE = re.compile(r"(?m)^(##\s+BL-)")

# Resilient raw id-scan over the YAML SSOT: matches an `id: BL-<n>` line whether
# it is the list-item key (`- id: BL-1`) or an indented key, WITHOUT parsing the
# whole document — so one corrupt record never drops the ids of the rest, and
# the rendered view's `## BL-NNN` headings are never read as ids.
_YAML_ID_RE = re.compile(r"(?m)^\s*-?\s*id:\s*[\"']?(BL-\d+)[\"']?\s*$")

# Canonical record field order (what a rendered YAML record lists, in order).
_REC_FIELDS = ("id", "text", "type", "priority", "status", "created_ts",
               "done_ts", "source_ref", "actor")

_STATUSES = ("open", "done", "archived")
_PRIORITIES = ("P0", "P1", "P2", "P3")

GENERATED_MARKER = (
    "<!-- generated from docs/backlog.yaml by backlog_register.py — "
    "do not edit -->"
)


class BacklogError(ValueError):
    """Raised on a grammar/shape/enum violation or a marker-guard abort."""


def _yaml_path(root) -> Path:
    """The YAML SSOT path inside the docs zone."""
    return Path(root) / "docs" / "backlog.yaml"


def _md_path(root) -> Path:
    """The rendered human view — an approved root markdown, NOT fenced."""
    return Path(root) / "BACKLOG.md"


def _lock_path(root) -> Path:
    return Path(root) / "docs" / ".backlog_register.lock"


def _uses_yaml(root) -> bool:
    return _yaml_path(root).is_file()


@contextlib.contextmanager
def _register_lock(root):
    """alloc-id + append + render as ONE critical section so concurrent agents
    on one machine cannot overwrite each other's records."""
    with register_lock(_lock_path(root)):
        yield


def _norm_record(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Coerce a raw YAML mapping to a canonical record dict, or None when the id
    is malformed (skipped fail-soft — one corrupt record never sinks a read)."""
    bl_id = str(raw.get("id", "")).strip()
    if not BACKLOG_ID_RE.match(bl_id):
        return None

    def _val(key: str) -> str:
        v = raw.get(key)
        return str(v) if v not in (None, "") else ""

    rec = {"id": bl_id}
    for key in _REC_FIELDS[1:]:
        rec[key] = _val(key)
    rec["status"] = rec["status"] or "open"
    return rec


def _load_yaml_raw(root) -> List[Dict[str, Any]]:
    """Records from the YAML SSOT. A whole-file parse failure yields [] here;
    id allocation uses the resilient raw id-scan instead, so a corrupt record
    never collapses id reservation back to BL-001."""
    path = _yaml_path(root)
    try:
        data = yaml_io.safe_load(path.read_text(encoding="utf-8"))
    except (yaml_io.YAMLError, OSError, UnicodeDecodeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    out: List[Dict[str, Any]] = []
    for raw in data:
        if isinstance(raw, dict):
            rec = _norm_record(raw)
            if rec is not None:
                out.append(rec)
    return out


def parse_backlog(root) -> List[Dict[str, Any]]:
    """Every record (open AND done/archived), in stored order. Missing file →
    empty list."""
    return _load_yaml_raw(root)


def _scan_all_ids(root) -> List[str]:
    """Raw `id: BL-<n>` values from the SSOT — the source for id allocation."""
    try:
        text = _yaml_path(root).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return []
    return _YAML_ID_RE.findall(text)


def alloc_id(root) -> str:
    """Next free `BL-<n>` = max-existing + 1 (BL-001 on an empty register),
    rendered zero-padded to 3 digits. Scans RAW SSOT id lines so a
    corrupt-but-id-bearing record still reserves its number, and the rendered
    view's `## BL-NNN` headings are never counted."""
    used = []
    for bl_id in _scan_all_ids(root):
        m = re.match(r"^BL-(\d+)$", bl_id)
        if m:
            used.append(int(m.group(1)))
    nxt = (max(used) + 1) if used else 1
    return "BL-%03d" % nxt


def _validate(text: str, type_: str, priority: str, status: str) -> None:
    if not text.strip():
        raise BacklogError("a backlog item needs a non-empty text")
    if not type_.strip():
        raise BacklogError("a backlog item needs a non-empty type")
    if priority not in _PRIORITIES:
        raise BacklogError(
            "priority %r is not one of %s" % (priority, list(_PRIORITIES))
        )
    if status not in _STATUSES:
        raise BacklogError(
            "status %r is not one of %s" % (status, list(_STATUSES))
        )


def _dump_yaml_records(root, records: List[Dict[str, Any]]) -> Path:
    """Write the YAML SSOT atomically THROUGH the docs fence."""
    yp = _yaml_path(root)
    # Append-only guard: the resilient id-scan recovers ids even from a file
    # that failed a whole-file YAML parse (where _load_yaml_raw returns []).
    # If the records about to be written drop an id the scan can still see,
    # this dump would silently truncate the backlog — the clobber. Refuse the
    # write and leave the SSOT byte-untouched; a human repairs the corrupt file.
    lost = set(_scan_all_ids(root)) - {r.get("id") for r in records}
    if lost:
        raise BacklogError(
            "refusing to overwrite the backlog SSOT: the write would drop %d "
            "existing record(s) %s — docs/backlog.yaml likely failed to parse "
            "(corrupt). Repair it by hand instead of overwriting." % (
                len(lost), sorted(lost))
        )
    fs_guard.assert_under(yp, "docs", root=root)
    yp.parent.mkdir(parents=True, exist_ok=True)
    payload = [{k: r.get(k, "") for k in _REC_FIELDS} for r in records]
    text = yaml_io.safe_dump(payload, sort_keys=False, allow_unicode=True,
                          default_flow_style=False, width=4096)
    atomic_write(yp, text)
    return yp


def _num(rec: Dict[str, Any]) -> int:
    m = re.match(r"^BL-(\d+)$", rec.get("id", ""))
    return int(m.group(1)) if m else 0


def render_md(records: List[Dict[str, Any]]) -> str:
    """Render the SSOT records to the BACKLOG.md view string. Deterministic
    (grouped by status, then priority, items sorted by BL number) with free
    text injection-escaped so the rendered file can never be re-parsed into a
    phantom record. Pure function — testable without files."""
    parts = ["# Backlog", "", GENERATED_MARKER, ""]
    status_titles = [("open", "Open"), ("done", "Done"),
                     ("archived", "Archived")]
    for status, title in status_titles:
        group = sorted((r for r in records if r.get("status") == status),
                       key=_num)
        if not group:
            continue
        parts.append("## %s" % title)
        parts.append("")
        for prio in _PRIORITIES:
            items = [r for r in group if r.get("priority") == prio]
            if not items:
                continue
            parts.append("### %s" % prio)
            for r in items:
                parts.append(_render_item(r))
            parts.append("")
        # any item with an off-enum priority still renders under "Other"
        rest = [r for r in group if r.get("priority") not in _PRIORITIES]
        if rest:
            parts.append("### Other")
            for r in rest:
                parts.append(_render_item(r))
            parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def _render_item(rec: Dict[str, Any]) -> str:
    text = sanitize_field(rec.get("text", ""), _INJ_BL_HEADING_RE)
    type_ = sanitize_field(rec.get("type", ""), _INJ_BL_HEADING_RE)
    src = sanitize_field(rec.get("source_ref", ""), _INJ_BL_HEADING_RE)
    suffix = "  (%s)" % src if src else ""
    return "- %s [%s] %s%s" % (rec["id"], type_, text, suffix)


def _render_view(root, records: List[Dict[str, Any]]) -> Path:
    """Write the BACKLOG.md view DIRECTLY (approved root markdown — not fenced).
    refuse to overwrite an existing BACKLOG.md that lacks the marker."""
    mp = _md_path(root)
    if mp.is_file():
        head = mp.read_text(encoding="utf-8", errors="replace")[:512]
        if GENERATED_MARKER not in head:
            raise BacklogError(
                "refusing to overwrite %s — it lacks the generated marker "
                "(un-migrated or hand-edited). Archive it first "
                "(e.g. `cp BACKLOG.md docs/BACKLOG-archive.md`) then re-render."
                % mp
            )
    atomic_write(mp, render_md(records))
    return mp


def render(root) -> Path:
    """Re-render BACKLOG.md from the SSOT (marker-guarded)."""
    return _render_view(root, parse_backlog(root))


def add(root, text: str, type: str, priority: str, source_ref: str = "",
        status: str = "open") -> Dict[str, Any]:
    """Allocate the next BL id INSIDE the lock, append the record, re-render the
    view. Free text has newlines collapsed so it cannot reshape the record."""
    _validate(text, type, priority, status)
    flat_text = re.sub(r"[\r\n]+", " ", text).strip()
    flat_src = re.sub(r"[\r\n]+", " ", source_ref).strip()
    with _register_lock(root):
        records = _load_yaml_raw(root)
        bl_id = alloc_id(root)
        rec = {
            "id": bl_id,
            "text": flat_text,
            "type": type.strip(),
            "priority": priority,
            "status": status,
            "created_ts": dt.datetime.now(dt.timezone.utc).isoformat(),
            "done_ts": "",
            "source_ref": flat_src,
            "actor": hook_runtime.resolve_actor(),
        }
        records.append(rec)
        _dump_yaml_records(root, records)
        _render_view(root, records)
    return rec


def _flip_status(root, bl_id: str, new_status: str) -> Dict[str, Any]:
    """Flip one record's status in place + stamp done_ts when closing. The only
    in-place edit the register makes."""
    with _register_lock(root):
        records = _load_yaml_raw(root)
        hit = None
        for r in records:
            if r["id"] == bl_id:
                r["status"] = new_status
                if new_status == "done" and not r.get("done_ts"):
                    r["done_ts"] = dt.datetime.now(dt.timezone.utc).isoformat()
                hit = r
                break
        if hit is None:
            raise BacklogError("no backlog record with id %r" % bl_id)
        _dump_yaml_records(root, records)
        _render_view(root, records)
    return hit


def done(root, bl_id: str) -> Dict[str, Any]:
    """Flip status open→done, stamp done_ts."""
    return _flip_status(root, bl_id, "done")


def archive(root, bl_id: str) -> Dict[str, Any]:
    """Flip status →archived."""
    return _flip_status(root, bl_id, "archived")


def query(root, type: Optional[str] = None, priority: Optional[str] = None,
          status: Optional[str] = None,
          source_ref: Optional[str] = None) -> List[Dict[str, Any]]:
    """Filter records by any combination of type/priority/status/source_ref.
    The --source-ref filter is load-bearing for the bell's run-scoped query."""
    out = []
    for r in parse_backlog(root):
        if status is not None and r.get("status") != status:
            continue
        if type is not None and r.get("type") != type:
            continue
        if priority is not None and r.get("priority") != priority:
            continue
        if source_ref is not None and r.get("source_ref") != source_ref:
            continue
        out.append(r)
    return out


def list_open(root) -> List[Dict[str, Any]]:
    """Open records only — the still-active backlog."""
    return query(root, status="open")


def main() -> int:
    ap = argparse.ArgumentParser()
    # --root is shared by every subcommand and accepted AFTER it (matching the
    # documented CLI), so it lives on a parent parser, not the top level.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", parents=[common], help="record a backlog item")
    p_add.add_argument("--text", required=True)
    p_add.add_argument("--type", required=True)
    p_add.add_argument("--priority", required=True)
    p_add.add_argument("--source-ref", default="")

    p_done = sub.add_parser("done", parents=[common], help="flip an item to done")
    p_done.add_argument("--id", required=True)

    p_arch = sub.add_parser("archive", parents=[common],
                            help="flip an item to archived")
    p_arch.add_argument("--id", required=True)

    sub.add_parser("list", parents=[common], help="open records as JSON")

    p_q = sub.add_parser("query", parents=[common], help="filter records as JSON")
    p_q.add_argument("--status")
    p_q.add_argument("--type")
    p_q.add_argument("--priority")
    p_q.add_argument("--source-ref")

    sub.add_parser("render", parents=[common],
                   help="re-render BACKLOG.md from the SSOT")

    args = ap.parse_args()
    root = Path(args.root).resolve()
    try:
        if args.cmd == "add":
            rec = add(root, text=args.text, type=args.type,
                      priority=args.priority, source_ref=args.source_ref)
            print(json.dumps({"id": rec["id"], "written": True},
                             ensure_ascii=False))
            return 0
        if args.cmd == "done":
            rec = done(root, args.id)
            print(json.dumps({"id": rec["id"], "status": rec["status"]},
                             ensure_ascii=False))
            return 0
        if args.cmd == "archive":
            rec = archive(root, args.id)
            print(json.dumps({"id": rec["id"], "status": rec["status"]},
                             ensure_ascii=False))
            return 0
        if args.cmd == "list":
            print(json.dumps({"open": list_open(root)}, indent=2,
                             ensure_ascii=False))
            return 0
        if args.cmd == "query":
            got = query(root, type=args.type, priority=args.priority,
                        status=args.status, source_ref=args.source_ref)
            print(json.dumps({"records": got}, indent=2, ensure_ascii=False))
            return 0
        if args.cmd == "render":
            path = render(root)
            print(json.dumps({"rendered": str(path)}, ensure_ascii=False))
            return 0
    except Exception as exc:  # noqa: BLE001 — surface as a JSON finding
        print(json.dumps(
            {"error": "invalid_input", "message": str(exc), "written": False},
            ensure_ascii=False,
        ))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
