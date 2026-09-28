#!/usr/bin/env python3
"""
check_traceability — structural traceability checks. No judgment.

Detects:
- orphan_story / orphan_epic / orphan_prd  (referenced parent does not exist)
- dangling_link                            (any frontmatter ID reference unresolved)
- parent_type_mismatch                     (parent ref resolves to a real id of the wrong TYPE)
- unaddressed_parent                       (a parent with zero inbound child edges)
- orphan_brd_goal                          (BRD goal with no PRD addressing it)

Emits findings JSON per validation-rules-spec.md. Always exits 0.

CLI:
    check_traceability.py --root <project-dir>
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from encoding_utils import configure_utf8_console, emit_json
from spec_graph import (
    build_graph, _now, CHILD_TYPE_FOR_PARENT, matching_child_counts,
    make_finding as _f,
)

configure_utf8_console()


def check(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    node_ids: Set[str] = {n["id"] for n in graph["nodes"]}
    # Type by id, so a parent reference can be checked for correct KIND, not just
    # existence: a story's `epic:` naming a real PRD id resolves past the
    # dangling_link (existence) check yet silently corrupts the traceability
    # matrix (the Epic column shows a PRD id). A last-wins collision on a
    # duplicate id is harmless here — dup_id is check_consistency's job.
    node_type: Dict[str, str] = {n["id"]: n["type"] for n in graph["nodes"]}
    # Shared expected-child counts (one pass over the edges); the gap views key
    # off the same helper so views and validator never disagree on a gap.
    child_counts = matching_child_counts(graph)

    for n in graph["nodes"]:
        ntype = n["type"]
        if ntype == "story":
            if not n.get("epic"):
                findings.append(_f("orphan_story", "error", n, "Story has no epic reference."))
            elif n["epic"] not in node_ids:
                findings.append(_f("dangling_link", "error", n, f"Story references unknown epic {n['epic']}.", ref=n["epic"]))
            elif node_type.get(n["epic"]) != "epic":
                findings.append(_f("parent_type_mismatch", "error", n, f"Story's epic reference {n['epic']} resolves to a {node_type.get(n['epic'])}, not an epic.", ref=n["epic"]))
        elif ntype == "epic":
            if not n.get("prd"):
                findings.append(_f("orphan_epic", "error", n, "Epic has no PRD reference."))
            elif n["prd"] not in node_ids:
                findings.append(_f("dangling_link", "error", n, f"Epic references unknown PRD {n['prd']}.", ref=n["prd"]))
            elif node_type.get(n["prd"]) != "prd":
                findings.append(_f("parent_type_mismatch", "error", n, f"Epic's PRD reference {n['prd']} resolves to a {node_type.get(n['prd'])}, not a PRD.", ref=n["prd"]))
        elif ntype == "prd":
            brd_goals = n.get("brd_goals")
            if not brd_goals:
                findings.append(_f("orphan_prd", "error", n, "PRD has no BRD goals declared."))
            elif not isinstance(brd_goals, list):
                # A bare string (hand-edit regression) would iterate per character
                # producing phantom "unknown BRD goal B/R/D/-/G/1" findings. The
                # invalid_type finding is check_consistency's job (LIST_FIELDS home);
                # emitting it here too counts it TWICE in strict_gate. Just skip.
                pass
            else:
                seen_goals: set = set()
                for g in brd_goals:
                    # A non-string element (dict/list from a hand-edit) is
                    # unhashable; `g not in node_ids` would raise TypeError and
                    # crash the gate. invalid_type owns the shape error
                    # (check_consistency); skip so membership never hashes it.
                    # Dedupe a repeated `brd_goals:[G,G]` so one edge is one
                    # finding (same dedupe class as depends_on / serves).
                    if not isinstance(g, str) or g in seen_goals:
                        continue
                    seen_goals.add(g)
                    if g not in node_ids:
                        findings.append(_f("dangling_link", "error", n, f"PRD references unknown BRD goal {g}.", ref=g))
                    elif node_type.get(g) != "goal":
                        findings.append(_f("parent_type_mismatch", "error", n, f"PRD's brd_goals reference {g} resolves to a {node_type.get(g)}, not a goal.", ref=g))

        if ntype in CHILD_TYPE_FOR_PARENT:
            expected_child = CHILD_TYPE_FOR_PARENT[ntype]
            if child_counts.get(n["id"], 0) == 0:
                check_id = "orphan_brd_goal" if ntype == "goal" else "unaddressed_parent"
                findings.append(_f(check_id, "warn", n, f"{n['id']} has no {expected_child} addressing it (gap-analysis input).", expected_child=expected_child))

    findings.extend(_check_dep_dangling(graph, node_ids))
    findings.extend(_check_dep_cycles(graph))

    for parse_err in graph.get("parse_errors", []):
        findings.append({
            "check": "parse_error",
            "severity": "error",
            "artifact_id": None,
            "file": parse_err["file"],
            "detail": parse_err["error"],
        })
    return findings


# ── depends_on graph family (lives here beside dangling_link) ────────────────
#
# The `depends_on: [ID]` edge joins the dangling family already owned by this
# module: an unresolved target is `dep_dangling` (error, beside dangling_link),
# and a circular chain is `dep_cycle` (error). Keeping the whole graph-walk
# dependency family in one home means a hierarchy/edge change edits one file.


def _build_dep_adj(graph: Dict[str, Any]) -> Dict[str, List[str]]:
    """node id -> sorted list of its depends_on targets, for every node that
    declares the edge. Sorted at the graph layer (spec_graph stores it sorted),
    so the cycle walk's iteration order — and thus its output — is deterministic
    (byte-deterministic). Targets that do not resolve to a real node are still included here:
    `dep_dangling` owns the missing-ID report; the cycle walk simply skips any
    target that is not itself a key (it cannot be on a cycle)."""
    adj: Dict[str, List[str]] = {}
    for n in graph["nodes"]:
        adj[n["id"]] = list(n.get("depends_on") or [])
    return adj


def _scc_tarjan(adj: Dict[str, List[str]]) -> List[List[str]]:
    """Iterative Tarjan's strongly-connected-components over `adj`.

    Deliberately duplicated (not imported) from `roadmap_rollup._scc_tarjan`
    in the shape skill: this module is the lower layer in the spec↔shape
    one-way boundary and must not depend on shape, and shape reaching down
    into spec for a small, stable, standard algorithm would add runtime
    coupling for no real payoff. Keep the two copies in sync by hand.

    Only edges landing on another key of `adj` are followed — a target absent
    from `adj` (dangling) is skipped; `dep_dangling` owns that report.

    The prior 3-color DFS (white/gray/black) conflated "already fully
    explored" (BLACK) with "cannot possibly close a cycle": a node reachable
    only through an already-BLACK sibling branch — a diamond
    ``MS-1->[MS-2,MS-3], MS-2->MS-4, MS-3->MS-4, MS-4->MS-1`` — never got its
    back-edge re-examined once that shared descendant (MS-4) was marked done
    by the first branch explored, so the second branch's membership in the
    same cycle went unreported (order-dependent under-count). Tarjan's
    `lowlink` propagates reachability correctly regardless of visit order.

    Iterative (explicit frame stack), not recursive — a ~2000-deep linear
    chain cannot RecursionError."""
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


# Elementary-cycle enumeration inside one SCC is worst-case factorial in the
# SCC's size (a complete digraph on n=10 already emits ~1.1M cycles / ~2.7s;
# n=12-15 -- an ordinary PRD/epic depends_on count -- runs minutes-to-hours).
# `check` runs on every `--validate`, so a hand-edited copy-paste that
# happens to produce a dense component must not be able to hang the gate.
#
# A node-COUNT size gate is density-BLIND: a sparse 9-node dependency ring
# has exactly one elementary cycle (trivial to enumerate) but a size gate
# keyed on `len(scc)` would reject it purely for having 9 members, and a
# realistic spec/epic graph can easily have a 9+ item ring. The bound tracks
# actual WORK done, not node count, so it stays generous across the realistic
# range (rings/chains of tens of nodes enumerate in milliseconds) and trips
# only when the search does genuinely large work. Two independent trip wires,
# either enough to fall back to `_dense_scc_marker`:
#   - step budget: counts backtracking steps (neighbor visits) spent while
#     enumerating one SCC across all its `start` nodes combined. Sized
#     generously (tens of thousands of steps) for any realistic depends_on
#     graph; a K12+ complete digraph blows it in well under a second. Note it
#     bounds WORK, not node count in the graph-theory sense: on a very large
#     ring (hundreds of nodes) whose ids sort in the SAME direction the edges
#     walk -- a sequentially-numbered chain like STORY-001 -> STORY-002 -> ...
#     -> STORY-N -> STORY-001 -- each non-minimal `start` re-walks an O(n) tail
#     of the induced subgraph before dead-ending, O(n^2) total, so such a ring
#     reaches the budget at a few hundred nodes and falls to the membership
#     marker (a shuffled-id ring of the same size, whose sort order does not
#     track its edges, stays well under budget). That is a graceful precision
#     trade -- the cycle's full membership is still reported and still blocks
#     the gate, not a missed detection -- and realistic spec graphs are far
#     smaller.
#   - cycle-count cap: a secondary OUTPUT-size bound, not a work bound — even
#     a search that stays inside the step budget stops emitting once a
#     single SCC's cycle count would exceed this (nobody reads more). It is
#     enforced by letting the search run one cycle past the cap and only
#     then declaring "more exist" (see `_cycles_through_start`), so hitting
#     the cap EXACTLY (the true count equals the cap) is reported as
#     complete, not capped.
_MAX_SCC_STEPS = 50_000
_MAX_CYCLES_PER_SCC = 500


def _cycles_through_start(
    adj: Dict[str, List[str]], induced: Set[str], start: str, limit: int, step_budget: int,
) -> Tuple[List[List[str]], bool, int]:
    """Every elementary (simple) cycle within the subgraph induced by
    `induced` that begins and ends at `start`. Returns `(cycles, stopped_early,
    steps_used)`.

    Two independent trip wires can cut the search short, both reported via
    `stopped_early=True`:
      - the `step_budget` (a count of backtracking steps — one per neighbor
        examined) runs out while frames remain unexplored;
      - more than `limit` cycles would be reported — detected by letting the
        search find ONE cycle past `limit` and trimming it off, so reaching
        `limit` exactly via true exhaustion is never confused with being cut
        short. (A naive `len(cycles) >= limit` check would report capped the
        instant the Nth cycle is found, even when that Nth cycle is also the
        LAST one the search would ever find — the one-past-limit probe avoids
        that false "more exist".)

    Iterative backtracking over an explicit frame stack (node,
    neighbor-iterator, path-so-far) — no recursion. Restricting `induced` to
    nodes >= `start` (by the caller) is the standard trick that lets each
    elementary cycle in an SCC be attributed to exactly one of its members
    (its lexicographically-least node), so iterating every SCC member as a
    `start` never double-reports the same cycle."""
    cycles: List[List[str]] = []
    steps = 0
    frames: List[Tuple[str, Any, List[str]]] = [
        (start, iter(sorted(set(n for n in adj.get(start, []) if n in induced))), [start])
    ]
    while frames:
        if steps >= step_budget:
            return cycles, True, steps
        node, it, path = frames[-1]
        descended = False
        for nxt in it:
            steps += 1
            if nxt == start:
                cycles.append(path + [start])
                if len(cycles) > limit:
                    return cycles[:limit], True, steps
                continue
            if nxt in path:
                continue
            if steps >= step_budget:
                return cycles, True, steps
            nbrs = iter(sorted(set(n for n in adj.get(nxt, []) if n in induced)))
            frames.append((nxt, nbrs, path + [nxt]))
            descended = True
            break
        if not descended:
            frames.pop()
    return cycles, False, steps


def _dense_scc_marker(scc: List[str]) -> List[str]:
    """A single closed-path stand-in for an SCC too combinatorially expensive
    to enumerate within budget: the sorted membership, closed like a real
    cycle path (first == last) so it still satisfies `find_dep_cycles`'s
    return shape, plus a trailing note element `_check_dep_cycles` folds into
    the finding's human-readable message. Reports exactly what an operator
    needs to act — which nodes are circular — without pretending to be one
    specific elementary path."""
    members = sorted(scc)
    return members + [
        members[0],
        "(component too complex to enumerate every elementary cycle within budget; showing membership only)",
    ]


def find_dep_cycles(adj: Dict[str, List[str]]) -> List[List[str]]:
    """Return every elementary dependency cycle in `adj` as a closed path,
    e.g. ``["A", "B", "A"]`` — except an SCC that blows the work/output
    budget (see `_MAX_SCC_STEPS`/`_MAX_CYCLES_PER_SCC`), which collapses to
    one `_dense_scc_marker` entry reporting membership instead of every path.

    Built on `_scc_tarjan` for COMPLETE cycle-membership (see that helper's
    docstring for the diamond case the old back-edge-per-DFS-path walk
    under-reported), then `_cycles_through_start` enumerates every
    elementary cycle inside each strongly-connected component of size > 1
    (a size-1 SCC is a cycle only via a self-loop). `_MAX_SCC_STEPS` is a
    single shared budget spent across every `start` node of one SCC (not
    reset per `start`) — a sparse ring stays cheap across its whole scan, a
    dense component exhausts the shared budget quickly regardless of which
    `start` triggers it. Sorted iteration throughout keeps the output
    byte-deterministic."""
    cycles: List[List[str]] = []
    for scc in sorted(_scc_tarjan(adj), key=min):
        if len(scc) == 1:
            node = scc[0]
            if node in adj.get(node, []):
                cycles.append([node, node])
            continue
        scc_cycles: List[List[str]] = []
        capped = False
        steps_remaining = _MAX_SCC_STEPS
        for start in sorted(scc):
            induced = {n for n in scc if n >= start}
            found, stopped_early, steps_used = _cycles_through_start(
                adj, induced, start, _MAX_CYCLES_PER_SCC - len(scc_cycles), steps_remaining
            )
            scc_cycles.extend(found)
            steps_remaining -= steps_used
            if stopped_early:
                capped = True
                break
        if capped:
            cycles.append(_dense_scc_marker(scc))
        else:
            cycles.extend(scc_cycles)
    return cycles


def _check_dep_dangling(graph: Dict[str, Any], node_ids: Set[str]) -> List[Dict[str, Any]]:
    """Flag any `depends_on` target that does not resolve to a real artifact.

    Same dangling family as `dangling_link` (parent edges) — a depends_on edge
    pointing at a ghost ID is `dep_dangling` (error). Independent of the type
    guard (check_consistency) — even a wrongly-placed depends_on is still
    checked for resolvability here."""
    findings: List[Dict[str, Any]] = []
    for n in graph["nodes"]:
        for dep in n.get("depends_on") or []:
            if dep not in node_ids:
                findings.append(_f(
                    "dep_dangling", "error", n,
                    f"{n['id']} depends_on unknown artifact {dep}.",
                    ref=dep,
                ))
    return findings


def _check_dep_cycles(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Emit one `dep_cycle` error per detected cycle; `context.cycle` carries the
    closed path. Anchored on the first node of the cycle path so the finding has
    a concrete `artifact_id`/`file`."""
    findings: List[Dict[str, Any]] = []
    nodes_by_id = {n["id"]: n for n in graph["nodes"]}
    for cycle in find_dep_cycles(_build_dep_adj(graph)):
        anchor = nodes_by_id.get(cycle[0], {"id": cycle[0]})
        findings.append(_f(
            "dep_cycle", "error", anchor,
            f"Circular depends_on chain: {' → '.join(cycle)}.",
            cycle=cycle,
        ))
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    graph = build_graph(root)
    findings = check(graph)
    output = {
        "schema_version": "1.0",
        "root": str(root),
        "checked_at": _now(),
        "findings": findings,
        "graph": graph,
    }
    emit_json(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
