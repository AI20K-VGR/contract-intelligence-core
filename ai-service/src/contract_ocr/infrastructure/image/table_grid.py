"""Bordered-table grid detection from a rendered page image (section 9).

Ruling-line morphology finds row/column boundaries directly from pixels, with no
dependency on OCR word granularity. This matters because no scanned-page word source
currently wired into this codebase's live pipeline produces word-level bbox --
`word_adapters.ocr.OcrAdapter` (dormant, no caller) detects at line granularity only
(see docs/ai1-decisions.md D5/D7) -- so `table_reconstruct`'s word-alignment column
detection cannot work on today's scanned OCR output. Ruling-line detection sidesteps
that: it needs no OCR output at all, only the rendered page image.

Deliberately NOT covered here: borderless tables (no ruling lines to detect at all --
a real, disclosed gap; see section 9's "word bbox alignment" approach, which needs
word-level OCR this codebase does not yet produce for scanned pages).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class TableGrid:
    """One detected bordered-table region, in the input image's own pixel space."""

    bbox: tuple[int, int, int, int]  # x0, y0, x1, y1
    row_boundaries: list[int]  # y pixel positions of horizontal ruling lines, ascending
    col_boundaries: list[int]  # x pixel positions of vertical ruling lines, ascending

    def cells(self) -> list[list[tuple[int, int, int, int]]]:
        """Row-major grid of cell bboxes (x0, y0, x1, y1), same pixel space as `bbox`."""
        return [
            [
                (
                    self.col_boundaries[c],
                    self.row_boundaries[r],
                    self.col_boundaries[c + 1],
                    self.row_boundaries[r + 1],
                )
                for c in range(len(self.col_boundaries) - 1)
            ]
            for r in range(len(self.row_boundaries) - 1)
        ]


def _binary_ink_mask(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if image.ndim == 3 else image
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return binary


def _line_mask(binary: np.ndarray, kernel: tuple[int, int]) -> np.ndarray:
    structure = cv2.getStructuringElement(cv2.MORPH_RECT, kernel)
    return cv2.morphologyEx(binary, cv2.MORPH_OPEN, structure, iterations=1)


def _boundary_positions(line_mask: np.ndarray, axis: int, min_run: int) -> list[int]:
    """Positions along `axis` (0=rows/y, 1=cols/x) where `line_mask` has a
    long-enough run of ink, collapsing an N-pixel-thick ruling line to its
    single center coordinate."""
    projection = line_mask.sum(axis=1 - axis) if axis == 0 else line_mask.sum(axis=0)
    threshold = 255 * min_run
    is_line = projection >= threshold
    positions: list[int] = []
    start = None
    for index, flag in enumerate(is_line):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            positions.append((start + index - 1) // 2)
            start = None
    if start is not None:
        positions.append((start + len(is_line) - 1) // 2)
    return positions


def detect_bordered_tables(
    image: np.ndarray,
    *,
    min_rows: int = 2,
    min_cols: int = 2,
    line_length_divisor: int = 15,
    min_region_area_fraction: float = 0.01,
) -> list[TableGrid]:
    """Detect bordered-table regions in `image` (RGB or grayscale ndarray, the same
    shape `PdfRenderer`/an OCR engine already works with). Deterministic, pure CV --
    no OCR, no network, no LLM call. A region only counts as a table when at least
    `min_rows` x `min_cols` cells are found; a stray box or single ruled line is not
    a table and is discarded rather than reported as a false positive.

    `line_length_divisor` sizes the morphology kernel that isolates ruling-line
    strokes from character strokes: a candidate line must span at least
    `dimension // line_length_divisor` pixels along its own axis. This is a
    reasonable starting default (small enough that a short table's vertical rules
    still register, large enough to reject individual glyph strokes) -- it has NOT
    been calibrated against real scanned contracts yet (see docs/ai1-decisions.md);
    treat detections on real scans as provisional until that calibration happens.
    """
    height, width = image.shape[:2]
    binary = _binary_ink_mask(image)

    horizontal_len = max(15, width // line_length_divisor)
    vertical_len = max(15, height // line_length_divisor)
    horizontal_lines = _line_mask(binary, (horizontal_len, 1))
    vertical_lines = _line_mask(binary, (1, vertical_len))
    grid_mask = cv2.bitwise_or(horizontal_lines, vertical_lines)

    contours, _ = cv2.findContours(grid_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = width * height * min_region_area_fraction
    grids: list[TableGrid] = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w * h < min_area:
            continue
        region_h = horizontal_lines[y : y + h, x : x + w]
        region_v = vertical_lines[y : y + h, x : x + w]
        rows = [y + p for p in _boundary_positions(region_h, axis=0, min_run=max(5, w // 4))]
        cols = [x + p for p in _boundary_positions(region_v, axis=1, min_run=max(5, h // 4))]
        if len(rows) - 1 < min_rows or len(cols) - 1 < min_cols:
            continue
        grids.append(TableGrid(bbox=(x, y, x + w, y + h), row_boundaries=rows, col_boundaries=cols))
    return grids
