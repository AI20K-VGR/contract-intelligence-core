#!/usr/bin/env python3
"""check_standards — structural traceability checks over the standards graph.

No judgment. Detects, mapped to the standards hierarchy:

- orphan_rule / orphan_rule_group / orphan_std_area  (error)
      a node with NO parent reference declared at all.
- orphan_arch_goal                                   (warn)
      an arch_goal with no std_area addressing it.
- dangling_link                                      (error)
      a declared parent-link id reference that does not resolve to a real node.
- dep_dangling                                       (error)
      a depends_on target that does not resolve (the same dangling family).
- unaddressed_parent                                 (warn)
      a parent (std_area/rule_group) with zero inbound child edges of the
      expected type.
- dep_cycle                                          (error)
      a circular depends_on chain.
- invalid_id                                         (error)
      a node id that fails its type's grammar (from the id-grammar framework).
- duplicate_id                                       (error)
      one id carried by more than one node — would otherwise collapse in every
      id-set and mask the duplicated/missing node.
- parse_error                                        (error)
      a malformed artifact surfaced by the builder.

orphan vs dangling_link: orphan = no reference declared; dangling_link = a
reference IS declared but points at a ghost id. Distinct findings so the report
tells the author "you forgot to link" vs "your link is broken".

Always exits 0; emits {findings, graph} JSON. The gate does the blocking.

CLI:
    check_standards.py --root <project-dir>
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

import graph_core
import standards_graph
from encoding_utils import configure_utf8_console, emit_json

configure_utf8_console()


# parent-link field name + the orphan check id per child type. orphan = the link
# field is missing/empty; dangling = the link names a ghost.
_PARENT_LINK = {
    "rule": ("rule_group", "orphan_rule"),
    "rule_group": ("std_area", "orphan_rule_group"),
}


def check(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    node_ids: Set[str] = {n["id"] for n in graph["nodes"]}
    child_counts = graph_core.matching_child_counts(
        graph, standards_graph.CHILD_TYPE_FOR_PARENT)

    for n in graph["nodes"]:
        ntype = n["type"]

        # scalar parent links (rule->rule_group, rule_group->std_area)
        if ntype in _PARENT_LINK:
            field, orphan_check = _PARENT_LINK[ntype]
            ref = n.get(field)
            if not ref:
                findings.append(graph_core.make_finding(
                    orphan_check, "error", n,
                    f"{n['id']} has no {field} reference."))
            elif not isinstance(ref, str):
                pass  # bad shape (builder coerces to None) — tolerate, don't flag
            elif ref not in node_ids:
                findings.append(graph_core.make_finding(
                    "dangling_link", "error", n,
                    f"{n['id']} references unknown {field} {ref}.", ref=ref))

        # std_area: arch_goals is a list (may name multiple goals)
        elif ntype == "std_area":
            goals = n.get("arch_goals")
            # An operational-zone area is self-rooted (H2: org-charter ⟂
            # operational) — it is NOT required to address a charter goal, so a
            # missing arch_goals there is not an orphan. A declared (but
            # dangling) goal is still checked below for both zones.
            if not goals and n.get("zone") != "operational":
                findings.append(graph_core.make_finding(
                    "orphan_std_area", "error", n,
                    f"{n['id']} declares no arch_goals it addresses."))
            elif isinstance(goals, list):
                for g in goals:
                    if not isinstance(g, str):
                        continue  # bad shape — not char-split, not flagged here
                    if g not in node_ids:
                        findings.append(graph_core.make_finding(
                            "dangling_link", "error", n,
                            f"{n['id']} references unknown arch_goal {g}.", ref=g))

        # unaddressed-parent / orphan-arch-goal via the shared child counts
        if ntype in standards_graph.CHILD_TYPE_FOR_PARENT:
            expected_child = standards_graph.CHILD_TYPE_FOR_PARENT[ntype]
            if child_counts.get(n["id"], 0) == 0:
                check_id = "orphan_arch_goal" if ntype == "arch_goal" else "unaddressed_parent"
                findings.append(graph_core.make_finding(
                    check_id, "warn", n,
                    f"{n['id']} has no {expected_child} addressing it (gap-analysis input).",
                    expected_child=expected_child))

    findings.extend(_check_duplicate_ids(graph))
    findings.extend(_check_dep_dangling(graph, node_ids))
    findings.extend(_check_dep_cycles(graph))
    findings.extend(graph_core.id_grammar_findings(
        graph["nodes"], standards_graph.ID_PATTERN_BY_TYPE))

    for parse_err in graph.get("parse_errors", []):
        findings.append({
            "check": "parse_error",
            "severity": "error",
            "artifact_id": None,
            "file": parse_err["file"],
            "detail": parse_err["error"],
            "context": None,
        })
    return findings


def _check_duplicate_ids(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    """One error per id carried by more than one node.

    Every other check builds its id index as a set, so two artifacts declaring
    the same id silently collapse to one node — a copy-pasted duplicate can then
    mask a genuinely missing node and let dangling/orphan pass wrongly. Counting
    the raw node list (which the builder leaves un-deduped) names the collision
    before the set-based masking can happen.
    """
    findings: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}
    first: Dict[str, Dict[str, Any]] = {}
    for n in graph["nodes"]:
        nid = n["id"]
        counts[nid] = counts.get(nid, 0) + 1
        first.setdefault(nid, n)
    for nid in sorted(c for c in counts if counts[c] > 1):
        findings.append(graph_core.make_finding(
            "duplicate_id", "error", first[nid],
            f"{nid} is declared by {counts[nid]} nodes (ids must be unique).",
            count=counts[nid]))
    return findings


def _build_dep_adj(graph: Dict[str, Any]) -> Dict[str, List[str]]:
    """node id -> its depends_on targets (already sorted at the graph layer)."""
    return {n["id"]: list(n.get("depends_on") or []) for n in graph["nodes"]}


def _check_dep_dangling(graph: Dict[str, Any], node_ids: Set[str]) -> List[Dict[str, Any]]:
    """Flag any depends_on target that does not resolve to a real node."""
    findings: List[Dict[str, Any]] = []
    for n in graph["nodes"]:
        for dep in n.get("depends_on") or []:
            if dep not in node_ids:
                findings.append(graph_core.make_finding(
                    "dep_dangling", "error", n,
                    f"{n['id']} depends_on unknown standard {dep}.", ref=dep))
    return findings


def _check_dep_cycles(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Emit one dep_cycle error per detected cycle; context.cycle is the closed path."""
    findings: List[Dict[str, Any]] = []
    nodes_by_id = {n["id"]: n for n in graph["nodes"]}
    for cycle in graph_core.find_dep_cycles(_build_dep_adj(graph)):
        anchor = nodes_by_id.get(cycle[0], {"id": cycle[0]})
        findings.append(graph_core.make_finding(
            "dep_cycle", "error", anchor,
            f"Circular depends_on chain: {' -> '.join(cycle)}.", cycle=cycle))
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    graph = standards_graph.build_graph(root)
    findings = check(graph)
    emit_json({
        "schema_version": "1.0",
        "root": str(root),
        "checked_at": graph_core._now(),
        "findings": findings,
        "graph": graph,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
