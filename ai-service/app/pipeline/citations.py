from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

from app.contracts.models import Citation, PageSnapshot, StructuralNode, TableSnapshot


def normalize_digest(value: str | None) -> str:
    return str(value or "").removeprefix("sha256:").lower()


def quote_digest(value: str) -> str:
    """Hash the exact stored quote; do not fold whitespace or diacritics."""

    return sha256(value.encode("utf-8")).hexdigest()


def canonical_page_text(page: PageSnapshot) -> str:
    if page.text:
        return page.text
    return "\n".join(page.line_texts.values())


@dataclass(frozen=True)
class CitationCheck:
    status: str
    reason: str
    page: PageSnapshot | None = None

    @property
    def valid(self) -> bool:
        return self.status == "VALID"


class CitationResolver:
    """Resolve citations against immutable page revisions and exact spans."""

    def __init__(
        self,
        pages: Iterable[PageSnapshot],
        tables: Iterable[TableSnapshot] = (),
        nodes: Iterable[StructuralNode] = (),
    ) -> None:
        self.pages = list(pages)
        self.tables = {table.table_id: table for table in tables}
        self.nodes = {node.node_id: node for node in nodes}
        self.by_revision = {page.page_revision_id: page for page in self.pages}

    def page_for(self, citation: Citation) -> PageSnapshot | None:
        if not citation.page_revision_id:
            return None
        page = self.by_revision.get(citation.page_revision_id)
        if page is None:
            return None
        if citation.source_file_id and citation.source_file_id != page.source_file_id:
            return None
        if citation.page is not None and citation.page != page.page_number:
            return None
        if citation.page_range and page.page_number not in citation.page_range:
            return None
        return page

    def verify(self, citation: Citation, *, require_provenance: bool = True) -> CitationCheck:
        page = self.page_for(citation)
        if page is None:
            return CitationCheck("INVALID", "page_revision_id/source scope did not resolve")
        node = self.nodes.get(citation.node_id)
        if self.nodes and node is None and citation.node_id != f"page:{page.page_revision_id}":
            return CitationCheck("INVALID", "citation node is outside the active evidence scope", page)
        if node is not None:
            if node.page_revision_id and node.page_revision_id != page.page_revision_id:
                return CitationCheck("INVALID", "node page revision does not match citation", page)
            if node.source_file_id and page.source_file_id != node.source_file_id:
                return CitationCheck("INVALID", "node source file does not match page", page)
            if node.page_range and page.page_number not in node.page_range:
                return CitationCheck("INVALID", "citation page is outside node page range", page)
            if citation.source_file_id and node.source_file_id and citation.source_file_id != node.source_file_id:
                return CitationCheck("INVALID", "citation source file does not match node", page)
        text = canonical_page_text(page)
        if not citation.text_span:
            return CitationCheck("INVALID", "citation text_span is empty", page)
        if citation.bbox and not _valid_bbox(citation.bbox):
            return CitationCheck("INVALID", "citation bbox is invalid", page)
        if require_provenance:
            if not citation.source_hash or not page.source_hash:
                return CitationCheck("UNVERIFIED", "source hash is missing", page)
            if normalize_digest(citation.source_hash) != normalize_digest(page.source_hash):
                return CitationCheck("INVALID", "source hash does not match page revision", page)
            if not citation.quote_sha256:
                return CitationCheck("UNVERIFIED", "quote hash is missing", page)
            if citation.quote_sha256.lower() != quote_digest(citation.text_span):
                return CitationCheck("INVALID", "quote hash does not match exact text span", page)
        if citation.table_id or citation.cell_id:
            table = self.tables.get(citation.table_id or "")
            if table is None:
                return CitationCheck("UNVERIFIED", "source table is unavailable", page)
            cell = next((c for c in table.cells if c.cell_id == citation.cell_id), None)
            if cell is None or table.page_revision_id != page.page_revision_id or table.node_id != citation.node_id:
                return CitationCheck("INVALID", "table cell scope did not resolve", page)
            if cell.text != citation.text_span or cell.bbox != citation.bbox:
                return CitationCheck("INVALID", "citation differs from source cell", page)
            if getattr(cell, "geometry_provenance", "MEASURED") != "MEASURED":
                return CitationCheck("UNVERIFIED", "table cell geometry is claimed or derived", page)
            return CitationCheck("VALID", "exact source cell verified", page)
        if citation.char_start is None or citation.char_end is None:
            return CitationCheck("UNVERIFIED", "exact character offsets are missing", page)
        if citation.char_start < 0 or citation.char_end <= citation.char_start or citation.char_end > len(text):
            return CitationCheck("INVALID", "character offsets are outside page text", page)
        if text[citation.char_start : citation.char_end] != citation.text_span:
            return CitationCheck("INVALID", "text span does not match exact character offsets", page)
        if not citation.line_ids:
            return CitationCheck("UNVERIFIED", "line_ids are missing", page)
        line_ranges = _line_ranges(page)
        unknown = set(citation.line_ids) - set(line_ranges)
        if unknown:
            return CitationCheck("INVALID", f"unknown line_ids: {sorted(unknown)}", page)
        if not any(
            start < citation.char_end and end > citation.char_start
            for line_id in citation.line_ids
            for start, end in [line_ranges[line_id]]
        ):
            return CitationCheck("INVALID", "line_ids do not cover the cited span", page)
        return CitationCheck("VALID", "exact citation verified", page)


def _line_ranges(page: PageSnapshot) -> dict[str, tuple[int, int]]:
    ranges: dict[str, tuple[int, int]] = {}
    cursor = 0
    for index, (line_id, line_text) in enumerate(page.line_texts.items()):
        start = cursor
        end = start + len(line_text)
        ranges[line_id] = (start, end)
        cursor = end + (1 if index < len(page.line_texts) - 1 else 0)
    return ranges


def _valid_bbox(value: list[float]) -> bool:
    return len(value) == 4 and all(0 <= item <= 1 for item in value) and value[2] > value[0] and value[3] > value[1]
