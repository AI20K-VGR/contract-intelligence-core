#!/usr/bin/env python3
"""roadmap_rollup — milestone + effort rollup for hs:shape (BA sidecar).

Groups dev tasks (`task_model.py`) into milestones with an effort figure
(`effort_map.py`) and a technical-feasibility precondition read from the POC
sidecar (`poc_gate.py`). The data only ever flows ONE way here: this module
READS an already-closed POC verdict as a precondition for a milestone to count
work as committed; it never re-opens, re-orders, or writes back into a POC
record. A task whose declared POC has not closed simply does not make it into
`contains` this rollup -- it is held back, not rejected outright, and the next
rollup run picks it up automatically once that POC closes.

Not every task carries a POC precondition. Only a task explicitly named in the
caller-supplied `task_poc_map` is gated at all; every other task rolls up
unconditionally. `poc_gated` on the resulting milestone record is `True` only
when at least one gate was declared for it AND every declared gate resolved to
closed; it is `False` both when nothing was gated (nothing to verify, purely
advisory) and when a declared gate is still open, missing, or unreadable --
none of those three cases ever raises.

Per-task effort comes from `task_model`'s own `estimate` field (a BA figure
already on the task record); `effort_map.sum_estimates()` folds a milestone's
task estimates into one rollup figure. Falling a blank task estimate back to a
size-derived range needs the linked story's PO size, which this module does
not fetch itself -- it accepts an optional caller-supplied `story_sizes`
mapping instead of importing the PO's own graph builder, so this module stays
testable without seeding a full PO spec tree (the same independent-testability
split `serves_resolver.py` draws around its own PO-graph read).

Storage: unlike the one-file-per-record task/POC/experiment sidecars, the
roadmap is a single sidecar document -- `docs/product/shape/roadmap.md`
(YAML frontmatter `milestones: [...]` + a rendered body) -- written through
`shape_paths.shape_path()` like every other hs:shape writer. Nothing here ever
touches `docs/product/stories/` or any other PO-owned path.
"""

from __future__ import annotations

import argparse
import fcntl
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shape_paths import shape_path  # noqa: E402
from task_model import TaskError, read_task  # noqa: E402
from poc_gate import PocError, read_poc  # noqa: E402
from effort_map import (  # noqa: E402
    default_size_range_table,
    estimate_for_task,
    map_size_to_range,
    parse_estimate_days,
    sum_estimates,
)
from _sidecar import _default_actor, _now_iso, write_record, SidecarError  # noqa: E402
from _spec_bridge import (  # noqa: E402
    load_frontmatter_parser as _load_frontmatter_parser,
    load_id_grammar as _load_id_grammar,
)

RootLike = Any  # str | Path, kept untyped to avoid a PEP-604 union annotation


class RoadmapError(ValueError):
    """Raised on a malformed roadmap input (bad milestone id, ...)."""


_MS_ID_RE = re.compile(r"^MS-([0-9]+)$")


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def roadmap_file(root: RootLike) -> Path:
    return shape_path(root, "roadmap.md")


# ---------------------------------------------------------------------------
# Technical-feasibility precondition read (fail-open, never raises)
# ---------------------------------------------------------------------------

def poc_closed_status(root: RootLike, poc_id: Optional[str]) -> Optional[bool]:
    """`True` when `poc_id` reads back closed, `False` when it exists but is
    still open, `None` when it is absent/unreadable/not given at all. `None`
    and `False` are both treated as "not yet satisfied" by `build_milestone`
    -- the caller distinguishes them only for diagnostics, never to crash."""
    if not poc_id:
        return None
    try:
        fm, _body = read_poc(root, poc_id)
    except PocError:
        return None
    # `is True`, not `bool(...)`: poc_gate.gate() always writes a real bool,
    # but a hand-edited `closed: "false"` (a truthy non-empty string) must
    # read as NOT closed, not accidentally coerce true via bool(str).
    return fm.get("closed") is True


# ---------------------------------------------------------------------------
# One milestone: gather tasks, roll up effort, gate on POC precondition
# ---------------------------------------------------------------------------

def build_milestone(
    root: RootLike,
    milestone_id: str,
    title: str = "",
    target_window: str = "",
    task_ids: Optional[Sequence[str]] = None,
    depends_on: Optional[Sequence[str]] = None,
    task_poc_map: Optional[Dict[str, str]] = None,
    story_sizes: Optional[Dict[str, str]] = None,
    size_table: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Build one milestone record from `task_ids`, holding back any task whose
    declared POC precondition has not closed. Never raises on a missing task
    or a missing/open POC -- both simply narrow `contains`/`excluded`."""
    if not _MS_ID_RE.match(milestone_id or ""):
        raise RoadmapError("not a valid milestone id: %r" % milestone_id)

    # Order-preserving dedupe: a repeated id (a hand-edited or re-run
    # `--task-ids TASK-1,TASK-1`) must not double-count that task's effort
    # into `effort_rollup` below -- `serves_resolver` already dedupes its
    # own story ids the same way; `task_ids` never did.
    seen_task_ids: set = set()
    deduped_task_ids: List[str] = []
    for tid in task_ids or []:
        if tid not in seen_task_ids:
            seen_task_ids.add(tid)
            deduped_task_ids.append(tid)
    task_ids = deduped_task_ids
    # Coerce via the same helper detect_cycles uses (NOT a bare list(): a
    # programmatic `depends_on="MS-2"` would otherwise char-explode to
    # ['M','S','-','2'] and be stored to disk, defeating cycle detection).
    depends_on = _coerce_depends_on(depends_on)
    task_poc_map = dict(task_poc_map or {})
    story_sizes = dict(story_sizes or {})

    contains: List[str] = []
    excluded: List[Dict[str, str]] = []
    estimates: List[str] = []
    dropped_estimates: List[str] = []
    unmapped_sizes: List[Dict[str, str]] = []
    any_gate_declared = False
    any_gate_unsatisfied = False
    id_grammar = _load_id_grammar()
    # Resolve the size->range table ONCE: on the size_table=None path (the CLI /
    # add_milestone default) both estimate_for_task and map_size_to_range would
    # each parse the default YAML per task (2× per task). A non-None table is
    # passed straight through, so this is byte-identical to the per-call default.
    eff_table = size_table if size_table is not None else default_size_range_table()

    for task_id in task_ids:
        try:
            fm, _body = read_task(root, task_id)
        except TaskError:
            excluded.append({"task_id": task_id, "reason": "task_not_found"})
            continue

        poc_id = task_poc_map.get(task_id)
        if poc_id:
            any_gate_declared = True
            status = poc_closed_status(root, poc_id)
            if status is not True:
                any_gate_unsatisfied = True
                excluded.append({
                    "task_id": task_id,
                    "poc_id": poc_id,
                    "reason": "poc_not_closed" if status is False else "poc_unknown",
                })
                continue

        contains.append(task_id)
        # `serves` is read through `id_grammar.normalize_serves` -- the same
        # shared reading the BA `serves_resolver` uses -- instead of a bare
        # `for story_id in serves`: a hand-edited non-list `serves` (a bare
        # string, an int) is directly ITERABLE-OR-NOT depending on its type,
        # so the old loop either char-iterated a bare string (silently
        # matching a bogus single-letter story_sizes key) or TypeError'd on
        # a non-iterable value (`serves: 5`) or an unhashable list entry
        # (`serves: [["S1"]]`). Only the valid string ids can ever match a
        # `story_sizes` key, so only those are walked here.
        valid_serves, _invalid_serves = id_grammar.normalize_serves(fm.get("serves"))
        story_size = None
        for story_id in valid_serves:
            if story_id in story_sizes:
                story_size = story_sizes[story_id]
                break

        raw_est = fm.get("estimate")
        if raw_est not in (None, ""):
            if not isinstance(raw_est, str):
                # A hand-edited task record can carry a non-string estimate
                # (a bare YAML int `estimate: 3`). `estimate_for_task` below
                # already ignores it and falls through to a size-derived
                # range, but that fallback is silent -- surface the drop
                # here so an operator can see the rollup leaned on story
                # size instead of the BA's own (malformed) figure, rather
                # than the estimate just vanishing.
                dropped_estimates.append(task_id)
            elif parse_estimate_days(raw_est) is None:
                # A truthy STRING estimate that still fails to parse
                # ("-2d", "2 days", "3", "~3d") is a different failure mode:
                # not caught by the non-string branch above. `estimate_for_task`
                # now falls through to the same size-derived range the
                # non-string case gets (it no longer returns the unparsable
                # string as-is) -- but the BA's own figure was still ignored,
                # so flag it here too, at the same place the non-string case
                # is flagged.
                dropped_estimates.append(task_id)

        est = estimate_for_task(fm, story_size=story_size, table=eff_table)
        if not est and story_size and map_size_to_range(story_size, table=eff_table) is None:
            # The linked story's size letter has no entry in the size->range
            # table (e.g. the PO spec's size vocab grew an XS/XL this table's
            # author never mirrored) -- a loud, counted skip, never a silent
            # 0 folded into effort_rollup.
            unmapped_sizes.append({"task_id": task_id, "size": story_size})
        if est:
            if parse_estimate_days(est) is None and task_id not in dropped_estimates:
                # `est` can also come from a SIZE-DERIVED range (a caller
                # -supplied `size_table` entry like {"S": "2 days"}) rather
                # than the task's own `estimate` field -- that source is
                # never checked by the raw_est branch above. Truthy-but
                # -unparsable is the same silent-0 failure mode either way:
                # it would otherwise ride into `estimates` and only get
                # dropped once `sum_estimates` fails to parse it, with no
                # record anywhere. The `not in` guard avoids double-flagging
                # a task the raw_est branch already caught.
                dropped_estimates.append(task_id)
            estimates.append(est)

    if not any_gate_declared:
        poc_gate_status = "advisory"  # nothing declared -- purely informational
    elif any_gate_unsatisfied:
        poc_gate_status = "unsatisfied"  # at least one declared gate still open/missing
    else:
        poc_gate_status = "satisfied"  # every declared gate closed

    return {
        "id": milestone_id,
        "title": title,
        "target_window": target_window,
        "contains": contains,
        "excluded": excluded,
        "effort_rollup": sum_estimates(estimates),
        "poc_gated": any_gate_declared and not any_gate_unsatisfied,
        # `poc_gated` alone cannot distinguish "nothing was gated" from "a
        # gate was declared but is not yet satisfied" -- both render False.
        # `poc_gate_status` carries that distinction explicitly.
        "poc_gate_status": poc_gate_status,
        "dropped_estimates": dropped_estimates,
        "unmapped_sizes": unmapped_sizes,
        "depends_on": depends_on,
    }


# ---------------------------------------------------------------------------
# Cycle-safe depends_on resolution across milestones
# ---------------------------------------------------------------------------

def _coerce_depends_on(value: Any) -> List[str]:
    """Coerce a milestone's raw `depends_on` field to a list of str ids
    before `detect_cycles()`'s `list()`/membership walk. A hand-edited bare
    (non-list) string (`depends_on: MS-2`) reads as the single dependency it
    names -- the old bare `list(depends_on)` char-iterated it into
    `['M','S','-','2']` instead, none of which ever matches a real
    `MS-<n>` id, so the real dependency (and the cycle it would complete)
    went undetected. A bare non-string scalar (`depends_on: 5`) cannot be
    wrapped into a real id and is dropped to `[]` rather than `TypeError`ing
    `list()`. Inside an actual list, only string entries survive.

    Deliberately NOT `id_grammar.as_str_list` here (a DRY reviewer will flag
    the divergence): `as_str_list` str()-coerces every entry, including a
    non-string one -- `detect_cycles()`'s cycle-detection integrity depends
    on `graph[node]` never containing a coerced id that cannot possibly
    match a real `MS-<n>` key, so an entry that was never a string is
    dropped here rather than str()-coerced into a phantom edge."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def _scc_tarjan(adj: Dict[str, List[str]]) -> List[List[str]]:
    """Iterative Tarjan's strongly-connected-components over `adj`.

    Deliberately duplicated (not imported) from
    `check_traceability._scc_tarjan` in the spec skill: spec is the lower
    layer in the one-way spec↔shape boundary, so importing across it here
    would add runtime coupling (plus isolated-loader complexity) for a
    small, stable, standard algorithm. Keep the two copies in sync by hand.

    Only edges landing on another key of `adj` are followed -- a `depends_on`
    target absent from `adj` (dangling) is skipped, mirroring every other
    walk in this module.

    A node is on a REAL cycle iff it sits in an SCC of size > 1, or it has a
    self-loop (a size-1 SCC whose sole member also appears in its own
    adjacency list). The prior 3-color DFS conflated "already fully
    explored" (BLACK) with "cannot possibly close a cycle" -- a node
    reachable only through an already-BLACK sibling branch (a diamond:
    MS-1->[MS-2,MS-3], MS-2->MS-4, MS-3->MS-4, MS-4->MS-1) never got its
    back-edge re-examined once that shared descendant (MS-4) was marked
    done by the first branch, so the second branch's membership in the same
    cycle went unreported. Tarjan's `lowlink` propagates reachability
    correctly regardless of visit order, closing that gap.

    Iterative (explicit frame stack), not recursive: a plain recursive walk
    raises RecursionError once a `depends_on` chain exceeds Python's default
    recursion limit (~1000) -- `frames` stands in for the call stack so a
    long chain degrades gracefully instead of crashing."""
    index_of: Dict[str, int] = {}
    lowlink: Dict[str, int] = {}
    on_tstack: Dict[str, bool] = {}
    tstack: List[str] = []
    sccs: List[List[str]] = []
    counter = 0

    for root in sorted(adj):
        if root in index_of:
            continue
        index_of[root] = lowlink[root] = counter
        counter += 1
        tstack.append(root)
        on_tstack[root] = True
        frames: List[Tuple[str, Any]] = [(root, iter(sorted(adj.get(root, []))))]
        while frames:
            node, it = frames[-1]
            descended = False
            for nbr in it:
                if nbr not in adj:
                    continue
                if nbr not in index_of:
                    index_of[nbr] = lowlink[nbr] = counter
                    counter += 1
                    tstack.append(nbr)
                    on_tstack[nbr] = True
                    frames.append((nbr, iter(sorted(adj.get(nbr, [])))))
                    descended = True
                    break
                elif on_tstack.get(nbr):
                    lowlink[node] = min(lowlink[node], index_of[nbr])
            if descended:
                continue
            frames.pop()
            if frames:
                parent = frames[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[node])
            if lowlink[node] == index_of[node]:
                scc: List[str] = []
                while True:
                    w = tstack.pop()
                    on_tstack[w] = False
                    scc.append(w)
                    if w == node:
                        break
                sccs.append(scc)
    return sccs


def detect_cycles(milestones: Sequence[Dict[str, Any]]) -> Set[str]:
    """Return the set of milestone ids participating in a `depends_on` cycle
    (including a self-loop). A `depends_on` id absent from `milestones`
    (dangling) is skipped, never raised on.

    Built on `_scc_tarjan`'s complete SCC membership rather than a
    back-edge-per-DFS-path walk (see that helper's docstring for the diamond
    case the old walk under-reported)."""
    # Union same-id records' edges rather than a plain dict comprehension:
    # two milestone entries can carry the SAME id (a hand-edited roadmap.md,
    # or two assemble_roadmap specs both naming MS-1 -- add_milestone_locked
    # dedupes, assemble does not), and a comprehension keeps only the LAST
    # copy's `depends_on`, silently discarding an earlier copy's edges. If the
    # cyclic edge lived on an earlier copy and a later copy declared `[]`, the
    # cycle vanished -- and swapping the two copies' order flipped detection,
    # making it pure list-order luck. Unioning (accumulate + dedupe, mirroring
    # serves_resolver.resolve_serves) means ANY copy declaring the cyclic edge
    # surfaces the cycle: cycle detection is fail-safe toward reporting, never
    # order-dependent masking.
    graph: Dict[str, List[str]] = {}
    for m in milestones:
        mid = m.get("id")
        if not mid:
            continue
        edges = graph.setdefault(mid, [])
        for dep in _coerce_depends_on(m.get("depends_on")):
            if dep not in edges:
                edges.append(dep)
    in_cycle: Set[str] = set()
    for scc in _scc_tarjan(graph):
        if len(scc) > 1:
            in_cycle.update(scc)
        else:
            node = scc[0]
            if node in graph.get(node, []):
                in_cycle.add(node)
    return in_cycle


# ---------------------------------------------------------------------------
# Read / write the single roadmap sidecar document
# ---------------------------------------------------------------------------

def _render_body(milestones: Sequence[Dict[str, Any]]) -> str:
    lines = ["# Roadmap", ""]
    for m in milestones:
        header = "## %s — %s" % (m.get("id", ""), m.get("title") or m.get("id", ""))
        if m.get("target_window"):
            header += " (%s)" % m["target_window"]
        lines.append(header)
        lines.append("- effort_rollup: %s" % m.get("effort_rollup", "0d"))
        lines.append("- poc_gated: %s" % m.get("poc_gated", False))
        # Coerce a whole non-list `contains` first (a hand-edited bare string
        # `contains: TASK-1` would otherwise char-split to "T, A, S, K, -, 1"
        # and be written back), then str()-coerce entries (skip only None) so a
        # hand-edited `contains: [1, 2]` cannot TypeError the join.
        #
        # Deliberately NOT `id_grammar.as_str_list` here (a DRY reviewer will
        # flag the divergence): `as_str_list` str()-coerces a `None` list
        # entry into the literal string `"None"`, which would render a
        # visible "None" into this DISPLAY-only join; dropping `None` here
        # keeps the rendered `contains:` line clean instead.
        contains_val = m.get("contains")
        if not isinstance(contains_val, list):
            contains_val = [] if contains_val is None else [contains_val]
        contains_str = ", ".join(str(c) for c in contains_val if c is not None)
        # `%` binds tighter than `or`: the old `"- contains: %s" % contains_str
        # or "- contains: (none)"` formatted the LHS first, which is always a
        # non-empty string (the "- contains: " prefix alone), so the `or`
        # fallback could never fire -- an empty `contains` rendered a bare
        # "- contains: " instead of the intended "(none)".
        lines.append(("- contains: %s" % contains_str) if contains_str else "- contains: (none)")
        if m.get("cycle"):
            lines.append("- cycle: true (depends_on forms a cycle -- resolve before committing)")
        lines.append("")
    if not milestones:
        lines.append("(no milestones yet)")
    return "\n".join(lines)


def read_roadmap(root: RootLike) -> Dict[str, Any]:
    """Read the roadmap sidecar's frontmatter. Returns `{"milestones": []}`
    when the file does not exist yet or is malformed -- a roadmap that has
    never been rolled up is a valid starting state, not an error.

    Routed through `frontmatter_parser.parse_text` (the hardened SSOT)
    instead of a locally hand-tuned `_FRONTMATTER_RE` + `yaml.safe_load` +
    `(yaml.YAMLError, ValueError)` catch: PyYAML raises a wider family than
    that pair on malformed frontmatter -- e.g. a bare `AttributeError` from
    `construct_yaml_timestamp` on an explicit-tag `ts: !!timestamp 'not a
    ts'` -- and the SSOT already fails soft on the whole family in one place."""
    path = roadmap_file(root)
    if not path.is_file():
        return {"milestones": []}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {"milestones": []}
    fp = _load_frontmatter_parser()
    parsed = fp.parse_text(text, file_label=str(path))
    if not parsed["ok"]:
        return {"milestones": []}
    fm = parsed["frontmatter"]
    # Keep only well-formed milestone entries: a dict with a non-empty STRING
    # `id`. A bare-string `milestones:` or a non-dict element would blow up the
    # first downstream `.get()` with AttributeError; worse, a hand-edited
    # non-string `id` (e.g. `id: {a: 1}`, valid YAML) is unhashable and crashes
    # `detect_cycles` (which keys its graph by `id`) with a raw TypeError,
    # taking down every read AND poisoning the locked read-merge-write add path.
    # Filtering here mirrors serves_resolver.list_task_records' `id` guard.
    milestones = fm.get("milestones")
    if not isinstance(milestones, list):
        milestones = []
    else:
        milestones = [m for m in milestones
                      if isinstance(m, dict) and isinstance(m.get("id"), str) and m.get("id")]
    fm["milestones"] = milestones
    return fm


def write_roadmap(root: RootLike, milestones: Sequence[Dict[str, Any]], actor: Optional[str] = None) -> Path:
    """Annotate `milestones` with cycle membership and write the roadmap
    sidecar in one shot -- the roadmap is always rewritten whole (unlike the
    one-file-per-record siblings), since it is one small aggregate document,
    not a growing per-record set."""
    in_cycle = detect_cycles(milestones)
    annotated = []
    for m in milestones:
        m2 = dict(m)
        m2["cycle"] = m2.get("id") in in_cycle
        annotated.append(m2)

    record: Dict[str, Any] = {
        "milestones": annotated,
        "generated_ts": _now_iso(),
        "actor": actor or _default_actor(),
    }
    body = _render_body(annotated)
    target = roadmap_file(root)
    write_record(target, record, body)
    return target


# ---------------------------------------------------------------------------
# Assemble: build every milestone spec, cycle-annotate, write
# ---------------------------------------------------------------------------

def _roadmap_lock_path(root: RootLike) -> Path:
    """The roadmap sidecar's own lock file, mirroring `task_model.py`'s
    `.tasks.lock` idiom -- `add_milestone_locked` takes an exclusive flock
    on this file for its whole read -> merge -> write sequence."""
    path = roadmap_file(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.parent / ".roadmap.lock"


def add_milestone_locked(
    root: RootLike,
    milestone_id: str,
    actor: Optional[str] = None,
    **build_kwargs: Any,
) -> Dict[str, Any]:
    """Build one milestone and merge+write it into the roadmap sidecar as a
    single lock-guarded read -> merge -> write -- the CLI's `--add-milestone`
    used to read the existing milestone list, build the new one, then write
    the merged list back with no lock spanning that whole sequence: two
    concurrent `--add-milestone` calls could both read the same `existing`
    list before either wrote, so the second writer's update silently
    clobbered the first's (confirmed 7/15 concurrent updates surviving).
    Locking only the final `write_roadmap()` call would not have closed this
    -- the read of `existing` happens before that write -- so the lock has
    to span the read too, exactly like `task_model.author()`'s
    allocate-then-write critical section."""
    lock_path = _roadmap_lock_path(root)
    with open(lock_path, "a+") as lock_fd:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        try:
            new_milestone = build_milestone(root, milestone_id, **build_kwargs)
            existing = read_roadmap(root).get("milestones") or []
            milestones = [m for m in existing if m.get("id") != milestone_id] + [new_milestone]
            write_roadmap(root, milestones, actor=actor)
            return new_milestone
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)


def assemble_roadmap(
    root: RootLike,
    milestone_specs: Sequence[Dict[str, Any]],
    actor: Optional[str] = None,
) -> Dict[str, Any]:
    """`milestone_specs` is a list of kwargs dicts for `build_milestone`
    (each must carry at least `milestone_id`). Builds every milestone, cycle-annotates
    the batch, writes the roadmap sidecar once, and returns the written
    record plus its path."""
    built = [build_milestone(root, **spec) for spec in milestone_specs]
    target = write_roadmap(root, built, actor=actor)
    written = read_roadmap(root)
    written["path"] = str(target)
    return written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="roadmap_rollup.py",
        description="Roll dev tasks up into milestones with an effort figure, "
        "gated on each declared technical-POC precondition. Never mutates a "
        "PO story or a POC record.",
    )
    p.add_argument("--root", required=True, help="workspace root (holds docs/product/)")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--add-milestone", action="store_true", help="build + append one milestone")
    mode.add_argument("--list", action="store_true", help="print current roadmap milestones")
    p.add_argument("--id", default=None, help="MS-<n> id (required with --add-milestone)")
    p.add_argument("--title", default="")
    p.add_argument("--target-window", default="")
    p.add_argument("--task-ids", default="", help="comma-separated TASK-<n> ids")
    p.add_argument("--depends-on", default="", help="comma-separated MS-<n> ids")
    p.add_argument("--task-poc-map", default="", help="comma-separated task_id:poc_id pairs")
    p.add_argument("--actor", default=None)
    return p


def _parse_task_poc_map(raw: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        task_id, poc_id = pair.split(":", 1)
        if task_id.strip() and poc_id.strip():
            out[task_id.strip()] = poc_id.strip()
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_argparser().parse_args(argv)
    if args.add_milestone:
        if not args.id:
            print("error: --add-milestone requires --id", file=sys.stderr)
            return 1
        task_ids = [t.strip() for t in args.task_ids.split(",") if t.strip()]
        depends_on = [d.strip() for d in args.depends_on.split(",") if d.strip()]
        task_poc_map = _parse_task_poc_map(args.task_poc_map)
        try:
            new_milestone = add_milestone_locked(
                args.root, args.id, title=args.title, target_window=args.target_window,
                task_ids=task_ids, depends_on=depends_on, task_poc_map=task_poc_map,
                actor=args.actor,
            )
        except (RoadmapError, SidecarError) as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 1
        # The "loud" skip on unmapped_sizes/dropped_estimates was previously
        # only a stored record field -- an operator running this CLI never
        # saw it unless they went looking at the roadmap sidecar by hand.
        if new_milestone.get("unmapped_sizes"):
            print(
                "warning: %d task(s) had an unmapped story size -- excluded "
                "from effort_rollup" % len(new_milestone["unmapped_sizes"]),
                file=sys.stderr,
            )
        if new_milestone.get("dropped_estimates"):
            # Not "dropped from effort_rollup": when a linked story size
            # exists, `estimate_for_task` already fell back to a
            # size-derived range and that range still folds into
            # effort_rollup -- only the BA's own (malformed/unparsable)
            # figure was ignored, not the effort itself.
            print(
                "warning: %d task(s) had a non-string or unparsable estimate "
                "-- BA estimate ignored; effort leaned on story size"
                % len(new_milestone["dropped_estimates"]),
                file=sys.stderr,
            )
        print("%s\t%s\t%s" % (new_milestone["id"], new_milestone["effort_rollup"],
                               "poc_gated" if new_milestone["poc_gated"] else "advisory"))
        return 0
    if args.list:
        for m in read_roadmap(args.root).get("milestones") or []:
            print("%s\t%s\t%s" % (m.get("id", ""), m.get("effort_rollup", ""),
                                   m.get("target_window", "")))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
