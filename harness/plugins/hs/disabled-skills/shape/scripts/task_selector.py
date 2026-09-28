#!/usr/bin/env python3
"""task_selector — fan an epic/prd selector out to its descendant stories and
author one dev task per selected story, for hs:shape's `--task [story|epic|prd]`.

The container (epic/prd) is only a SELECTOR: it picks WHICH stories to author
tasks for. Every authored task's `serves` still points at a STORY id, never at
the container -- the story-serving task model is unchanged. This module is the
one place that composes the read side (`descendant_resolver`, the PO story
graph) with the write side (`task_model.author`), keeping each of those two
independently testable: the resolver never writes, and `task_model` never reads
the graph.

Scope rules (locked):
  * empty branch (no descendant stories) is NEVER authored -- the BA cannot
    create a PO story, so the caller is routed back to `hs:spec --story`.
  * an explicit STORY target keeps the old path: author it directly, with no
    approved/draft filter and no `from_draft` mark (the BA named that story).
  * an epic/prd target applies the scope choice: approved-only by default, or
    include-draft when the caller opted in. A task authored off a not-yet-
    approved story carries `from_draft: true` as a warning marker only -- the
    `serves` field is unchanged.

This module authors; it does not interview. The approved-vs-draft choice is a
human decision the skill collects (an epic/prd fans out to several stories, so
the human is asked how far to go) and passes in as `include_draft`; the empty
branch is a hard stop the skill surfaces, not a silent no-op.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import descendant_resolver  # noqa: E402
import task_model  # noqa: E402
from _spec_bridge import load_spec_modules as _load_spec_modules  # noqa: E402

RootLike = Any  # str | Path, kept untyped to avoid a PEP-604 union annotation


def author_tasks_for_selector(
    root: RootLike,
    target_id: str,
    include_draft: bool = False,
    actor: Optional[str] = None,
) -> Dict[str, Any]:
    """Author dev tasks for the stories under `target_id`.

    Returns ``{"empty_branch", "target_kind", "route", "authored": [record,
    ...], "skipped_draft": [story_id, ...]}``:

      * empty branch  -> nothing authored; ``route`` names the hs:spec command
                         to create a story; ``authored`` empty.
      * story target  -> the one story authored directly (old path); no mark.
      * epic/prd       -> approved stories authored; draft stories authored only
                         when ``include_draft`` (each marked ``from_draft``),
                         otherwise collected in ``skipped_draft``.

    The PO story tree is never mutated -- authoring goes only through
    ``task_model.author`` (which writes under ``docs/product/shape/tasks/``).
    """
    resolved = descendant_resolver.resolve_descendant_stories(root, target_id)
    kind = resolved.get("target_kind")

    if resolved.get("empty_branch"):
        return {
            "empty_branch": True,
            "target_kind": kind,
            "route": "hs:spec --story %s" % target_id,
            "authored": [],
            "skipped_draft": [],
        }

    stories: List[Dict[str, Any]] = resolved.get("stories", [])

    # Explicit single-story target: author it directly, unchanged old path --
    # no approved/draft filter, no from_draft mark (the BA named this story).
    if kind == "story":
        sid = stories[0]["id"]
        record = task_model.author(root, serves=[sid], actor=actor)
        return {
            "empty_branch": False,
            "target_kind": "story",
            "route": None,
            "authored": [record],
            "skipped_draft": [],
        }

    authored: List[Dict[str, Any]] = []
    skipped_draft: List[str] = []
    for story in stories:
        sid = story.get("id")
        approved = story.get("status") == "approved"
        if not approved and not include_draft:
            skipped_draft.append(sid)
            continue
        record = task_model.author(
            root, serves=[sid], from_draft=not approved, actor=actor
        )
        authored.append(record)

    return {
        "empty_branch": False,
        "target_kind": kind,
        "route": None,
        "authored": authored,
        "skipped_draft": skipped_draft,
    }


# ---------------------------------------------------------------------------
# CLI (mirrors serves_resolver.py: --root, JSON out via the shared emitter)
# ---------------------------------------------------------------------------

def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="task_selector.py",
        description="Fan an epic/prd selector out to its descendant stories and "
        "author one dev task per selected story; print the result as JSON. A "
        "story target authors directly; an empty branch authors nothing and "
        "returns a route to hs:spec.",
    )
    p.add_argument("--root", required=True, help="workspace root (holds docs/product/)")
    p.add_argument("--target", required=True, help="story/epic/prd id to author for")
    p.add_argument(
        "--include-draft",
        action="store_true",
        help="also author tasks for not-yet-approved (draft) stories, each "
        "marked from_draft; default authors only approved stories",
    )
    return p


def main(argv=None) -> int:
    args = _build_argparser().parse_args(argv)
    result = author_tasks_for_selector(
        args.root, args.target, include_draft=args.include_draft
    )
    _load_spec_modules(("encoding_utils",)).emit_json(result, sort_keys=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
