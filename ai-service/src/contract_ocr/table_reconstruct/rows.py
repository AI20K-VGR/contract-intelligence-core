"""Merge column-sliced physical lines into logical rows via the anchor column."""

from __future__ import annotations

import statistics
from collections.abc import Sequence

from .columns import _looks_like_anchor_value, _normalize_confusables, _score_column
from .config import Config
from .numbers import parse_vn_number
from .types import Cell, LogicalRow, SlicedLine


def merge_into_logical_rows(
    lines: Sequence[SlicedLine], anchor_col: int, config: Config = Config()
) -> list[LogicalRow]:
    """A value in the anchor column starts a new logical row; no value
    merges this line into the currently open row (text joined, bboxes
    accumulated). When the anchor column looks broken, three fallback
    layers decide in order:

    a) normalize OCR-confusable characters (l/I/| -> 1, O -> 0, S -> 5)
       and re-check — a recovered value still starts a new row, flagged
       `needs_review`.
    b) a vertical gap to the previous line bigger than
       `config.vertical_gap_new_row_ratio` times the median inter-line gap
       starts a new row, flagged `needs_review`.
    c) a value in the secondary anchor column (the next-best-scoring
       column besides `anchor_col`) starts a new row, flagged
       `needs_review`.

    Otherwise the line merges into the open row. When uncertain, this
    function always leans towards flagging rather than guessing.
    """
    if not lines:
        return []

    gaps = [b.y0 - a.y1 for a, b in zip(lines, lines[1:])]
    positive_gaps = [g for g in gaps if g > 0]
    median_gap = statistics.median(positive_gaps) if positive_gaps else 0.0

    secondary_col = _pick_secondary_anchor_column(lines, anchor_col, config)

    finished_rows: list[LogicalRow] = []
    open_cells: list[Cell] | None = None
    open_flags: set[str] = set()

    def close_open_row() -> None:
        nonlocal open_cells, open_flags
        if open_cells is None:
            return
        touched_pages = {p for cell in open_cells for p in cell.pages}
        flags = set(open_flags)
        if len(touched_pages) > 1:
            flags.add("spans_page_break")
        finished_rows.append(LogicalRow(index=len(finished_rows), cells=open_cells, flags=flags))
        open_cells = None
        open_flags = set()

    for i, line in enumerate(lines):
        is_new_row, flags = _classify_line(
            line, lines[i - 1] if i > 0 else None, anchor_col, secondary_col, median_gap, config
        )
        if i == 0 or open_cells is None:
            is_new_row = True

        if is_new_row:
            close_open_row()
            open_cells = [Cell(text="", bboxes=[], pages=[]) for _ in line.columns]
            open_flags = flags

        for cell, col in zip(open_cells, line.columns):
            if not col.text:
                continue
            cell.text = f"{cell.text} {col.text}".strip() if cell.text else col.text
            if col.bbox is not None:
                cell.bboxes.append(col.bbox)
                cell.pages.append(line.page)

    close_open_row()
    _fill_down(finished_rows, anchor_col)
    return finished_rows


def _classify_line(
    line: SlicedLine,
    previous: SlicedLine | None,
    anchor_col: int,
    secondary_col: int | None,
    median_gap: float,
    config: Config,
) -> tuple[bool, set[str]]:
    raw_anchor = line.columns[anchor_col].text.strip() if anchor_col < len(line.columns) else ""

    if _looks_like_anchor_value(raw_anchor):
        return True, set()

    normalized = _normalize_confusables(raw_anchor, config)
    if _looks_like_anchor_value(normalized):
        return True, {"needs_review"}

    if previous is not None:
        gap = line.y0 - previous.y1
        if median_gap > 0 and gap > config.vertical_gap_new_row_ratio * median_gap:
            return True, {"needs_review"}

    if (
        secondary_col is not None
        and secondary_col < len(line.columns)
        and line.columns[secondary_col].text.strip()
    ):
        return True, {"needs_review"}

    return False, set()


def _pick_secondary_anchor_column(
    lines: Sequence[SlicedLine], anchor_col: int, config: Config
) -> int | None:
    """Pick a secondary, backup anchor column for fallback layer (c).

    Unlike `pick_anchor_column`, this only considers columns whose
    non-empty values mostly parse as numbers (an STT column, a secondary
    code column, or a money column) — never a free-text column such as a
    description, even one that happens to score well by fill rate. A
    description column is filled on every physical line, including the
    continuation lines of a wrapped multi-line cell, so scoring it the
    same way as the primary anchor would make every wrapped line look like
    the start of a new row.
    """
    preview = [[col.text for col in line.columns] for line in lines[: config.anchor_preview_rows]]
    if not preview:
        return None

    num_cols = max(len(r) for r in preview)
    best_col: int | None = None
    best_score = -1.0
    for c in range(num_cols):
        if c == anchor_col:
            continue
        values = [r[c] if c < len(r) else "" for r in preview]
        non_empty = [v for v in values if v.strip()]
        if not non_empty:
            continue
        numeric_like = sum(1 for v in non_empty if _parses_as_number(v))
        if numeric_like / len(non_empty) < 0.5:
            continue
        score = _score_column(values, len(preview), config)
        if score > best_score:
            best_score = score
            best_col = c

    return best_col


def _parses_as_number(text: str) -> bool:
    try:
        parse_vn_number(text)
        return True
    except ValueError:
        return False


def _fill_down(rows: list[LogicalRow], anchor_col: int) -> None:
    """Copy a still-open value down from the row above into an empty cell —
    the vertically-merged-cell case. Never applied to the anchor column
    itself: an empty anchor is how `is_total_row` recognizes a totals row,
    and a row created via fallback (b)/(c) is meant to stay flagged
    `needs_review` rather than silently look like a normal numbered row.
    """
    for i in range(1, len(rows)):
        previous_row = rows[i - 1]
        current_row = rows[i]
        for c, cell in enumerate(current_row.cells):
            if c == anchor_col or cell.text.strip() or c >= len(previous_row.cells):
                continue
            previous_cell = previous_row.cells[c]
            if not previous_cell.text.strip():
                continue
            cell.text = previous_cell.text
            current_row.flags.add("filled_down")
