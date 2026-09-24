"""Assemble fragments, in reading order, into logical tables."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from .columns import _row_is_header, detect_column_bounds, pick_anchor_column, slice_lines
from .config import Config
from .lines import group_physical_lines
from .merge import should_merge
from .rows import merge_into_logical_rows
from .types import Fragment, LogicalTable, PhysicalLine, SlicedLine
from .validate import validate


@dataclass
class _OpenTable:
    doc_id: str
    fragment_ids: list[int]
    header: list[str]
    anchor_col: int
    page_start: int
    page_end: int
    last_fragment: Fragment
    sliced_rows: list[SlicedLine] = field(default_factory=list)


def build_tables(fragments: Sequence[Fragment], config: Config = Config()) -> list[LogicalTable]:
    """Walk `fragments` in reading order, keeping one currently-open table.
    A fragment either continues the open table (per `should_merge`) or
    closes it and starts a new one. Before joining a continuation
    fragment, its repeated table-header row (if any) is dropped; a leading
    or trailing page-boilerplate line (e.g. "Trang 3/10") is dropped from
    every fragment before column detection.
    """
    tables: list[LogicalTable] = []
    open_table: _OpenTable | None = None

    for idx, fragment in enumerate(fragments):
        lines = _strip_page_boilerplate(group_physical_lines(fragment.words, config), config)
        if not lines:
            continue

        bounds = detect_column_bounds(lines, config)
        sliced = slice_lines(lines, bounds)
        header_row, data_rows = sliced[0], sliced[1:]

        merged = (
            open_table is not None and should_merge(open_table.last_fragment, fragment, config)[0]
        )

        if merged:
            assert open_table is not None
            if _row_is_header([c.text for c in header_row.columns], open_table.anchor_col, config):
                open_table.sliced_rows.extend(data_rows)
            else:
                open_table.sliced_rows.extend(sliced)
            open_table.fragment_ids.append(idx)
            open_table.page_end = fragment.page
            open_table.last_fragment = fragment
        else:
            if open_table is not None:
                tables.append(_finalize_table(open_table, config))
            preview = [[c.text for c in row.columns] for row in data_rows]
            anchor_col = pick_anchor_column(preview, config) if preview else 0
            open_table = _OpenTable(
                doc_id=fragment.doc_id,
                fragment_ids=[idx],
                header=[c.text for c in header_row.columns],
                anchor_col=anchor_col,
                page_start=fragment.page,
                page_end=fragment.page,
                last_fragment=fragment,
                sliced_rows=data_rows,
            )

    if open_table is not None:
        tables.append(_finalize_table(open_table, config))

    return tables


def _finalize_table(state: _OpenTable, config: Config) -> LogicalTable:
    rows = merge_into_logical_rows(state.sliced_rows, state.anchor_col, config)
    table = LogicalTable(
        doc_id=state.doc_id,
        fragment_ids=state.fragment_ids,
        header=state.header,
        rows=rows,
        page_start=state.page_start,
        page_end=state.page_end,
        checks={},
    )
    table.checks = validate(table, config)
    return table


def _strip_page_boilerplate(lines: list[PhysicalLine], config: Config) -> list[PhysicalLine]:
    if not lines:
        return lines

    pattern = re.compile(config.page_boilerplate_pattern, re.IGNORECASE)

    def is_boilerplate(line: PhysicalLine) -> bool:
        text = " ".join(w.text for w in line.words).strip()
        return bool(pattern.fullmatch(text))

    start = 1 if is_boilerplate(lines[0]) else 0
    end = len(lines)
    if end - start > 0 and is_boilerplate(lines[-1]):
        end -= 1
    return lines[start:end]
