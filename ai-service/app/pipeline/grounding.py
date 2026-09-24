from __future__ import annotations

from difflib import SequenceMatcher
import re

from app.contracts.models import Citation, Fact, HandoffIssue, ReviewState, StructuralNode, TenantProfile
from app.pipeline.structure import reconstruct_structure
from app.tools.store import DossierRecord


class GroundingGate:
    def ground_fact(self, fact: Fact, source_text: str, profile: TenantProfile | None = None) -> Fact:
        if _exact_span(fact.raw_value, source_text) or _exact_span(fact.citation.text_span, source_text):
            if fact.review_state == ReviewState.BLOCKED:
                return fact
            fact.review_state = ReviewState.PASS
            return fact
        if _fuzzy_ok(fact.raw_value, source_text):
            fact.review_state = ReviewState.NEEDS_REVIEW
            return fact
        if profile and _alias_in_source(fact, profile, source_text):
            fact.review_state = ReviewState.NEEDS_REVIEW
            return fact
        if fact.normalized_value and fact.normalized_value in source_text:
            fact.review_state = ReviewState.NEEDS_REVIEW
            return fact
        fact.review_state = ReviewState.INSUFFICIENT_EVIDENCE
        return fact

    def restore_citation(self, value: str, source_text: str, node_id: str, page_revision_id: str, bbox: list[float]) -> Citation | None:
        if value not in source_text:
            return None
        return Citation(
            node_id=node_id,
            page_revision_id=page_revision_id,
            bbox=bbox,
            text_span=value,
        )


def repair_active_nodes(record: DossierRecord) -> tuple[list[StructuralNode], list[HandoffIssue]]:
    """Create a grounded view without mutating the AI1 node list.

    Only numbered headings can be deterministically repaired. A field with an
    ungrounded value is excluded rather than invented. If no real heading is
    available, the fabricated structural node is excluded from evidence.
    """

    structured_nodes, structure_issues = reconstruct_structure(record)
    pages = {page.page_number: page.text or "" for page in record.pages}
    replacements: dict[str, StructuralNode] = {}
    issues: list[HandoffIssue] = list(structure_issues)
    seen_ids: set[tuple[str | None, str]] = set()
    for raw_node in record.nodes:
        key = (raw_node.source_file_id, raw_node.node_id)
        if key in seen_ids:
            issues.append(
                HandoffIssue(
                    code="STRUCTURE_DUPLICATE_NODE_ID",
                    message=f"{raw_node.node_id}: duplicate node kept out of active structure",
                    review_state=ReviewState.NEEDS_REVIEW,
                )
            )
        seen_ids.add(key)
    for node in structured_nodes:
        # A derived document/file root is an index anchor, not a claim.  It
        # may not literally occur in OCR text, but dropping it would also
        # orphan every grounded child in that file.
        if node.is_synthetic:
            replacements[node.node_id] = node
            continue
        # Table text is a reconstructed row/cell view and is not expected to
        # occur as one contiguous substring in the immutable OCR page text.
        # The table adapter already supplies the authoritative provenance, so
        # preserve the table node when its snapshot exists instead of hiding
        # embedded annex content from the workspace/query path.
        if node.type == "TABLE" and any(table.node_id == node.node_id for table in record.tables):
            replacements[node.node_id] = node
            continue
        page_text = "\n".join(pages.get(number, "") for number in node.page_range)
        if _grounded_node(node, page_text):
            replacements[node.node_id] = node
            continue

        repaired = _repair_heading(node, page_text)
        if repaired is not None:
            replacements[node.node_id] = repaired
            issues.append(
                HandoffIssue(
                    code="NODE_TEXT_UNGROUNDED",
                    message=f"{node.node_id} repaired from page heading",
                    review_state=ReviewState.NEEDS_REVIEW,
                )
            )
        else:
            issues.append(
                HandoffIssue(
                    code="NODE_TEXT_UNGROUNDED",
                    message=f"{node.node_id} is not present in referenced page text",
                    review_state=ReviewState.NEEDS_REVIEW,
                )
            )

    active: list[StructuralNode] = []
    id_map = {old_id: node.node_id for old_id, node in replacements.items()}
    roots_by_file = {
        node.source_file_id: node.node_id
        for node in structured_nodes
        if node.type == "SECTION" and not node.parent_id
    }
    for original in structured_nodes:
        node = replacements.get(original.node_id)
        if node is None:
            continue
        if node.parent_id:
            parent_id = id_map.get(node.parent_id)
            if parent_id is None:
                parent_id = roots_by_file.get(node.source_file_id)
            if parent_id is None:
                continue
            node = node.model_copy(update={"parent_id": parent_id})
        active.append(node)
    by_id = {node.node_id: node for node in active}

    def depth(node: StructuralNode) -> int:
        current = node
        seen: set[str] = set()
        value = 0
        while current.parent_id and current.parent_id in by_id and current.parent_id not in seen:
            seen.add(current.node_id)
            value += 1
            current = by_id[current.parent_id]
        return value

    active.sort(key=lambda node: (depth(node), node.page_range[0] if node.page_range else 10**9, node.order, node.node_id))
    active = [node.model_copy(update={"order": index}) for index, node in enumerate(active)]
    return active, issues


def _grounded_node(node: StructuralNode, page_text: str) -> bool:
    if not page_text.strip():
        return False
    normalized_page = _normalize_grounding_text(page_text)
    label = _normalize_grounding_text(node.raw_label)
    text = _normalize_grounding_text(node.text)
    value = _normalize_grounding_text(node.structured_value or "")
    return bool((label and label in normalized_page) or (text and text in normalized_page) or (value and value in normalized_page))


def _repair_heading(node: StructuralNode, page_text: str) -> StructuralNode | None:
    if node.type not in {"SECTION", "CLAUSE"} or not page_text.strip():
        return None
    pattern = re.compile(r"(?im)^\s*((?:Điều|ĐIỀU|Article|Phần|PHẦN|Phụ lục|PHỤ LỤC)\s+[^\n.]{1,80}(?:\.[^\n]*)?)\s*$")
    matches = [match.group(1).strip() for match in pattern.finditer(page_text)]
    if len(matches) != 1:
        return None
    heading = matches[0]
    return node.model_copy(
        update={
            "node_id": f"repair:{node.node_id}",
            "raw_label": heading[:120],
            "text": heading[:120],
            "provenance": "AI2_REPAIRED",
            "repaired_from_node_id": node.node_id,
            "status": "PARTIAL",
        }
    )


def _normalize_grounding_text(value: str) -> str:
    return " ".join((value or "").casefold().split())


def _exact_span(needle: str, haystack: str) -> bool:
    return bool(needle) and needle in haystack


def _fuzzy_ok(needle: str, haystack: str, threshold: float = 0.86) -> bool:
    if not needle or not haystack:
        return False
    ratio = SequenceMatcher(None, needle.lower(), haystack.lower()).ratio()
    if ratio >= threshold:
        return True
    for i in range(0, max(0, len(haystack) - len(needle)) + 1, max(1, len(needle) // 2)):
        window = haystack[i : i + max(len(needle), 8)]
        if SequenceMatcher(None, needle.lower(), window.lower()).ratio() >= threshold:
            return True
    return False


def _alias_in_source(fact: Fact, profile: TenantProfile, source_text: str) -> bool:
    low = source_text.lower()
    for canonical, aliases in profile.aliases.items():
        if canonical.lower() in low or any(a.lower() in low for a in aliases):
            if fact.raw_value.lower() in {canonical.lower(), *(a.lower() for a in aliases)}:
                return True
    return False
