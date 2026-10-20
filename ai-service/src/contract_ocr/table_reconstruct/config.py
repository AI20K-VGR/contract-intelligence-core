"""Every tunable threshold and score weight used by this package, in one place.

Kept free of business logic so the heuristics can be retuned without
touching the algorithms in `lines.py`, `columns.py`, `rows.py`, `merge.py`,
`tables.py` or `validate.py` — none of them hardcode a magic number of
their own; they all read from a `Config` instance (defaulted, so existing
call sites keep working untouched).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MergeScoreWeights:
    """Points awarded by `should_merge` for each corroborating signal, and
    the minimum total required to actually merge two fragments."""

    column_signature_match: int = 3
    anchor_continuous: int = 3
    no_header_in_next_fragment: int = 2
    continued_marker_present: int = 2
    prev_fragment_ends_near_bottom: int = 1
    next_fragment_starts_near_top: int = 1
    merge_threshold: int = 5


@dataclass(frozen=True)
class Config:
    # group_physical_lines: words within this many median-char-heights of a
    # line's running y-center belong to that same physical line.
    line_grouping_tolerance_ratio: float = 0.6

    # detect_column_bounds: how many lines after the header line are used to
    # build the x-axis projection profile (header + this many).
    column_bounds_preview_lines: int = 5

    # detect_column_bounds: a gap between adjacent ink spans narrower than
    # this (in PDF points) is ordinary word-spacing, not a column boundary.
    min_column_gap_pt: float = 8.0

    # pick_anchor_column: how many leading rows are scored to pick the
    # anchor column.
    anchor_preview_rows: int = 20

    # pick_anchor_column: score multiplier when a column's values are
    # strictly increasing numbers.
    ascending_numeric_bonus: float = 1.5

    # merge_into_logical_rows fallback (b): a vertical gap larger than this
    # multiple of the median inter-line gap starts a new logical row even
    # when the anchor column looks empty.
    vertical_gap_new_row_ratio: float = 1.4

    # column_signature / should_merge: two column boundaries are considered
    # the same position once their normalized (0..1) deviation is under this.
    column_signature_edge_tolerance: float = 0.025

    # column_signature: decimal places kept after normalizing by page width.
    column_signature_round_digits: int = 3

    # should_merge: how close (as a fraction of the fragment's own bbox
    # height) a fragment's last/first line must be to its bbox's
    # bottom/top edge to count as "ends near the bottom" / "starts near
    # the top" of the content area.
    edge_band_ratio: float = 0.15

    # merge_into_logical_rows / should_merge fallback (a): OCR-confusable
    # characters normalized to digits before checking whether an anchor
    # cell "has a value".
    confusable_digit_map: dict[str, str] = field(
        default_factory=lambda: {"l": "1", "I": "1", "|": "1", "O": "0", "S": "5"}
    )

    # should_merge: substrings (case-insensitive) that mark an explicit
    # continuation between two fragments.
    continued_markers: tuple[str, ...] = ("(tiếp theo)", "(tiep theo)")

    # should_merge hard gate: a heading between two fragments always blocks
    # a merge. Checked against the trailing line of the first fragment and
    # the leading line of the second, since `Fragment` carries only the two
    # candidate table blocks and not the paragraph blocks between them.
    heading_barrier_pattern: str = r"^\s*(ĐIỀU|PHỤ\s*LỤC|BIỂU)\b"

    # build_tables: a leading/trailing physical line matching this pattern
    # (e.g. a bare "Trang 3/10") is dropped before column detection.
    page_boilerplate_pattern: str = r"(trang|page)\s*\d+(\s*/\s*\d+)?"

    # is_total_row: keywords marking a "Tổng cộng"/"Cộng"/"Total" row.
    total_row_pattern: str = r"(tổng\s*cộng|tổng|cộng|total)"

    scoring: MergeScoreWeights = field(default_factory=MergeScoreWeights)
