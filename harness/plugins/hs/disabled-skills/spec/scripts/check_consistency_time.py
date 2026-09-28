"""
check_consistency_time — TIME-dimension structural checks for check_consistency.

All checks compare dates already on the graph (never the wall clock).
The wall-clock `overdue` advisory lives in time_advisory.py, outside this gate.
"""

import datetime as dt
import re
from typing import Any, Dict, List

from spec_graph import make_finding as _f

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Allowed artifact types for depends_on (non-empty list on any other type
# reuses the existing invalid_type finding).
DEPENDS_ON_ALLOWED_TYPES = ("prd", "epic")


def parse_iso_date(v: Any):
    """Coerce a node's target_date to a datetime.date for comparison, or None.

    PyYAML already parses a valid `YYYY-MM-DD` to datetime.date (or datetime).
    A str only reaches here if it slipped the shape gate; parse it leniently
    and return None on failure so a malformed value (already flagged invalid_type)
    simply drops out of the ordering checks.
    """
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, str) and _ISO_DATE_RE.match(v.strip()):
        try:
            return dt.date.fromisoformat(v.strip())
        except ValueError:
            return None
    return None


def check_target_date_shape(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    """target_date must be an ISO calendar date (YYYY-MM-DD). Absent is clean.
    A value PyYAML left as a non-ISO string is invalid_type."""
    v = node.get("target_date")
    if v is None:
        return []
    if isinstance(v, (dt.date, dt.datetime)):
        return []
    if isinstance(v, str) and _ISO_DATE_RE.match(v.strip()):
        try:
            dt.date.fromisoformat(v.strip())
            return []
        except ValueError:
            pass
    return [_f(
        "invalid_type", "error", node,
        f"Field target_date={v!r} must be a valid ISO calendar date (YYYY-MM-DD).",
        field="target_date", value=v,
    )]


def check_depends_on_type(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    """`depends_on` is allowed on PRD + Epic only. A non-empty list on any other
    artifact type reuses the EXISTING `invalid_type` finding (no new check id).
    An empty/absent list is always fine. A malformed (non-list scalar/mapping)
    depends_on is coerced to [] on the node so the adjacency/render consumers never
    char-split a bare string; the builder preserves the raw under
    `depends_on_invalid`, flagged here as the shape error — exactly like the sibling
    id-lists brd_goals/serves — so a typo'd dependency cannot vanish and pass
    --strict clean."""
    if "depends_on_invalid" in node:
        raw = node["depends_on_invalid"]
        return [_f(
            "invalid_type", "error", node,
            f"Field depends_on must be a YAML list of ids; got {type(raw).__name__}.",
            field="depends_on", value=raw,
        )]
    deps = node.get("depends_on")
    if not deps:
        return []
    if node.get("type") in DEPENDS_ON_ALLOWED_TYPES:
        return []
    return [_f(
        "invalid_type", "error", node,
        f"Field depends_on is only valid on {' or '.join(DEPENDS_ON_ALLOWED_TYPES)}; "
        f"{node['id']} is a {node.get('type')}.",
        field="depends_on", value=deps,
    )]


def time_child_late(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Warn when a child's target_date is AFTER its parent's (an epic due after
    its PRD finishes is incoherent). Only fires when BOTH dates parse."""
    findings: List[Dict[str, Any]] = []
    nodes_by_id = {n["id"]: n for n in graph["nodes"]}
    for n in graph["nodes"]:
        parent_id = n.get("epic") or n.get("prd")
        if not parent_id:
            continue
        parent = nodes_by_id.get(parent_id)
        if not parent:
            continue
        cd = parse_iso_date(n.get("target_date"))
        pd = parse_iso_date(parent.get("target_date"))
        if cd is None or pd is None:
            continue
        if cd > pd:
            findings.append(_f(
                "time_child_late", "warn", n,
                f"{n['id']} target_date {cd} is after parent {parent['id']} "
                f"target_date {pd}; a child cannot finish after its parent.",
                parent_id=parent["id"],
                child_target_date=str(cd),
                parent_target_date=str(pd),
            ))
    return findings


def dep_order(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Warn when A depends_on B but A.target_date < B.target_date — A is due
    before the prerequisite it waits on. Only fires when BOTH dates parse."""
    findings: List[Dict[str, Any]] = []
    nodes_by_id = {n["id"]: n for n in graph["nodes"]}
    for n in graph["nodes"]:
        ad = parse_iso_date(n.get("target_date"))
        if ad is None:
            continue
        for dep in n.get("depends_on") or []:
            target = nodes_by_id.get(dep)
            if not target:
                continue  # dep_dangling owns the missing-ID case
            bd = parse_iso_date(target.get("target_date"))
            if bd is None:
                continue
            if ad < bd:
                findings.append(_f(
                    "dep_order", "warn", n,
                    f"{n['id']} target_date {ad} is before its prerequisite "
                    f"{target['id']} target_date {bd}; A cannot complete before B.",
                    depends_on=dep,
                    target_date=str(ad),
                    prerequisite_target_date=str(bd),
                ))
    return findings


def dep_target_type(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    """A depends_on TARGET must be a PRD or Epic — the same `DEPENDS_ON_ALLOWED_TYPES`
    set depends_on is allowed to live ON. A resolved target of any other type (a
    story, a BRD goal, the PRODUCT/vision root) is a semantically-broken edge that
    slips past `dep_dangling` (target exists) and `dep_cycle` (not circular), so
    `--strict` reported green on it. Flag it `dep_type_mismatch` (error) — the
    depends_on-edge analogue of `parent_type_mismatch` on the parent-link fields.

    Skips a missing target (dep_dangling owns that) and a non-string entry
    (invalid_type owns the shape). Dedupes a hand-edited `depends_on:[X,X]` so one
    broken edge is one finding, matching the dep_dangling / serves dedupe class."""
    findings: List[Dict[str, Any]] = []
    node_type = {n["id"]: n.get("type") for n in graph["nodes"]}
    for n in graph["nodes"]:
        seen: set = set()
        for dep in n.get("depends_on") or []:
            if not isinstance(dep, str) or dep in seen:
                continue
            seen.add(dep)
            tt = node_type.get(dep)
            if tt is None:
                continue  # dep_dangling owns the missing-target case
            if tt not in DEPENDS_ON_ALLOWED_TYPES:
                findings.append(_f(
                    "dep_type_mismatch", "error", n,
                    f"{n['id']} depends_on {dep}, which is a {tt}, not a "
                    f"{' or '.join(DEPENDS_ON_ALLOWED_TYPES)}.",
                    ref=dep,
                ))
    return findings
