#!/usr/bin/env python3
"""serves_resolver — resolve dev-task `serves:[story_ids]` against the PO
story graph, for hs:shape (BA).

Takes a list of `{"id": <task_id>, "serves": [<story_id>, ...]}` records
(the same shape `task_model.author()`/`task_model.list_tasks()` return) and
builds the story<->task map plus the dangling-id flag list. All three
cardinalities (1-1/1-n/n-1) fall out of the same walk over `serves` — there
is no branch for "the n-1 case" or "the 1-n case"; see
`references/task-model.md`.

This module resolves whatever task records it is handed, whether they came
from disk, from an in-memory batch-author pass, or from a test fixture — it
never calls into `task_model`'s CRUD functions (`author`/`read_task`/
`write_task`). A caller that wants "resolve everything currently on disk"
reads the tasks dir itself (either via `task_model.list_tasks()` or
`list_task_records()` below) and passes the result in — keeping the writer
(`task_model`) and this reader independently testable/cookable, the same
design the sibling `experiment_spec.py` uses to stay independent of
`shape_paths.py`. The one exception is `_TASK_FILE_RE`, the `TASK-<n>.md`
filename regex, imported from `task_model.py` (the single SSOT) instead of
being redefined here — the two copies were identical today but a latent
drift hazard (a naming-scheme change landing in one and not the other would
silently break one reader's `TASK-*.md` glob match). A shared data-shape
constant is not the read/write coupling this module otherwise avoids.

Story-id resolution reuses hs:spec's `spec_graph.build_graph` through the
shared `_spec_bridge.load_spec_graph()` loader (the one home for the isolated
load, so no reader re-rolls it):
a naive `from spec_graph import build_graph` at module scope would collide
with the harness-internal docs-governance module of the same name already on
`sys.path` in-process (see `harness/tests/_spec_skill_import.py`), making
resolution order-dependent. Loading it fresh under a save/restore of
`sys.modules`/`sys.path` avoids that hazard without hard-coupling this
module to hs:spec's script layout beyond the one relative path below.

(Independent of hs:spec's `strict_gate.py`: that gate reads shape task
frontmatter as DATA to flag orphaned `serves`, but does not import this
module — see `references/story-task-spec.md`.)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

# Sibling import (same pattern as experiment_verdict.py -> experiment_spec.py):
# insert this file's own directory and import by bare name. Import machinery
# checks sys.modules FIRST, so under the isolated test loader (which loads
# task_model before serves_resolver and pre-registers "task_model" in
# sys.modules) this resolves to that exact loaded copy instead of re-reading
# the file from disk -- the same object `task_model.py` itself compiles.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from shape_paths import shape_dir  # noqa: E402
from _spec_bridge import (  # noqa: E402
    load_spec_graph as _load_spec_graph,
    load_frontmatter_parser as _load_frontmatter_parser,
    load_id_grammar as _load_id_grammar,
    load_spec_modules as _load_spec_modules,
)
from task_model import _TASK_FILE_RE  # noqa: E402

RootLike = Any  # str | Path, kept untyped to avoid a PEP-604 union annotation


def known_story_ids(root: RootLike) -> set:
    """Every story id currently in the PO spec graph."""
    spec_graph_mod = _load_spec_graph()
    graph = spec_graph_mod.build_graph(Path(root))
    return {
        n.get("id") for n in graph.get("nodes", [])
        if isinstance(n, dict) and n.get("type") == "story" and n.get("id")
    }


# ---------------------------------------------------------------------------
# Task record reading (no task_model import -- see module docstring)
# ---------------------------------------------------------------------------

def list_task_records(root: RootLike) -> List[Dict[str, Any]]:
    """Read every `TASK-<n>.md` frontmatter block under the tasks sidecar
    directly (read-only, no lock needed -- unlike task_model.author() this
    never writes). A malformed task file is skipped rather than raising, so
    one hand-edited-bad task cannot block resolving every other one.

    Routed through `frontmatter_parser.parse_text` (the hardened SSOT) rather
    than a locally hand-tuned `_FRONTMATTER_RE` + `yaml.safe_load` + catch:
    that SSOT already fails soft on the WHOLE PyYAML exception family (a bare
    `ValueError`/`AttributeError` from the timestamp constructor included,
    not just `yaml.YAMLError`), so this reader cannot drift out of sync with
    its siblings on which exception types it happens to catch.

    Sorted NUMERICALLY by the `TASK-<n>` number (mirroring
    `task_model.list_tasks()`), not lexicographically on the filename --
    a bare `sorted(d.glob(...))` string-sorts "TASK-10.md" before
    "TASK-2.md", diverging from every other task listing in this skill."""
    d = shape_dir(root) / "tasks"
    if not d.exists():
        return []
    fp = _load_frontmatter_parser()
    numbered = []
    for p in d.glob("TASK-*.md"):
        m = _TASK_FILE_RE.match(p.name)
        if m:
            numbered.append((int(m.group(1)), p))
    out = []
    for _num, p in sorted(numbered):
        # A non-regular glob match -- a FIFO/socket/device or a symlink to one --
        # would BLOCK read_text forever (the `except OSError` never fires: the
        # read blocks before it can raise). is_file() follows the symlink but only
        # stats, so it skips the non-regular entry without blocking. Same fail-soft
        # skip a malformed/non-UTF-8 file already gets.
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        parsed = fp.parse_text(text, file_label=str(p))
        if not parsed["ok"]:
            continue
        fm = parsed["frontmatter"]
        # A non-string `id` (a hand-edited `id: [TASK-1, TASK-2]` YAML-parses
        # to a LIST, not a scalar) can never name a real task and is
        # unhashable -- skip it here, at the source, the same way a
        # malformed-YAML or non-UTF-8 file already is, rather than letting it
        # ride into resolve_serves()'s dict-keyed accumulation below.
        if isinstance(fm.get("id"), str) and fm.get("id"):
            out.append(fm)
    return out


# ---------------------------------------------------------------------------
# Resolve
# ---------------------------------------------------------------------------

def resolve_serves(root: RootLike, tasks: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the story<->task map from `tasks` (each a dict with `id` +
    `serves`), against the PO story graph at `root`.

    Returns:
        story_to_tasks:  {story_id: [task_id, ...]}   -- covers 1-1 and 1-n
        task_to_stories: {task_id: [story_id, ...]}    -- covers n-1
        dangling:        {task_id: [story_id, ...]}    -- serves id absent
                          from the PO graph, OR a serves value that could
                          never resolve to one in the first place (flagged,
                          never dropped/crashed)

    No cardinality branch: a 1-1 task has one entry in `serves`, a 1-n
    story simply accumulates in `story_to_tasks` across several tasks, and
    an n-1 task's `task_to_stories` entry just has >1 element. Same field,
    same walk, all three shapes.

    `serves` is read through `id_grammar.normalize_serves` -- the ONE shared
    reading of the field also used by the PO strict-gate check, so this BA
    resolver cannot silently disagree with CI about what a malformed
    `serves` means (a non-list value used to empty to `[]` here instead of
    flagging, and a non-string list entry like a YAML-auto-resolved
    `datetime.date` used to ride through un-stringified and blow up this
    module's own `json.dumps` at the CLI boundary). Every returned invalid
    entry is already `str`-coerced by `normalize_serves`, so a caller can
    always JSON-serialize the result.
    """
    id_grammar = _load_id_grammar()
    known = known_story_ids(root)
    story_to_tasks: Dict[str, List[str]] = {}
    task_to_stories: Dict[str, List[str]] = {}
    dangling: Dict[str, List[str]] = {}

    for t in tasks:
        task_id = t.get("id")
        # `task_to_stories[task_id] = ...` below needs a hashable key -- a
        # caller that hands resolve_serves() a raw dict directly (bypassing
        # list_task_records()'s own str-`id` filter) could still carry a
        # non-str `id` (a hand-edited `id: [TASK-1, TASK-2]` YAML-parses to a
        # list). Guard here too, defense-in-depth: a non-str id can never
        # name a real task, so it is skipped, not str-coerced into a fake key
        # that would silently merge unrelated bad records together.
        if not isinstance(task_id, str) or not task_id:
            continue
        valid_ids, invalid_ids = id_grammar.normalize_serves(t.get("serves"))

        # Dedupe the valid (string) ids, order-preserving, before
        # accumulating: a hand-edited `serves:[S1,S1]` must not double-count
        # -- story_to_tasks[S1] would otherwise list TASK-1 twice, inflating
        # any downstream coverage count. `invalid_ids` is already
        # str-coerced by normalize_serves, so it never carries an unhashable
        # value here -- no need for the isinstance guard the old inline dedup
        # loop carried.
        seen: set = set()
        deduped: List[str] = []
        for story_id in valid_ids:
            if story_id not in seen:
                seen.add(story_id)
                deduped.append(story_id)
        # Dedupe invalid entries too (order-preserving): a hand-edited
        # `serves:[1,1]` is one malformed edge, not two -- matching
        # strict_gate.check_shape_serves, so the two shared readers cannot
        # disagree on how many times a duplicate malformed serves is reported.
        invalid_ids = list(dict.fromkeys(invalid_ids))

        # Accumulate + dedupe (not plain assignment) so two task files that
        # collide on the same `id` (a copy-paste that forgot to rename) keep a
        # UNION of their story edges here -- matching story_to_tasks' own
        # accumulation below. Plain assignment was last-record-wins and silently
        # dropped the earlier record's edge, making the two maps contradict. The
        # duplicate id itself is surfaced as a `dup_task_id` gate error.
        task_to_stories[task_id] = list(dict.fromkeys(
            task_to_stories.get(task_id, []) + deduped + invalid_ids))
        for story_id in deduped:
            if story_id in known:
                lst = story_to_tasks.setdefault(story_id, [])
                if task_id not in lst:  # one edge, one entry (dup id -> no inflation)
                    lst.append(task_id)
            else:
                # Accumulate + dedupe, matching the other two maps: two task
                # files colliding on the same id must report a dangling edge
                # ONCE, not once per duplicate record -- an un-guarded append
                # inflated this diagnostic count while task_to_stories (deduped)
                # stayed at one, so the two disagreed on the same dup id.
                dl = dangling.setdefault(task_id, [])
                if story_id not in dl:
                    dl.append(story_id)
        if invalid_ids:
            dangling[task_id] = list(dict.fromkeys(
                dangling.get(task_id, []) + invalid_ids))

    return {
        "story_to_tasks": story_to_tasks,
        "task_to_stories": task_to_stories,
        "dangling": dangling,
    }


def resolve_serves_from_dir(root: RootLike) -> Dict[str, Any]:
    """Convenience: resolve every task currently committed to the sidecar
    (read via `list_task_records()`, no `task_model` import)."""
    return resolve_serves(root, list_task_records(root))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="serves_resolver.py",
        description="Resolve dev-task `serves:[story_ids]` against the PO story "
        "graph; print the story<->task map + any dangling ids as JSON.",
    )
    p.add_argument("--root", required=True, help="workspace root (holds docs/product/)")
    return p


def main(argv=None) -> int:
    args = _build_argparser().parse_args(argv)
    result = resolve_serves_from_dir(args.root)
    # emit_json (spec's shared BrokenPipe-safe + lone-surrogate-safe emitter) keeps
    # the `... | head` always-exit-0 contract the raw print(json.dumps(...)) broke.
    _load_spec_modules(("encoding_utils",)).emit_json(result, sort_keys=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
