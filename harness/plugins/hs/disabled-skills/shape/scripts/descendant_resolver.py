#!/usr/bin/env python3
"""descendant_resolver — resolve an epic/prd selector id down to its child
STORY nodes and classify each, for hs:shape's `--task` selector (BA).

`--task` may name a container (epic or prd) rather than a single story. The
container is a *selector*: it fans out to the stories beneath it so a task can
be authored for each, but a task's `serves` still only ever points at a story,
never at the container. This module produces that fan-out list.

Everything is derived from the existing PO spec graph
(`spec_graph.build_graph`, via the shared `_spec_bridge` loader) and the
existing serves map (`serves_resolver.resolve_serves_from_dir`) — no
frontmatter is hand-parsed here, so a `type`/`status`/parent-link field can
never drift between this reader and the gate that reads the same graph. It is
strictly read-only: it never writes, never calls a `shape_paths` write path,
and never mutates `docs/product/**`.

Two rules are load-bearing and easy to get subtly wrong:

  * only `type == "story"` nodes count as descendants. A non-story artifact
    hand-edited to carry `epic: <target>` (a nested-epic mistake) must NOT
    leak into the story list, or a task's `serves` could end up pointing at a
    non-story id.
  * `empty_branch` is defined by the STORY count, not by "has child epics". A
    prd with child epics but zero stories underneath is still an empty branch
    (the caller cannot author a task with nothing to serve).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Sibling import (same pattern as serves_resolver.py): insert this file's own
# directory and import by bare name so the isolated test loader resolves the
# already-loaded module objects rather than re-reading from disk.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import serves_resolver  # noqa: E402
from _spec_bridge import (  # noqa: E402
    load_spec_graph as _load_spec_graph,
    load_spec_modules as _load_spec_modules,
)

RootLike = Any  # str | Path, kept untyped to avoid a PEP-604 union annotation


def _empty(kind: Optional[str] = None) -> Dict[str, Any]:
    return {"target_kind": kind, "stories": [], "empty_branch": True}


def _story_entry(node: Dict[str, Any], story_to_tasks: Dict[str, Any]) -> Dict[str, Any]:
    sid = node.get("id")
    return {"id": sid, "status": node.get("status"), "has_task": sid in story_to_tasks}


def resolve_descendant_stories(root: RootLike, target_id: str) -> Dict[str, Any]:
    """Resolve `target_id` (a story, epic, or prd id) to its descendant stories.

    Returns ``{"target_kind", "stories": [{"id", "status", "has_task"}, ...],
    "empty_branch": bool}``:

      * story target      -> returns itself (kind ``"story"``, not empty).
      * epic target       -> child stories where ``epic == target_id``.
      * prd target        -> stories under any epic where ``prd == target_id``.
      * unknown/other id  -> ``target_kind`` None (or the raw kind for a
                             non-container node), empty stories, empty_branch.

    Fail-soft: a missing/corrupt graph yields an empty result, never raises.
    """
    try:
        spec_graph_mod = _load_spec_graph()
        graph = spec_graph_mod.build_graph(Path(root))
    except Exception:
        return _empty()

    nodes: List[Dict[str, Any]] = graph.get("nodes", []) if isinstance(graph, dict) else []
    by_id: Dict[str, Dict[str, Any]] = {}
    for n in nodes:
        if isinstance(n, dict) and isinstance(n.get("id"), str):
            by_id.setdefault(n["id"], n)

    target = by_id.get(target_id)
    if target is None:
        return _empty(None)

    kind = target.get("type")

    try:
        story_to_tasks = serves_resolver.resolve_serves_from_dir(root).get("story_to_tasks", {})
    except Exception:
        story_to_tasks = {}

    if kind == "story":
        return {
            "target_kind": "story",
            "stories": [_story_entry(target, story_to_tasks)],
            "empty_branch": False,
        }

    def _is_story(n: Dict[str, Any]) -> bool:
        return isinstance(n, dict) and n.get("type") == "story"

    story_nodes: List[Dict[str, Any]] = []
    if kind == "epic":
        story_nodes = [n for n in nodes if _is_story(n) and n.get("epic") == target_id]
    elif kind == "prd":
        child_epic_ids = {
            n.get("id")
            for n in nodes
            if isinstance(n, dict) and n.get("type") == "epic" and n.get("prd") == target_id
        }
        story_nodes = [n for n in nodes if _is_story(n) and n.get("epic") in child_epic_ids]
    else:
        # A non-container node (brd goal, vision, ...) is not a valid selector.
        return {"target_kind": kind, "stories": [], "empty_branch": True}

    # Dedup by id (defensive against a duplicated hand-authored artifact) and
    # sort for a deterministic list.
    seen: set = set()
    deduped: List[Dict[str, Any]] = []
    for n in story_nodes:
        sid = n.get("id")
        if isinstance(sid, str) and sid not in seen:
            seen.add(sid)
            deduped.append(n)
    deduped.sort(key=lambda n: n.get("id") or "")

    entries = [_story_entry(n, story_to_tasks) for n in deduped]
    return {"target_kind": kind, "stories": entries, "empty_branch": len(entries) == 0}


# ---------------------------------------------------------------------------
# CLI (mirrors serves_resolver.py: --root, JSON out via the shared emitter)
# ---------------------------------------------------------------------------

def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="descendant_resolver.py",
        description="Resolve an epic/prd selector id down to its descendant "
        "stories (status + has_task); print as JSON. Read-only.",
    )
    p.add_argument("--root", required=True, help="workspace root (holds docs/product/)")
    p.add_argument("--target", required=True, help="story/epic/prd id to resolve")
    return p


def main(argv=None) -> int:
    args = _build_argparser().parse_args(argv)
    result = resolve_descendant_stories(args.root, args.target)
    _load_spec_modules(("encoding_utils",)).emit_json(result, sort_keys=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
