#!/usr/bin/env python3
"""task_model — dev-task CRUD for hs:shape (BA), the story<->task bridge.

The BA decomposes an approved PO story (read from `hs:spec`'s graph) into one
or more concrete developer tasks. A task carries `serves: [story_ids]` — a
plain list, with NO schema-level special-case for cardinality:

    1-1   one task,  serves:[S1]           -- one story, one task
    1-n   many tasks, each serves:[S1]     -- one story, several tasks
    n-1   one task,  serves:[S1,S2,S3]     -- several stories, one task

The three shapes all fall out of how many tasks reference the same story id
and how many ids one task lists — see `references/task-model.md`. This
module only validates that `serves` is non-empty; RESOLVING those ids against
the PO story graph (and flagging a dangling one) is `serves_resolver.py`'s
job, not this module's — reading the graph is a separate concern from
writing the task record.

Storage: one file per task, `<root>/docs/product/shape/tasks/TASK-<n>.md`
(YAML frontmatter + free-text body) — the same one-file-per-record shape the
sibling experiment sidecar uses for `EXP-<n>.md`, so a later task edit
(status updates, a future POC-gate loop) can rewrite just that one file
without touching any sibling task.

`TASK-<n>` is parent-free and globally monotonic within the workspace tasks
dir (max existing `TASK-<n>.md` filename + 1, never reused) — a story-scoped
id (e.g. `TASK-<story>-<n>`) cannot express n-1 (one task serving several
stories has no single parent story to scope under).

Containment: every write resolves through `shape_paths.shape_path()` — this
module never writes anywhere but `docs/product/shape/tasks/`, and in
particular never touches `docs/product/stories/` (the PO-owned tree): there
is no code path here that accepts a PO-tree destination.
"""

from __future__ import annotations

import argparse
import fcntl
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shape_paths import shape_dir, shape_path  # noqa: E402
from _sidecar import _default_actor, _now_iso, write_record, SidecarError  # noqa: E402
from _spec_bridge import (  # noqa: E402
    load_frontmatter_parser as _load_frontmatter_parser,
    load_id_grammar as _load_id_grammar,
)

RootLike = Any  # str | Path, kept untyped to avoid a PEP-604 union annotation


class TaskError(ValueError):
    """Raised on a malformed task input (empty serves, missing task, ...)."""


_TASK_ID_RE = re.compile(r"^TASK-([0-9]+)$")
_TASK_FILE_RE = re.compile(r"^TASK-([0-9]+)\.md$")

STATUSES = ("open", "in_progress", "done")


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def tasks_dir(root: RootLike) -> Path:
    return shape_dir(root) / "tasks"


def _existing_task_nums(root: RootLike) -> List[int]:
    d = tasks_dir(root)
    if not d.exists():
        return []
    nums = []
    for p in sorted(d.glob("TASK-*.md")):
        m = _TASK_FILE_RE.match(p.name)
        if m:
            nums.append(int(m.group(1)))
    return nums


# ---------------------------------------------------------------------------
# Frontmatter render / read
# ---------------------------------------------------------------------------

def _render_body(task_id: str, title: str, acceptance: Sequence[str]) -> str:
    lines = ["# %s — %s" % (task_id, title or task_id), ""]
    if acceptance:
        lines.append("## Acceptance")
        lines.append("")
        for a in acceptance:
            lines.append("- %s" % a)
    return "\n".join(lines)


def _read_frontmatter_at(path: Path, label: str) -> Tuple[Dict[str, Any], str]:
    """Read (frontmatter dict, body) off the ACTUAL file at `path`. Raises
    TaskError on a missing file or malformed/non-mapping frontmatter --
    never a raw parser traceback. `label` is only for the error message.

    Routed through `frontmatter_parser.parse_text` (the hardened SSOT)
    instead of a locally hand-tuned `_FRONTMATTER_RE` + `yaml.safe_load` +
    `(yaml.YAMLError, ValueError)` catch: PyYAML raises a wider family than
    that pair on malformed frontmatter -- e.g. a bare `AttributeError` from
    `construct_yaml_timestamp` on an explicit-tag `ts: !!timestamp 'not a
    ts'` -- and the SSOT already fails soft on the whole family in one place,
    so this reader cannot drift out of sync with its siblings on which
    exception types it happens to catch."""
    if not path.is_file():
        raise TaskError("task not found: %s" % label)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise TaskError("cannot read task file (%s): %s" % (label, exc))
    fp = _load_frontmatter_parser()
    parsed = fp.parse_text(text, file_label=str(path))
    if not parsed["ok"]:
        raise TaskError("malformed task frontmatter (%s): %s" % (label, parsed["error"]))
    return parsed["frontmatter"], parsed["body"]


def read_task(root: RootLike, task_id: str) -> Tuple[Dict[str, Any], str]:
    """Return (frontmatter dict, body) for `task_id`, resolved to the
    CANONICAL `tasks/<task_id>.md` path. Raises TaskError on a missing file
    or malformed/non-mapping frontmatter (see `_read_frontmatter_at`).

    A non-canonical (e.g. zero-padded `TASK-02.md`) file is invisible here
    by design -- this is the id-addressed lookup; `list_tasks()` below is
    the glob-addressed one and reads whatever file is actually on disk."""
    if not _TASK_ID_RE.match(task_id or ""):
        raise TaskError("not a valid task id: %r" % task_id)
    path = shape_path(root, "tasks/%s.md" % task_id)
    return _read_frontmatter_at(path, task_id)


def write_task(root: RootLike, task_id: str, record: Dict[str, Any], body: str) -> Path:
    target = shape_path(root, "tasks/%s.md" % task_id)
    write_record(target, record, body)
    return target


# ---------------------------------------------------------------------------
# Author
# ---------------------------------------------------------------------------

def author(
    root: RootLike,
    serves: Sequence[str],
    title: str = "",
    estimate: str = "",
    depends_on: Optional[Sequence[str]] = None,
    acceptance: Optional[Sequence[str]] = None,
    actor: Optional[str] = None,
    from_draft: bool = False,
) -> Dict[str, Any]:
    """Allocate the next TASK-<n> and write it under `shape_path()`.

    `serves` is required and must be a non-empty list of story ids -- the
    n-1 shape needs at least one, and a task serving nothing is not a task.
    Ids are stored VERBATIM (not resolved against the PO graph here); a
    dangling id is a `serves_resolver.py` concern, not an author-time
    rejection, so a BA can record intent before the PO story lands.

    `from_draft` is an optional warning marker: when a selector fan-out
    authors a task off a story that is not yet approved, the record carries
    `from_draft: true` so a later reader can flag work built on unratified
    scope. It is additive -- omitted (not written) on the common approved /
    explicit-story path, so a record without it reads as false and the old
    record shape is preserved.
    """
    if not serves or not isinstance(serves, list) or not all(
        isinstance(s, str) and s for s in serves
    ):
        raise TaskError("serves must be a non-empty list of story ids")

    depends_on = list(depends_on or [])
    acceptance = list(acceptance or [])

    d = tasks_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    lock_path = d / ".tasks.lock"
    with open(lock_path, "a+") as lock_fd:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        try:
            nums = _existing_task_nums(root)
            new_num = (max(nums) + 1) if nums else 1
            task_id = "TASK-%d" % new_num

            resolved_actor = actor or _default_actor()
            record: Dict[str, Any] = {
                "id": task_id,
                "serves": list(serves),
                "title": title,
                "estimate": estimate,
                "depends_on": depends_on,
                "acceptance": acceptance,
                "status": "open",
                "actor": resolved_actor,
                "ts": _now_iso(),
            }
            if from_draft:
                record["from_draft"] = True
            body = _render_body(task_id, title, acceptance)
            target = write_task(root, task_id, record, body)

            result = dict(record)
            result["path"] = str(target)
            return result
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)


def list_tasks(root: RootLike) -> List[Dict[str, Any]]:
    """Return frontmatter dicts for every TASK-<n>.md under the tasks dir,
    sorted by numeric id. A malformed task file -- one that fails to parse OR
    one whose `id` is not a non-empty string -- is skipped rather than
    raising, so `--list` never surfaces a raw traceback over one bad
    hand-edited record AND never surfaces a record no sibling reader would
    (mirrors serves_resolver.list_task_records, which applies the same
    str-`id` guard).

    Reads the ACTUAL glob-matched file path (mirrors
    serves_resolver.list_task_records), not a re-derived canonical
    `TASK-%d.md` path: a hand-authored zero-padded filename like
    `TASK-02.md` still matches `_TASK_FILE_RE` and must stay visible here,
    the same way it already is to serves_resolver/strict_gate -- re-deriving
    `"TASK-%d" % num` and looking THAT up used to silently drop it (no file
    named exactly `TASK-2.md` on disk) instead of reading the file that is
    actually there."""
    d = tasks_dir(root)
    if not d.exists():
        return []
    numbered = []
    for p in sorted(d.glob("TASK-*.md")):
        m = _TASK_FILE_RE.match(p.name)
        if m:
            numbered.append((int(m.group(1)), p))
    out = []
    for _num, p in sorted(numbered):
        try:
            fm, _body = _read_frontmatter_at(p, p.name)
        except TaskError:
            continue
        # A non-string / empty `id` (a hand-edited `id: [TASK-1, TASK-2]`
        # YAML-parses to a LIST, a missing `id:` key to None) can never name a
        # real task -- skip it, the SAME way serves_resolver.list_task_records
        # does, so the two readers cannot disagree on membership and
        # loop_handoff never embeds a raw non-scalar id into a human brief.
        if isinstance(fm.get("id"), str) and fm.get("id"):
            out.append(fm)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="task_model.py",
        description="Author/list dev-task sidecar records (`serves:[story_ids]`, "
        "1-1/1-n/n-1, no schema special-case). Never mutates a PO story file.",
    )
    p.add_argument("--root", required=True, help="workspace root (holds docs/product/)")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--add", action="store_true", help="allocate + author a new task")
    mode.add_argument("--list", action="store_true", help="list existing tasks")
    p.add_argument("--serves", default="", help="comma-separated story ids")
    p.add_argument("--title", default="")
    p.add_argument("--estimate", default="")
    p.add_argument("--depends-on", default="", help="comma-separated TASK-<n> ids")
    p.add_argument("--acceptance", default="", help="semicolon-separated acceptance lines")
    p.add_argument("--actor", default=None)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_argparser().parse_args(argv)
    if args.add:
        serves = [s.strip() for s in args.serves.split(",") if s.strip()]
        depends_on = [d.strip() for d in args.depends_on.split(",") if d.strip()]
        acceptance = [a.strip() for a in args.acceptance.split(";") if a.strip()]
        try:
            record = author(
                args.root,
                serves=serves,
                title=args.title,
                estimate=args.estimate,
                depends_on=depends_on,
                acceptance=acceptance,
                actor=args.actor,
            )
        except (TaskError, SidecarError) as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 1
        print(record["id"])
        return 0
    if args.list:
        # Routed through `id_grammar.normalize_serves` -- the same shared
        # reading `serves_resolver`/`loop_handoff` use -- instead of a bare
        # `",".join(serves)`: a hand-edited non-list `serves` (a bare
        # string, an int) used to char-iterate or raise an uncaught
        # TypeError here, bricking the whole `--list` output over one bad
        # record. Invalid entries ride along in the same joined column
        # (str-coerced by normalize_serves) rather than being swallowed.
        id_grammar = _load_id_grammar()
        for rec in list_tasks(args.root):
            valid, invalid = id_grammar.normalize_serves(rec.get("serves"))
            print("%s\t%s\t%s" % (rec.get("id", ""), rec.get("status", ""),
                                   ",".join(valid + invalid)))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
