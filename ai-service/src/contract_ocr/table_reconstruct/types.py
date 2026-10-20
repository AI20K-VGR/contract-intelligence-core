"""Data contracts for the table-reconstruction pipeline.

`Word` and `Fragment` are the fixed, external input shapes produced upstream
by OCR/PyMuPDF extraction and layout detection. `Cell`, `LogicalRow` and
`LogicalTable` are the fixed output shapes. Everything else here
(`PhysicalLine`, `ColumnValue`, `SlicedLine`) is this package's own internal
intermediate representation between those two: physical lines grouped by
y-coordinate, then sliced into per-column values once column bounds are
known. None of it crosses the package boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Bbox = tuple[float, float, float, float]


@dataclass(frozen=True)
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    page: int
    source: Literal["native", "ocr", "vision"]


@dataclass
class Fragment:
    """A table block on ONE page, already cut out by layout detection."""

    doc_id: str
    page: int
    bbox: Bbox
    words: list[Word]


@dataclass
class Cell:
    text: str
    bboxes: list[Bbox]
    pages: list[int]


@dataclass
class LogicalRow:
    index: int
    cells: list[Cell]
    flags: set[str]  # spans_page_break | filled_down | needs_review


@dataclass
class LogicalTable:
    doc_id: str
    fragment_ids: list[int]
    header: list[str]
    rows: list[LogicalRow]
    page_start: int
    page_end: int
    checks: dict


@dataclass
class PhysicalLine:
    """Words on one fragment sharing a y-band, in reading (left-to-right) order."""

    page: int
    words: list[Word]
    y0: float
    y1: float
    y_center: float


@dataclass
class ColumnValue:
    """A `PhysicalLine`'s content within one detected column band."""

    text: str
    bbox: Bbox | None


@dataclass
class SlicedLine:
    """A `PhysicalLine` after its words have been assigned to columns."""

    page: int
    y0: float
    y1: float
    columns: list[ColumnValue] = field(default_factory=list)
