"""Deterministic table reconstruction from already-normalized OCR/PyMuPDF words.

Pure logic only: no LLM calls, no network access, no PDF/file I/O. Every
function here is a pure function of its inputs (plus an optional `Config`)
— same input always yields the same output. All monetary/numeric values use
`Decimal`; floats are never used for anything that represents money.

Pipeline, in order:
    1. `group_physical_lines`  — words -> physical lines (by y-coordinate)
    2. `detect_column_bounds`  — physical lines -> column x-boundaries
    3. `pick_anchor_column`    — pick the sequential-number ("STT") column
    4. `merge_into_logical_rows` — physical lines -> logical rows
    5. `should_merge` / `build_tables` — join fragments across page breaks
    6. `validate`              — consistency checks on the finished table
"""

from __future__ import annotations

from .columns import column_signature, detect_column_bounds, pick_anchor_column, slice_lines
from .config import Config, MergeScoreWeights
from .lines import group_physical_lines
from .merge import should_merge
from .numbers import is_total_row, parse_vn_number, vn_words_to_number
from .rows import merge_into_logical_rows
from .tables import build_tables
from .types import (
    Cell,
    ColumnValue,
    Fragment,
    LogicalRow,
    LogicalTable,
    PhysicalLine,
    SlicedLine,
    Word,
)
from .validate import validate

__all__ = [
    "Cell",
    "ColumnValue",
    "Config",
    "Fragment",
    "LogicalRow",
    "LogicalTable",
    "MergeScoreWeights",
    "PhysicalLine",
    "SlicedLine",
    "Word",
    "build_tables",
    "column_signature",
    "detect_column_bounds",
    "group_physical_lines",
    "is_total_row",
    "merge_into_logical_rows",
    "parse_vn_number",
    "pick_anchor_column",
    "should_merge",
    "slice_lines",
    "validate",
    "vn_words_to_number",
]
