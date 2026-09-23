"""Column detection, anchor-column scoring, and column-shape helpers.

Also hosts a few small helpers shared by `rows.py`, `merge.py`, `tables.py`
and `validate.py` (anchor-value recognition, OCR-confusable normalization,
header-row detection) since they all revolve around "what does this column
look like", which is this module's concern.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Container, Sequence

from .config import Config
from .numbers import parse_vn_number
from .types import ColumnValue, PhysicalLine, SlicedLine, Word


def detect_column_bounds(lines: Sequence[PhysicalLine], config: Config = Config()) -> list[float]:
    """Build an x-axis projection profile from the header line plus the next
    `config.column_bounds_preview_lines` lines, then return it as a list of
    column boundaries (length = number of columns + 1) to be applied as-is
    to the rest of the fragment.

    Adjacent word spans closer than `config.min_column_gap_pt` are treated
    as ordinary word-spacing within one column; wider gaps become column
    boundaries (placed at the gap's midpoint).
    """
    preview = list(lines[: 1 + config.column_bounds_preview_lines])
    intervals = sorted((w.x0, w.x1) for line in preview for w in line.words)
    if not intervals:
        return []

    merged: list[list[float]] = [list(intervals[0])]
    for x0, x1 in intervals[1:]:
        if x0 - merged[-1][1] < config.min_column_gap_pt:
            merged[-1][1] = max(merged[-1][1], x1)
        else:
            merged.append([x0, x1])

    bounds = [merged[0][0]]
    for (_, prev_x1), (next_x0, _) in zip(merged, merged[1:]):
        bounds.append((prev_x1 + next_x0) / 2)
    bounds.append(merged[-1][1])
    return bounds


def slice_line_into_columns(line: PhysicalLine, bounds: Sequence[float]) -> list[ColumnValue]:
    """Assign a physical line's words to the columns described by `bounds`
    (as returned by `detect_column_bounds`), joining each column's words
    into one text value with their union bbox."""
    num_cols = max(len(bounds) - 1, 1)
    buckets: list[list[Word]] = [[] for _ in range(num_cols)]
    for word in line.words:
        center = (word.x0 + word.x1) / 2
        buckets[_assign_column(center, bounds)].append(word)

    columns: list[ColumnValue] = []
    for bucket in buckets:
        if not bucket:
            columns.append(ColumnValue(text="", bbox=None))
            continue
        bucket.sort(key=lambda w: w.x0)
        text = " ".join(w.text for w in bucket)
        bbox = (
            min(w.x0 for w in bucket),
            min(w.y0 for w in bucket),
            max(w.x1 for w in bucket),
            max(w.y1 for w in bucket),
        )
        columns.append(ColumnValue(text=text, bbox=bbox))
    return columns


def slice_lines(lines: Sequence[PhysicalLine], bounds: Sequence[float]) -> list[SlicedLine]:
    """`slice_line_into_columns` applied over a whole fragment's lines."""
    return [
        SlicedLine(page=line.page, y0=line.y0, y1=line.y1, columns=slice_line_into_columns(line, bounds))
        for line in lines
    ]


def _assign_column(x_center: float, bounds: Sequence[float]) -> int:
    if len(bounds) < 2:
        return 0
    if x_center <= bounds[0]:
        return 0
    for i in range(len(bounds) - 1):
        if bounds[i] <= x_center <= bounds[i + 1]:
            return i
    return len(bounds) - 2


def pick_anchor_column(
    preview_rows: Sequence[Sequence[str]],
    config: Config = Config(),
    *,
    exclude: Container[int] = (),
) -> int:
    """Score each column over the first `config.anchor_preview_rows` rows as
    `fill_rate * format_consistency * (ascending_numeric_bonus if strictly
    increasing else 1)` and return the winning column's index (ties broken
    towards the leftmost column). `exclude` lets callers pick a *secondary*
    anchor by excluding the primary one (used by `merge_into_logical_rows`'s
    fallback layer c).

    A row that looks like a "Tổng cộng"/"Cộng"/"Total" summary row is
    dropped before scoring — by definition such a row has no sequence
    number, and without this it would unfairly count against the true
    anchor column's fill rate and let a merely-ascending data column
    (e.g. a running money total) outscore it.
    """
    total_pattern = re.compile(config.total_row_pattern, re.IGNORECASE)
    candidates = [
        row for row in preview_rows if not any(total_pattern.search(cell) for cell in row)
    ]
    rows = list(candidates[: config.anchor_preview_rows])
    if not rows:
        raise ValueError("preview_rows must not be empty")

    num_cols = max(len(r) for r in rows)
    best_index: int | None = None
    best_score = -1.0
    for c in range(num_cols):
        if c in exclude:
            continue
        column_values = [r[c] if c < len(r) else "" for r in rows]
        score = _score_column(column_values, len(rows), config)
        if score > best_score:
            best_score = score
            best_index = c

    if best_index is None:
        raise ValueError("no eligible columns to score")
    return best_index


def column_signature(
    bounds: Sequence[float], page_width: float, config: Config = Config()
) -> list[float]:
    """Normalize column boundaries by page width and round, so boundaries
    from two different fragments/pages become comparable."""
    if page_width <= 0:
        raise ValueError("page_width must be positive")
    digits = config.column_signature_round_digits
    return [round(b / page_width, digits) for b in bounds]


def _shape_signature(value: str) -> str:
    return "".join("d" if ch.isdigit() else "a" if ch.isalpha() else ch for ch in value)


def _format_consistency(values: Sequence[str]) -> float:
    if not values:
        return 0.0
    counts = Counter(_shape_signature(v) for v in values)
    return counts.most_common(1)[0][1] / len(values)


def _is_ascending(values: Sequence[str]) -> bool:
    if len(values) < 2:
        return False
    numbers = []
    for v in values:
        try:
            numbers.append(parse_vn_number(v))
        except ValueError:
            return False
    return all(a < b for a, b in zip(numbers, numbers[1:]))


def _score_column(values: Sequence[str], total_rows: int, config: Config) -> float:
    non_empty = [v for v in values if v.strip()]
    fill_rate = len(non_empty) / total_rows if total_rows else 0.0
    consistency = _format_consistency(non_empty)
    bonus = config.ascending_numeric_bonus if _is_ascending(non_empty) else 1.0
    return fill_rate * consistency * bonus


def _normalize_confusables(text: str, config: Config = Config()) -> str:
    """Map OCR-confusable characters to the digits they're commonly
    misread from (l/I/| -> 1, O -> 0, S -> 5) before checking whether an
    anchor-column value "looks like" a number."""
    return text.translate(str.maketrans(config.confusable_digit_map))


def _looks_like_anchor_value(text: str) -> bool:
    return text.strip().isdigit()


def _row_is_header(column_texts: Sequence[str], anchor_col: int, config: Config = Config()) -> bool:
    """A row counts as a header when its anchor-column cell is empty or
    doesn't look like a sequence number — the normal shape of a labelled
    column header rather than an "STT" value."""
    if anchor_col >= len(column_texts):
        return True
    anchor_text = column_texts[anchor_col].strip()
    if not anchor_text:
        return True
    return not _looks_like_anchor_value(_normalize_confusables(anchor_text, config))
