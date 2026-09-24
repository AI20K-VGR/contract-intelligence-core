"""Deterministic reconstruction of a contract structure from AI1 evidence.

AI1 owns OCR/layout evidence.  AI2 may derive a conservative hierarchy from
that evidence, but it must never invent a heading or silently discard a file
root.  This module is shared by PDF-demo ingestion and official AI1 snapshots.
"""

from __future__ import annotations

import re
from collections import defaultdict

from app.contracts.models import HandoffIssue, ReviewState, StructuralNode
from app.tools.store import DossierRecord


_ANNEX_HEADING = re.compile(
    r"^\s*phụ\s+lục\s+\d+(?:\s*(?:[-–—:]\s*.*)?)?\s*$", re.I
)
_PART_HEADING = re.compile(r"^\s*(?:phần|chương|mục)\s+\d+(?:\s*[.:–—-].*)?\s*$", re.I)
_ARTICLE_HEADING = re.compile(r"^\s*(?:điều|article)\s+[\d.]+(?:\s*[.:–—-].*)?\s*$", re.I)
_SUBCLAUSE_HEADING = re.compile(r"^\s*(?:khoản|điểm)\s+\(?[a-z0-9]+\)?(?:\s*[.:–—-].*)?\s*$", re.I)


def is_structural_heading(label: str) -> bool:
    """Return true only for a line that can safely become a section heading."""

    value = (label or "").strip()
    return bool(
        _ANNEX_HEADING.match(value)
        or _PART_HEADING.match(value)
        or _ARTICLE_HEADING.match(value)
        or _SUBCLAUSE_HEADING.match(value)
    )


def heading_level(label: str, node_type: str = "") -> str:
    value = (label or "").strip().casefold()
    if re.match(r"^(phụ\s+lục|phu\s+luc)\s+\d+", value):
        return "ANNEX"
    if re.match(r"^(phần|phần|chương|mục)\s+\d+", value):
        return "SECTION"
    if re.match(r"^(điều|article)\s+[\d.]", value):
        return "ARTICLE"
    if re.match(r"^(khoản|điểm)\s+", value):
        return "SUBCLAUSE"
    if node_type == "TABLE":
        return "TABLE"
    if node_type == "FIELD":
        return "FIELD"
    return "BLOCK"


def reconstruct_structure(record: DossierRecord) -> tuple[list[StructuralNode], list[HandoffIssue]]:
    """Build an active, conservative hierarchy while keeping raw AI1 intact."""

    grouped: dict[str | None, list[StructuralNode]] = defaultdict(list)
    for node in record.nodes:
        grouped[node.source_file_id].append(node)

    output: list[StructuralNode] = []
    issues: list[HandoffIssue] = []
    file_roles = {item.file_id: item.role for item in record.source_files}

    for file_id, raw_nodes in grouped.items():
        raw_nodes = sorted(raw_nodes, key=_node_order)
        roots = [
            node
            for node in raw_nodes
            if node.type == "SECTION" and not node.parent_id
        ]
        synthetic_root: StructuralNode | None = None
        if not roots:
            role = file_roles.get(file_id, "body")
            label = "Phụ lục" if role == "annex" else "Hợp đồng"
            root_id = f"ai2-root:{file_id or 'document'}"
            first_page = min((p for node in raw_nodes for p in node.page_range), default=1)
            synthetic_root = StructuralNode(
                node_id=root_id,
                type="SECTION",
                raw_label=label,
                text=label,
                order=-1,
                page_range=[first_page],
                source_file_id=file_id,
                structure_level="DOCUMENT",
                scope_id=root_id,
                heading_confidence=1.0,
                parent_confidence=1.0,
                provenance="AI2_REPAIRED",
                is_synthetic=True,
                status="PARTIAL",
            )
            roots = [synthetic_root]
            issues.append(
                HandoffIssue(
                    code="STRUCTURE_ROOT_DERIVED",
                    message=f"{root_id}: AI1 did not provide a document root; AI2 created a non-evidentiary root",
                    review_state=ReviewState.NEEDS_REVIEW,
                )
            )

        # Existing documents with multiple top-level roots (for example a
        # body and an annex represented in one fixture) already have a stable
        # hierarchy.  Only repair nodes whose parent is missing/invalid.
        root_ids = {node.node_id for node in roots}
        raw_by_id = {node.node_id: node for node in raw_nodes}
        valid_section_ids = {
            node.node_id
            for node in raw_nodes
            if node.type == "SECTION"
            and (node.node_id in root_ids or is_structural_heading(node.raw_label))
        }
        false_sections = {
            node.node_id
            for node in raw_nodes
            if node.type == "SECTION"
            and node.node_id not in root_ids
            and node.node_id not in valid_section_ids
        }

        # If there is one root, reconstruct in reading order.  This is the
        # common upload/snapshot case and prevents a false annex mention from
        # becoming the parent of every later article.
        single_root = len(roots) == 1
        current_section: str | None = roots[0].node_id if single_root else None
        current_clause: str | None = None
        emitted_ids: set[str] = set()
        replacements: dict[str, StructuralNode] = {}

        if synthetic_root is not None:
            replacements[synthetic_root.node_id] = synthetic_root

        for node in raw_nodes:
            if node.node_id in emitted_ids:
                continue
            if node.node_id in root_ids:
                normalized = _normalize_node(
                    node,
                    parent_id=None,
                    scope_id=node.node_id,
                    level="DOCUMENT",
                    changed=False,
                )
                replacements[node.node_id] = normalized
                emitted_ids.add(node.node_id)
                if single_root:
                    current_section = node.node_id
                continue

            if node.node_id in false_sections:
                parent_id = current_clause or current_section or _fallback_root(roots)
                normalized = _normalize_node(
                    node,
                    parent_id=parent_id,
                    scope_id=_scope_for(parent_id, replacements, roots),
                    level="BLOCK",
                    changed=True,
                    type_override="UNNUMBERED_BLOCK",
                    status="PARTIAL",
                )
                replacements[node.node_id] = normalized
                emitted_ids.add(node.node_id)
                issues.append(
                    HandoffIssue(
                        code="AMBIGUOUS_HEADING_AS_BLOCK",
                        message=f"{node.node_id}: '{node.raw_label}' kept as content, not promoted to a section",
                        review_state=ReviewState.NEEDS_REVIEW,
                    )
                )
                continue

            if node.type == "SECTION" and is_structural_heading(node.raw_label):
                parent_id = _fallback_root(roots) if single_root else _valid_parent(node, valid_section_ids, root_ids)
                current_section = node.node_id
                current_clause = None
                replacements[node.node_id] = _normalize_node(
                    node,
                    parent_id=parent_id,
                    scope_id=node.node_id,
                    level=heading_level(node.raw_label, node.type),
                    changed=node.parent_id != parent_id,
                )
                emitted_ids.add(node.node_id)
                continue

            if node.type == "CLAUSE":
                parent_id = current_section or _fallback_root(roots)
                level = heading_level(node.raw_label, node.type)
                replacements[node.node_id] = _normalize_node(
                    node,
                    parent_id=parent_id,
                    scope_id=_scope_for(parent_id, replacements, roots),
                    level=level if level != "BLOCK" else "ARTICLE",
                    changed=node.parent_id != parent_id,
                )
                current_clause = node.node_id
                emitted_ids.add(node.node_id)
                continue

            parent_id = _choose_content_parent(
                node,
                current_clause=current_clause,
                current_section=current_section,
                roots=roots,
                valid_ids=set(raw_by_id),
            )
            replacements[node.node_id] = _normalize_node(
                node,
                parent_id=parent_id,
                scope_id=_scope_for(parent_id, replacements, roots),
                level=heading_level(node.raw_label, node.type),
                changed=node.parent_id != parent_id,
            )
            emitted_ids.add(node.node_id)

        output.extend(replacements.values())

    # Preserve deterministic source order, with derived roots first.
    output.sort(key=_node_order)
    return output, issues


def _node_order(node: StructuralNode) -> tuple[int, int, int, str]:
    return (
        min(node.page_range) if node.page_range else 10**9,
        node.page_in_file or 0,
        node.order,
        node.node_id,
    )


def _fallback_root(roots: list[StructuralNode]) -> str:
    return roots[0].node_id


def _valid_parent(node: StructuralNode, valid_section_ids: set[str], root_ids: set[str]) -> str:
    if node.parent_id in valid_section_ids or node.parent_id in root_ids:
        return str(node.parent_id)
    return next(iter(root_ids))


def _choose_content_parent(
    node: StructuralNode,
    *,
    current_clause: str | None,
    current_section: str | None,
    roots: list[StructuralNode],
    valid_ids: set[str],
) -> str:
    if node.parent_id in valid_ids and node.parent_id not in {root.node_id for root in roots}:
        # Keep an already-valid explicit parent for catalog/snapshot data.
        return str(node.parent_id)
    # Party declarations and tax identifiers describe the document parties,
    # not the first article that happens to precede them in AI1's ordering.
    # Keeping them at document scope prevents a common OCR/result handoff
    # error where the tree makes "Bên A/B" look like children of Điều 1.
    if node.type == "FIELD" and _is_document_level_field(node.structured_key):
        return current_section or _fallback_root(roots)
    return current_clause or current_section or _fallback_root(roots)


def _is_document_level_field(key: str | None) -> bool:
    if not key:
        return False
    normalized = key.casefold().replace("-", "_")
    return normalized in {
        "party_a",
        "party_b",
        "party_c",
        "party_y",
        "mst_party_a",
        "mst_party_b",
        "mst_party_c",
        "mst_party_y",
        "mst_seller",
        "mst_buyer",
    }


def _scope_for(parent_id: str | None, replacements: dict[str, StructuralNode], roots: list[StructuralNode]) -> str:
    if parent_id and parent_id in replacements:
        return replacements[parent_id].scope_id or parent_id
    return parent_id or roots[0].node_id


def _normalize_node(
    node: StructuralNode,
    *,
    parent_id: str | None,
    scope_id: str | None,
    level: str,
    changed: bool,
    type_override: str | None = None,
    status: str | None = None,
) -> StructuralNode:
    return node.model_copy(
        update={
            "parent_id": parent_id,
            "structure_level": level,
            "scope_id": scope_id,
            "heading_confidence": 0.95 if level in {"DOCUMENT", "ANNEX", "SECTION", "ARTICLE", "SUBCLAUSE"} else node.heading_confidence,
            "parent_confidence": 0.95 if parent_id else 1.0,
            "provenance": "AI2_REPAIRED" if changed or node.provenance == "AI2_REPAIRED" else node.provenance,
            "status": status or ("PARTIAL" if changed and node.status == "CONFIRMED" else node.status),
            "type": type_override or node.type,
            "repaired_from_node_id": node.node_id if changed else node.repaired_from_node_id,
            # A file/document root is an index anchor.  Keep it even when
            # AI1 used a filename as its label and that label is absent from
            # OCR text; child evidence must never be orphaned.
            "is_synthetic": node.is_synthetic or (parent_id is None and node.type == "SECTION"),
        }
    )
