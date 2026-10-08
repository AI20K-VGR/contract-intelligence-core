"""Contract graph builder: operation units → resolved targets → typed edges + issues.

``plan_edges`` is pure (text + ``StructureIndex`` only) and shared by the runtime and the
eval harness (``evals/contract_graph/pipeline_predictor.py``). ``build_contract_graph`` adds
two-sided citations, the PASS gate, issues for unresolved targets, implicit annex
substitutions, dedupe and the ``MAX_EDGES`` cap. Neither mutates its inputs; ``run_idp``
calls it only behind ``AI2_CONTRACT_GRAPH_ENABLED`` (D2) and turns any exception into a
``CONTRACT_GRAPH_FAILED`` issue (D11).
"""

from __future__ import annotations

import hashlib
import os
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Any

from app.contracts.contract_graph import (
    NEW_TEXT_MAX,
    ContractEdge,
    ContractGraphResult,
    EdgeMethod,
    EdgeOp,
    edge_id_for,
)
from app.contracts.models import (
    Citation,
    EvidenceIssue,
    Fact,
    RelationSupport,
    ReviewState,
    StructuralNode,
)
from app.pipeline.citations import CitationResolver
from app.pipeline.contract_graph.address import Address, inherit, parse_parent_context
from app.pipeline.contract_graph.implicit import implicit_matches
from app.pipeline.contract_graph.operations import (
    Operation,
    Unit,
    head_of,
    parse_operation,
    rejection_without_address,
    split_operation_units,
    unit_levels,
)
from app.pipeline.contract_graph.resolver import (
    Resolution,
    Status,
    StructureIndex,
    default_target_parts,
    disambiguate_by_order,
)
from app.pipeline.contract_graph.review_policy import (
    auto_pass_enabled,
    load_calibration,
    review_state_for,
)
from app.pipeline.outline import citation_for_node
from app.pipeline.relation_markers import has_amend_marker
from app.tools.store import DossierRecord

ENABLED_ENV = "AI2_CONTRACT_GRAPH_ENABLED"
MAX_EDGES = 500
SPAN_MAX = 240
_TRUTHY = {"1", "true", "yes", "on"}
_SKIPPED_TYPES = frozenset({"FIELD", "TABLE"})
_CONTEXT_OPS = (EdgeOp.REJECTION, EdgeOp.SCOPE_LIMIT)
_LEVEL_ORDER = ("diem", "khoan", "dieu")


def contract_graph_enabled() -> bool:
    return os.getenv(ENABLED_ENV, "false").strip().casefold() in _TRUTHY


@dataclass(frozen=True)
class PlannedEdge:
    """One (unit, target address) of an operation, resolved or not; no citation, no review."""

    op: EdgeOp
    source_node_id: str
    source_address: str | None
    source_span: str  # operation sentence, exact substring of the source node text
    resolution: Resolution
    anchor_node_id: str | None
    standard: bool
    new_text: str | None
    scope_text: str | None

    @property
    def status(self) -> Status:
        return self.resolution.status

    @property
    def target_node_id(self) -> str | None:
        return self.resolution.node_id if self.status == Status.UNIQUE else None

    @property
    def target_address(self) -> str | None:
        return self.resolution.canonical

    @property
    def method(self) -> EdgeMethod | None:
        method = self.resolution.method
        return EdgeMethod(method.value) if method is not None else None


@dataclass(frozen=True)
class _Parsed:
    node: StructuralNode
    units: list[Unit]
    ops: list[Operation | None]

    def last_open_op(self) -> int | None:
        """Index of a trailing operation unit with no new wording (it announces sub-items)."""

        if self.ops and self.ops[-1] is not None and self.ops[-1].new_text is None:
            return len(self.ops) - 1
        return None


def plan_edges(
    source_nodes: Iterable[StructuralNode],
    index: StructureIndex,
    *,
    stats: Counter[str] | None = None,
) -> list[PlannedEdge]:
    """Every operation of ``source_nodes`` with its target resolved in ``index``.

    A unit (or node) whose sub-items carry operations is context only (``parse_parent_context``)
    and plans nothing itself. REJECTION/SCOPE_LIMIT are planned only from an annex part or
    under an operation unit (RT-06); otherwise counted as ``scope_rejection_out_of_context``.
    """

    stats = stats if stats is not None else Counter()
    nodes = sorted(
        (n for n in source_nodes if n.type not in _SKIPPED_TYPES),
        key=lambda n: (_position(index, n.node_id), n.node_id),
    )
    parsed = {}
    for node in nodes:
        units = split_operation_units(node.text or "")
        parsed[node.node_id] = _Parsed(node, units, [parse_operation(u.text) for u in units])
    node_containers = _node_containers(parsed)
    planned: list[PlannedEdge] = []
    groups: dict[tuple[str, int], list[int]] = {}
    for node in nodes:
        item = parsed[node.node_id]
        parent_item = parsed.get(node.parent_id or "")
        node_context_op = parent_item.last_open_op() if parent_item else None
        child_units = {
            u.parent for u, op in zip(item.units, item.ops) if op and u.parent is not None
        }
        for i, (unit, op) in enumerate(zip(item.units, item.ops)):
            if op is None:
                _count_rejected(unit, stats)
                continue
            if i in child_units or (node.node_id in node_containers and i == item.last_open_op()):
                stats["container_units"] += 1
                continue
            ancestors = _unit_ancestors(item, i)
            if op.op in _CONTEXT_OPS and not (
                (index.part_of(node.node_id) or "").startswith("annex:")
                or any(item.ops[a] is not None for a in ancestors)
                or node_context_op is not None
            ):
                stats["scope_rejection_out_of_context"] += 1
                continue
            if unit.parent is not None:
                context = parse_parent_context(head_of(item.units[unit.parent].text))
                group_key = (node.node_id, unit.parent)
            elif node_context_op is not None:
                context = parse_parent_context(parent_item.ops[node_context_op].span)
                group_key = (node.parent_id or "", -1)
            else:
                context, group_key = None, None
            source_address = _source_address(index, node.node_id, item.units, i)
            for addr in op.addresses:
                target = inherit(addr, context)
                planned.append(_plan(index, node.node_id, source_address, op, target))
                if group_key is not None:
                    groups.setdefault(group_key, []).append(len(planned) - 1)
    for members in groups.values():
        ordered = disambiguate_by_order([planned[m].resolution for m in members], index)
        for m, res in zip(members, ordered):
            if res != planned[m].resolution:
                planned[m] = _replace_resolution(planned[m], res)
    return _drop_nested_duplicates(planned, {n.node_id: n.parent_id for n in nodes}, stats)


def build_contract_graph(
    record: DossierRecord,
    facts: Sequence[Fact],
    *,
    calibration: dict[str, Any] | None = None,
    auto_pass: bool | None = None,
) -> ContractGraphResult:
    digest = record.pins.source_snapshot_digest
    nodes = list(record.evidence_nodes())
    roles = {source.file_id: source.role for source in record.source_files}
    index = StructureIndex.build(nodes, roles)
    stats: Counter[str] = Counter()
    planned = plan_edges(nodes, index, stats=stats)
    calibration = calibration if calibration is not None else load_calibration()
    enabled = auto_pass if auto_pass is not None else auto_pass_enabled()
    verifier = CitationResolver(record.pages, record.tables)
    edges: list[ContractEdge] = []
    issues: list[EvidenceIssue] = []

    def citation(node_id: str, span: str | None) -> Citation | None:
        raw = citation_for_node(nodes, record.pages, node_id, text_span=span)
        if raw is None:
            return None
        found = Citation(**raw)
        found.validation_status = verifier.verify(found).status
        return found

    for plan in planned:
        if plan.status != Status.UNIQUE or plan.target_node_id is None:
            issues.append(
                _planned_issue(
                    digest, plan, citation(plan.source_node_id, plan.source_span[:SPAN_MAX])
                )
            )
            stats[_issue_stat(plan)] += 1
            continue
        if plan.target_node_id == plan.source_node_id:
            stats["self_edges"] += 1
            continue
        source = citation(plan.source_node_id, plan.source_span[:SPAN_MAX])
        target = citation(plan.target_node_id, None)
        if source is None or target is None:
            stats["citation_missing"] += 1
            continue
        edges.append(
            _edge(
                digest,
                plan.op,
                plan.source_node_id,
                plan.target_node_id,
                plan.target_address or "",
                plan.source_span,
                source,
                target,
                method=plan.method or EdgeMethod.EXACT,
                support=RelationSupport.EXPLICIT_TEXT,
                standard=plan.standard,
                implicit=False,
                anchor=plan.anchor_node_id,
                new_text=plan.new_text,
                scope_text=plan.scope_text,
            )
        )
    explicit_parts = {index.part_of(p.source_node_id) for p in planned} - {None}
    matches, implicit_issues = implicit_matches(index, nodes, facts, explicit_parts, stats)
    for match in matches:
        source = _verified(match.annex_fact.citation, verifier)
        target = _verified(match.body_fact.citation, verifier)
        body_node = match.body_fact.citation.node_id
        edges.append(
            _edge(
                digest,
                EdgeOp.SUBSTITUTION,
                match.annex_fact.citation.node_id,
                body_node,
                index.canonical_of(body_node) or f"item_key {match.item_key}",
                f"{match.item_key}|{source.text_span}",
                source,
                target,
                method=EdgeMethod.ITEM_KEY,
                support=RelationSupport.HEURISTIC,
                standard=False,
                implicit=True,
                anchor=None,
                new_text=match.annex_fact.raw_value[:NEW_TEXT_MAX],
                scope_text=None,
            )
        )
        stats["implicit_edges"] += 1
    for found in implicit_issues:
        issues.append(
            _issue(
                digest,
                found.kind,
                f"{found.annex_fact.citation.node_id}|item_key {found.item_key}",
                f"item_key {found.item_key}",
                _verified(found.annex_fact.citation, verifier),
            )
        )
        stats[
            "unresolved_targets" if found.kind == "TARGET_NOT_FOUND" else "ambiguous_targets"
        ] += 1
    for edge in edges:
        edge.review_state = review_state_for(edge, calibration, enabled)
        if "VALID" != edge.source_citation.validation_status or (
            "VALID" != edge.target_citation.validation_status
        ):
            stats["citation_invalid"] += 1
    edges = _dedupe(edges, lambda e: e.edge_id, stats, "duplicate_edges")
    issues = _dedupe(issues, lambda i: i.issue_id, stats, "duplicate_issues")
    if len(edges) > MAX_EDGES:
        stats["truncated"] = len(edges) - MAX_EDGES
        edges = edges[:MAX_EDGES]
        issues.append(
            EvidenceIssue(
                issue_id=_issue_id(digest, "CONTRACT_GRAPH_TRUNCATED", str(MAX_EDGES)),
                missing="CONTRACT_GRAPH_TRUNCATED",
                reason=f"Đồ thị sửa đổi vượt {MAX_EDGES} cạnh; phần còn lại không được phát hiện.",
                review_state=ReviewState.NEEDS_REVIEW,
            )
        )
    return ContractGraphResult(edges=edges, issues=issues, stats=_stats(edges, stats))


# -- planning helpers ------------------------------------------------------------------------


def _plan(
    index: StructureIndex, node_id: str, source_address: str | None, op: Operation, target: Address
) -> PlannedEdge:
    parts = default_target_parts(index, node_id, target)
    res = index.resolve(
        target, parts=parts, source_node_id=node_id, require_existing=op.op != EdgeOp.INSERTION
    )
    anchor = None
    if target.insert_after is not None and res.status == Status.UNIQUE:
        found = index.resolve(target.insert_after, parts=parts, source_node_id=node_id)
        anchor = found.node_id if found.status == Status.UNIQUE else None
    return PlannedEdge(
        op=op.op,
        source_node_id=node_id,
        source_address=source_address,
        source_span=op.span,
        resolution=res,
        anchor_node_id=anchor,
        standard=op.standard,
        new_text=op.new_text,
        scope_text=op.scope_text,
    )


def _replace_resolution(plan: PlannedEdge, res: Resolution) -> PlannedEdge:
    return replace(plan, resolution=res)


def _node_containers(parsed: dict[str, _Parsed]) -> set[str]:
    """Nodes whose trailing open operation announces operations of their child nodes."""

    out = set()
    for item in parsed.values():
        parent = parsed.get(item.node.parent_id or "")
        if parent is None or parent.last_open_op() is None:
            continue
        if item.ops and item.ops[0] is not None:
            out.add(parent.node.node_id)
    return out


def _unit_ancestors(item: _Parsed, index: int) -> list[int]:
    out, walk, seen = [], item.units[index].parent, set()
    while walk is not None and walk not in seen:
        out.append(walk)
        seen.add(walk)
        walk = item.units[walk].parent
    return out


def _source_address(index: StructureIndex, node_id: str, units: list[Unit], i: int) -> str | None:
    node_levels = index.levels_of(node_id) or {}
    finest = min((_LEVEL_ORDER.index(k) for k in node_levels if k in _LEVEL_ORDER), default=3)
    own = unit_levels(units, i)
    prefix = " ".join(
        f"{level} {own[level]}"
        for level in _LEVEL_ORDER
        if level in own and _LEVEL_ORDER.index(level) < finest
    )
    node_canonical = index.canonical_of(node_id)
    return " ".join(part for part in (prefix, node_canonical) if part) or None


def _count_rejected(unit: Unit, stats: Counter[str]) -> None:
    if rejection_without_address(unit.text):
        stats["rejection_without_address"] += 1
    elif has_amend_marker(head_of(unit.text)):
        stats["excluded"] += 1


def _drop_nested_duplicates(
    planned: list[PlannedEdge], parents: dict[str, str | None], stats: Counter[str]
) -> list[PlannedEdge]:
    """The same operation read from a node and from an ancestor repeating its text: keep the
    deepest source node (same wording in unrelated nodes stays two operations)."""

    def depth(node_id: str) -> int:
        seen, walk, d = set(), parents.get(node_id), 0
        while walk is not None and walk not in seen:
            seen.add(walk)
            walk, d = parents.get(walk), d + 1
        return d

    kept: list[int] = []
    by_key: dict[tuple, list[int]] = {}
    for i, plan in enumerate(planned):
        key = (
            plan.op,
            " ".join(plan.source_span.split()),
            plan.target_address,
            plan.target_node_id,
        )
        same = by_key.setdefault(key, [])
        dup = next(
            (j for j in same if _related(plan.source_node_id, planned[j].source_node_id, parents)),
            None,
        )
        if dup is None:
            same.append(i)
            kept.append(i)
            continue
        stats["nested_duplicates"] += 1
        if depth(plan.source_node_id) > depth(planned[dup].source_node_id):
            kept[kept.index(dup)] = i
            same[same.index(dup)] = i
    return [planned[i] for i in kept]


def _related(a: str, b: str, parents: dict[str, str | None]) -> bool:
    def chain(node_id: str) -> set[str]:
        seen, walk = set(), node_id
        while walk is not None and walk not in seen:
            seen.add(walk)
            walk = parents.get(walk)
        return seen

    return a in chain(b) or b in chain(a)


def _position(index: StructureIndex, node_id: str) -> int:
    try:
        return index.position(node_id)
    except KeyError:
        return 1 << 30


# -- edges, issues, stats --------------------------------------------------------------------


def _edge(
    digest: str,
    op: EdgeOp,
    source_node: str,
    target_node: str,
    target_address: str,
    span: str,
    source: Citation,
    target: Citation,
    *,
    method: EdgeMethod,
    support: RelationSupport,
    standard: bool,
    implicit: bool,
    anchor: str | None,
    new_text: str | None,
    scope_text: str | None,
) -> ContractEdge:
    return ContractEdge(
        edge_id=edge_id_for(digest, op, source_node, target_node, target_address, span),
        op=op,
        source_node_id=source_node,
        target_node_id=target_node,
        target_address=target_address,
        anchor_node_id=anchor,
        method=method,
        support=support,
        standard=standard,
        implicit=implicit,
        new_text=new_text,
        scope_text=scope_text,
        source_citation=source,
        target_citation=target,
        source_snapshot_digest=digest,
    )


def _verified(citation: Citation, verifier: CitationResolver) -> Citation:
    copy = citation.model_copy(deep=True)
    copy.validation_status = verifier.verify(copy).status
    return copy


def _issue_stat(plan: PlannedEdge) -> str:
    if plan.status == Status.NOT_FOUND:
        return "unresolved_targets"
    if plan.status == Status.AMBIGUOUS:
        return "ambiguous_targets"
    return "new_unit_insertions"


def _planned_issue(digest: str, plan: PlannedEdge, citation: Citation | None) -> EvidenceIssue:
    kind = {
        Status.NOT_FOUND: "TARGET_NOT_FOUND",
        Status.AMBIGUOUS: "TARGET_AMBIGUOUS",
    }.get(plan.status, "NEW_UNIT_INSERTION")
    key = f"{plan.source_node_id}|{plan.op.value}|{plan.target_address}|{plan.source_span}"
    return _issue(digest, kind, key, plan.target_address or "?", citation)


_REASONS = {
    "TARGET_NOT_FOUND": "Không tìm thấy đơn vị đích {key} của thao tác sửa đổi; không suy đoán đích.",
    "TARGET_AMBIGUOUS": "Đích {key} của thao tác sửa đổi khớp nhiều đơn vị; cần người duyệt chọn.",
    "NEW_UNIT_INSERTION": (
        "Thao tác bổ sung đơn vị mới {key}: văn bản gốc không có node đích; cần người duyệt."
    ),
}
_STATES = {
    "TARGET_NOT_FOUND": ReviewState.INSUFFICIENT_EVIDENCE,
    "TARGET_AMBIGUOUS": ReviewState.NEEDS_REVIEW,
    "NEW_UNIT_INSERTION": ReviewState.NEEDS_REVIEW,
}


def _issue(
    digest: str, kind: str, key: str, target: str, citation: Citation | None
) -> EvidenceIssue:
    return EvidenceIssue(
        issue_id=_issue_id(digest, kind, key),
        missing=kind,
        reason=_REASONS[kind].format(key=target),
        citation=citation,
        review_state=_STATES[kind],
    )


def _issue_id(digest: str, kind: str, key: str) -> str:
    return (
        "contract-graph:"
        + hashlib.sha256(f"{digest}|{kind}|{key}".encode("utf-8")).hexdigest()[:24]
    )


def _dedupe(items: list, key, stats: Counter[str], stat: str) -> list:
    seen: set[str] = set()
    out = []
    for item in items:
        k = key(item)
        if k in seen:
            stats[stat] += 1
            continue
        seen.add(k)
        out.append(item)
    return out


def _stats(edges: list[ContractEdge], counts: Counter[str]) -> dict[str, int | dict[str, int]]:
    out: dict[str, int | dict[str, int]] = {
        "edges_total": len(edges),
        "edges_by_op": {op.value: sum(e.op == op for e in edges) for op in EdgeOp},
        "edges_by_method": {m.value: sum(e.method == m for e in edges) for m in EdgeMethod},
    }
    for key in (
        "unresolved_targets",
        "ambiguous_targets",
        "new_unit_insertions",
        "implicit_edges",
        "implicit_same_value",
        "excluded",
        "rejection_without_address",
        "scope_rejection_out_of_context",
        "container_units",
        "self_edges",
        "citation_missing",
        "citation_invalid",
        "nested_duplicates",
        "duplicate_edges",
        "duplicate_issues",
        "truncated",
    ):
        out[key] = int(counts.get(key, 0))
    return out
