"""Deterministic reconstruction of a contract structure from AI1 evidence.

AI1 owns OCR/layout evidence.  AI2 may derive a conservative hierarchy from
that evidence, but it must never invent a heading or silently discard a file
root.  This module is shared by PDF-demo ingestion and official AI1 snapshots.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

from app.contracts.models import HandoffIssue, PageSnapshot, ReviewState, StructuralNode
from app.tools.store import DossierRecord

_ANNEX_HEADING = re.compile(
    r"^\s*phụ\s+lục\s+\d+(?:\s*(?:[-–—:]\s*.*)?)?\s*$", re.I
)
_PART_HEADING = re.compile(r"^\s*(?:phần|chương|mục)\s+\d+(?:\s*[.:–—-].*)?\s*$", re.I)
_ARTICLE_HEADING = re.compile(r"^\s*(?:điều|article)\s+[\d.]+(?:\s*[.:–—-].*)?\s*$", re.I)
_SUBCLAUSE_HEADING = re.compile(r"^\s*(?:khoản|điểm)\s+\(?[a-z0-9]+\)?(?:\s*[.:–—-].*)?\s*$", re.I)


def contract_unit_line_scopes(pages: list[PageSnapshot]) -> dict[tuple[str, str], str]:
    """Split only explicit contract openings supported by a number and both parties."""
    grouped: dict[str | None, list[PageSnapshot]] = defaultdict(list)
    for page in pages:
        grouped[page.source_file_id].append(page)
    scopes: dict[tuple[str, str], str] = {}
    for file_id, file_pages in grouped.items():
        lines = [
            (page, line_id, text)
            for page in sorted(file_pages, key=lambda p: p.page_number)
            for line_id, text in page.line_texts.items()
        ]
        folded = [_fold_contract_text(text) for _, _, text in lines]
        titles = [
            index for index, (_, _, text) in enumerate(lines)
            if _is_contract_title(text)
        ]
        starts: dict[int, str] = {}
        for title_index, start in enumerate(titles):
            stop = min(start + 24, titles[title_index + 1] if title_index + 1 < len(titles) else len(lines))
            opening = folded[start:stop]
            # Running headers and prose references cannot start a contract unit.
            has_number = any(re.search(r"\bso\s*[:：]?\s*\d", text) for text in opening)
            parties = {
                match.group(1) for text in opening
                if (match := re.match(r"ben\s+([ab])(?:\s*\([^)]*\))?\s*[:：]", text))
            }
            if has_number and parties == {"a", "b"}:
                page, line_id, _ = lines[start]
                starts[start] = f"contract-unit:{file_id}:{page.page_revision_id}:{line_id}"
        if len(starts) < 2:
            continue
        current: str | None = None
        for index, (page, line_id, _) in enumerate(lines):
            current = starts.get(index, current)
            if current is not None:
                scopes[(page.page_revision_id, line_id)] = current
    return scopes


def _fold_contract_text(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.casefold())
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn").replace("đ", "d").strip()


def _is_contract_title(text: str) -> bool:
    return bool(re.match(r"^hop dong(?:\s|$)", _fold_contract_text(text))) and text.strip().isupper()


def assign_contract_units(record: DossierRecord) -> None:
    """Annotate the derived hierarchy; raw OCR nodes and snapshot stay immutable."""
    scopes = contract_unit_line_scopes(record.pages)
    if not scopes:
        titles_by_file: dict[str | None, int] = defaultdict(int)
        for page in record.pages:
            titles_by_file[page.source_file_id] += sum(_is_contract_title(text) for text in page.line_texts.values())
        if any(count > 1 for count in titles_by_file.values()) and not any(
            issue.code == "CONTRACT_UNIT_BOUNDARY_AMBIGUOUS" for issue in record.handoff_issues
        ):
            record.handoff_issues.append(HandoffIssue(
                code="CONTRACT_UNIT_BOUNDARY_AMBIGUOUS",
                message="Tiêu đề hợp đồng lặp nhưng thiếu số hoặc khai báo hai bên; giữ nguyên ranh giới để người duyệt kiểm tra.",
                review_state=ReviewState.NEEDS_REVIEW,
            ))
        return
    if not any(issue.code == "CONTRACT_UNITS_DERIVED" for issue in record.handoff_issues):
        record.handoff_issues.append(HandoffIssue(
            code="CONTRACT_UNITS_DERIVED",
            message="AI2 dẫn xuất ranh giới nhiều hợp đồng từ tiêu đề, số và khai báo các bên; cần xác nhận.",
            review_state=ReviewState.NEEDS_REVIEW,
        ))
    nodes = [node.model_copy(deep=True) for node in record.evidence_nodes()]
    node_units = {
        node.node_id: scopes.get((node.page_revision_id or "", node.source_line_ids[0]))
        for node in nodes if node.source_line_ids
    }
    for page in record.pages:
        for line_id, text in page.line_texts.items():
            unit_id = scopes.get((page.page_revision_id, line_id))
            if unit_id != f"contract-unit:{page.source_file_id}:{page.page_revision_id}:{line_id}":
                continue
            nodes.append(StructuralNode(
                node_id=unit_id, type="SECTION", raw_label=text, text=text,
                parent_id=f"ai2-root:{page.source_file_id}", scope_id=unit_id,
                structure_level="CONTRACT_UNIT", page_revision_id=page.page_revision_id,
                page_range=[page.page_number], page_in_file=page.page_in_file,
                bbox=page.line_bboxes.get(line_id, []), source_line_ids=[line_id],
                source_file_id=page.source_file_id, provenance="AI2_REPAIRED",
                heading_confidence=0.95, parent_confidence=0.95,
            ))
    for node in nodes:
        unit_id = node_units.get(node.node_id)
        if not unit_id:
            continue
        if node.structure_level == "ANNEX":
            node.parent_id = unit_id
            continue
        # Preserve annex scope so annex evidence is never relabelled as body.
        if node.scope_id and not node.scope_id.startswith("ai2-root:"):
            continue
        node.scope_id = unit_id
        if node_units.get(node.parent_id) != unit_id:
            node.parent_id = unit_id
        node.provenance = "AI2_REPAIRED"
    record.active_nodes = nodes
    for fact in [*record.facts, *(record.input_facts or [])]:
        citation = fact.citation
        if not citation.line_ids or not _is_document_level_field(fact.item_key or fact.role):
            continue
        unit_id = scopes.get((citation.page_revision_id, citation.line_ids[0]))
        if unit_id:
            fact.scope = unit_id


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
