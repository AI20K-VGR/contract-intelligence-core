"""Table extraction and cross-page continuation (section 11).

A table is recognized from consecutive `table_row` blocks on a page. When
the boundary detector/rule engine decide two pages' tables continue
(`TABLE_CONTINUE`), this module chains their rows together, merges a row
that was split mid-page-break, and marks a repeated header row so it is
excluded from the logical table while its provenance is kept.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz

from .config import TABLE_HEADER_SIMILARITY
from .header_footer_detector import HeaderFooterProfile
from .models import SourceBlockRef
from .schemas.block import TABLE_ROW, Block
from .schemas.document import Table, TableRow
from .schemas.page import Page


def parse_cells(text: str) -> list[str]:
    """Split a pipe-delimited row of text into stripped cell values."""
    parts = [cell.strip() for cell in text.split("|")]
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


@dataclass
class RawTableRow:
    block: Block
    cells: list[str]


@dataclass
class RawTable:
    """A run of consecutive table_row blocks found on a single page."""

    page: int
    rows: list[RawTableRow] = field(default_factory=list)

    @property
    def column_count(self) -> int:
        return len(self.rows[0].cells) if self.rows else 0

    @property
    def header_cells(self) -> list[str]:
        return self.rows[0].cells if self.rows else []


def extract_raw_tables(page: Page, header_footer: HeaderFooterProfile) -> list[RawTable]:
    """Group consecutive table_row blocks on one page into raw tables."""
    tables: list[RawTable] = []
    current: RawTable | None = None
    for block in page.blocks:
        if header_footer.is_noise(block, page):
            continue
        if block.type != TABLE_ROW:
            current = None
            continue
        cells = parse_cells(block.text)
        if not cells:
            continue
        if current is None:
            current = RawTable(page=page.page)
            tables.append(current)
        current.rows.append(RawTableRow(block=block, cells=cells))
    return [t for t in tables if t.rows]


def _header_similarity(a: list[str], b: list[str]) -> float:
    if not a or not b:
        return 0.0
    return fuzz.ratio(" | ".join(a), " | ".join(b))


def tables_continue(previous: RawTable, next_table: RawTable) -> tuple[bool, float]:
    """Decide whether `next_table` is the continuation of `previous`.

    Returns (is_continuation, confidence) using column-count and header
    similarity as the deciding signals (section 11).
    """
    if not previous.rows or not next_table.rows:
        return False, 0.0
    if previous.column_count != next_table.column_count:
        return False, 0.0

    similarity = _header_similarity(previous.header_cells, next_table.header_cells)
    if similarity >= TABLE_HEADER_SIMILARITY:
        return True, min(1.0, 0.9 + similarity / 1000.0)

    # Same column count but no matching header: still plausible, lower
    # confidence — the caller decides whether that clears the bar to merge.
    return True, 0.75


def is_incomplete_row(cells: list[str]) -> bool:
    """True if any cell is blank — a signal the row was split by a page
    break and its other half is on the next/previous page (section 7)."""
    return any(cell.strip() == "" for cell in cells)


def _merge_row_cells(a: list[str], b: list[str]) -> list[str]:
    return [cell_a if cell_a.strip() else cell_b for cell_a, cell_b in zip(a, b, strict=True)]


def _dedup_pages(pages: list[int]) -> list[int]:
    seen: list[int] = []
    for page in pages:
        if page not in seen:
            seen.append(page)
    return seen


def build_table(
    table_id: str,
    fragments: list[RawTable],
    header_similarity_threshold: float = TABLE_HEADER_SIMILARITY,
) -> Table:
    """Chain a document-ordered list of same-table page fragments into one
    logical `Table`.

    A fragment's first row is dropped (and recorded in
    `repeated_header_blocks`) whenever it matches the table's header. A row
    left incomplete at the end of one fragment is merged cell-by-cell with
    the first ordinary row of the next fragment, on the assumption it was
    split by the page break; provenance for both contributing blocks is
    kept on the merged row.
    """
    if not fragments:
        raise ValueError("build_table requires at least one fragment")

    columns = fragments[0].header_cells
    rows: list[TableRow] = []
    repeated_header_blocks: list[SourceBlockRef] = []

    pending: RawTableRow | None = None
    pending_page: int | None = None

    def flush_pending() -> None:
        nonlocal pending, pending_page
        if pending is not None:
            rows.append(
                TableRow(
                    values=pending.cells,
                    source_pages=[pending_page],
                    source_blocks=[
                        SourceBlockRef(page=pending_page, block_id=pending.block.block_id)
                    ],
                )
            )
            pending = None
            pending_page = None

    def queue(row: RawTableRow, page: int) -> None:
        nonlocal pending, pending_page
        flush_pending()
        pending = row
        pending_page = page

    for row in fragments[0].rows[1:]:
        queue(row, fragments[0].page)

    for fragment in fragments[1:]:
        fragment_rows = list(fragment.rows)
        if (
            fragment_rows
            and _header_similarity(fragment_rows[0].cells, columns) >= header_similarity_threshold
        ):
            repeated_header_blocks.append(
                SourceBlockRef(page=fragment.page, block_id=fragment_rows[0].block.block_id)
            )
            fragment_rows = fragment_rows[1:]

        if pending is not None and fragment_rows and is_incomplete_row(pending.cells):
            first_of_next = fragment_rows.pop(0)
            merged_cells = _merge_row_cells(pending.cells, first_of_next.cells)
            rows.append(
                TableRow(
                    values=merged_cells,
                    source_pages=_dedup_pages([pending_page, fragment.page]),  # type: ignore[list-item]
                    source_blocks=[
                        SourceBlockRef(page=pending_page, block_id=pending.block.block_id),
                        SourceBlockRef(page=fragment.page, block_id=first_of_next.block.block_id),
                    ],
                )
            )
            pending = None
            pending_page = None
        else:
            flush_pending()

        for row in fragment_rows:
            queue(row, fragment.page)

    flush_pending()

    return Table(
        table_id=table_id,
        page_start=fragments[0].page,
        page_end=fragments[-1].page,
        columns=columns,
        rows=rows,
        repeated_header_blocks=repeated_header_blocks,
    )
