"""Build the clause tree from a flat, in-order stream of logical segments.

Placement is driven by numbering, not semantic meaning (section 9): each
segment is either a fresh marker (opens a new node) or unmarked continuation
text (appended to whichever node is currently deepest open). A small stack
keyed by marker "tier" (numeric family / letter family / roman family)
decides each new marker's parent and level without needing to understand
what the clause is about.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import clause_parser
from .clause_parser import SECTION, TIER
from .models import ClauseMarker, ResolutionMethod, SourceBlockRef
from .schemas.document import Clause, ReconstructionInfo


@dataclass
class LogicalSegment:
    """One already-merged logical block, ready to be placed in the tree."""

    text: str
    page_start: int
    page_end: int
    source_blocks: list[SourceBlockRef]
    was_merged: bool = False
    method: ResolutionMethod = ResolutionMethod.RULE
    confidence: float = 1.0


def _derive_title(text: str, marker: ClauseMarker) -> str | None:
    if marker.marker_type != SECTION:
        return None
    remainder = text[len(marker.raw) :].lstrip()
    remainder = remainder.lstrip(".:-)–— ").strip()
    return remainder or None


@dataclass
class _MutableNode:
    clause_id: str
    parent_id: str | None
    level: int
    marker: str | None
    title: str | None
    text_parts: list[str] = field(default_factory=list)
    page_start: int = 0
    page_end: int = 0
    source_blocks: list[SourceBlockRef] = field(default_factory=list)
    was_merged: bool = False
    method: ResolutionMethod = ResolutionMethod.RULE
    confidence: float = 1.0
    children: list["_MutableNode"] = field(default_factory=list)


def _node_id(parent_id: str | None, normalized: str) -> str:
    return f"{parent_id}.{normalized}" if parent_id else normalized


def _to_clause(node: _MutableNode) -> Clause:
    return Clause(
        clause_id=node.clause_id,
        parent_id=node.parent_id,
        level=node.level,
        marker=node.marker,
        title=node.title,
        text=" ".join(part for part in node.text_parts if part).strip(),
        page_start=node.page_start,
        page_end=node.page_end,
        source_blocks=node.source_blocks,
        reconstruction=ReconstructionInfo(
            was_merged=node.was_merged, method=node.method, confidence=node.confidence
        ),
        children=[_to_clause(child) for child in node.children],
    )


class HierarchyBuilder:
    """Incrementally builds the clause tree, one logical segment at a time."""

    def __init__(self) -> None:
        self._roots: list[_MutableNode] = []
        self._stack: list[tuple[_MutableNode, int]] = []  # (node, tier)

    def add(self, segment: LogicalSegment) -> None:
        marker = clause_parser.parse_marker(segment.text)
        if marker is not None:
            self._open_node(marker, segment)
        else:
            self._append_to_current(segment)

    def _open_node(self, marker: ClauseMarker, segment: LogicalSegment) -> None:
        tier = TIER[marker.marker_type]
        if tier == 0:
            level = marker.level_hint or 1
            while self._stack and (self._stack[-1][1] > 0 or self._stack[-1][0].level >= level):
                self._stack.pop()
        else:
            while self._stack and self._stack[-1][1] >= tier:
                self._stack.pop()
            level = (self._stack[-1][0].level + 1) if self._stack else tier + 1

        parent = self._stack[-1][0] if self._stack else None
        # Numeric-family markers (section/decimal) already carry their full
        # dotted path in `normalized` (e.g. "5.2.1"), independent of any
        # "Dieu"/"Article" prefix — don't re-prefix it with the parent id.
        # Letter/roman markers only carry their own local token ("a", "i")
        # and must be joined onto the parent's path.
        clause_id = (
            marker.normalized
            if tier == 0
            else _node_id(parent.clause_id if parent else None, marker.normalized)
        )
        node = _MutableNode(
            clause_id=clause_id,
            parent_id=parent.clause_id if parent else None,
            level=level,
            marker=marker.raw,
            title=_derive_title(segment.text, marker),
            page_start=segment.page_start,
            page_end=segment.page_end,
            source_blocks=list(segment.source_blocks),
            was_merged=segment.was_merged,
            method=segment.method,
            confidence=segment.confidence,
        )
        node.text_parts.append(segment.text)
        if parent is not None:
            parent.children.append(node)
        else:
            self._roots.append(node)
        self._stack.append((node, tier))

    def _append_to_current(self, segment: LogicalSegment) -> None:
        if not self._stack:
            # Body text with no enclosing clause marker at all: keep it as
            # its own root-level node rather than discarding it.
            node = _MutableNode(
                clause_id=f"_unnumbered_{len(self._roots) + 1}",
                parent_id=None,
                level=1,
                marker=None,
                title=None,
                page_start=segment.page_start,
                page_end=segment.page_end,
                source_blocks=list(segment.source_blocks),
                was_merged=segment.was_merged,
                method=segment.method,
                confidence=segment.confidence,
            )
            node.text_parts.append(segment.text)
            self._roots.append(node)
            self._stack.append((node, 0))
            return

        node = self._stack[-1][0]
        node.text_parts.append(segment.text)
        node.page_end = max(node.page_end, segment.page_end)
        node.source_blocks.extend(segment.source_blocks)
        node.was_merged = node.was_merged or segment.was_merged
        node.confidence = min(node.confidence, segment.confidence)

    def roots(self) -> list[Clause]:
        return [_to_clause(node) for node in self._roots]

    def flatten(self) -> list[Clause]:
        flat: list[Clause] = []

        def visit(node: _MutableNode) -> None:
            clause = _to_clause(node)
            flat.append(clause.model_copy(update={"children": []}))
            for child in node.children:
                visit(child)

        for root in self._roots:
            visit(root)
        return flat


def build_hierarchy(segments: list[LogicalSegment]) -> tuple[list[Clause], list[Clause]]:
    """Build the clause tree from an ordered list of logical segments.

    Returns `(sections, clauses)`: `sections` are the top-level nodes with
    their full nested subtree, `clauses` is every node in the document
    flattened into one pre-order list (for chunking/RAG convenience).
    """
    builder = HierarchyBuilder()
    for segment in segments:
        builder.add(segment)
    return builder.roots(), builder.flatten()
