"""Visual text-line boxes from a rendered page image -- pure OpenCV, no OCR,
no network call.

`mistral-ocr-2512` reads Vietnamese correctly but returns no geometry at all,
so line positions are measured here instead and matched to its text by
`text_geometry_alignment`. Each box is the tight ink extent of one visual line
(or one column segment of it); boxes come back in reading order.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class LineBox:
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0

    @property
    def center_y(self) -> float:
        return (self.y0 + self.y1) / 2


def _ink_mask(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if image.ndim == 3 else image
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    if image.ndim == 3:
        # A red company seal stamped over a signer's name would otherwise merge
        # with it into one "graphic" blob and hide the name; seal ink is not
        # body text, so red-dominant pixels are dropped.
        r, g, b = (image[..., i].astype(np.int16) for i in range(3))
        binary[(r - g > 50) & (r - b > 50)] = 0
    return binary


def _remove_rules(binary: np.ndarray) -> np.ndarray:
    """Drop long horizontal/vertical strokes (separators, underlines, borders):
    they carry no text and would otherwise glue neighbouring lines together."""
    height, width = binary.shape
    horizontal = cv2.morphologyEx(
        binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, width // 8), 1))
    )
    vertical = cv2.morphologyEx(
        binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(20, height // 8)))
    )
    return cv2.subtract(binary, cv2.bitwise_or(horizontal, vertical))


def _char_height(binary: np.ndarray) -> float:
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    heights = stats[1:count, cv2.CC_STAT_HEIGHT]
    heights = heights[(heights >= 4) & (heights <= binary.shape[0] // 10)]
    return float(np.median(heights)) if heights.size else 0.0


def _overlap_ratio(a: LineBox, b: LineBox) -> float:
    overlap = min(a.y1, b.y1) - max(a.y0, b.y0)
    return overlap / max(1, min(a.height, b.height))


def _union(a: LineBox, b: LineBox) -> LineBox:
    return LineBox(min(a.x0, b.x0), min(a.y0, b.y0), max(a.x1, b.x1), max(a.y1, b.y1))


def _merge_same_row(boxes: list[LineBox], max_gap: float) -> list[LineBox]:
    """Merge fragments of one visual line (word groups, detached accents) while
    keeping far-apart columns (signature blocks, two-column headers) separate."""
    merged: list[LineBox] = []
    for box in sorted(boxes, key=lambda b: (b.y0, b.x0)):
        for index, other in enumerate(merged):
            horizontal_gap = max(box.x0, other.x0) - min(box.x1, other.x1)
            if _overlap_ratio(box, other) >= 0.5 and horizontal_gap <= max_gap:
                merged[index] = _union(box, other)
                break
        else:
            merged.append(box)
    return merged


def _attach_accents(boxes: list[LineBox], char_height: float) -> list[LineBox]:
    """A tone mark separated from its letter by a few pixels forms its own
    flat box just above (or a dot just below) a text line; fold it in."""
    lines = [b for b in boxes if b.height >= 0.6 * char_height]
    marks = [b for b in boxes if b.height < 0.6 * char_height]
    for mark in marks:
        best = None
        for index, line in enumerate(lines):
            horizontally_inside = mark.x0 >= line.x0 - char_height and mark.x1 <= line.x1 + char_height
            vertical_gap = max(line.y0 - mark.y1, mark.y0 - line.y1, 0)
            if horizontally_inside and vertical_gap <= 0.6 * char_height:
                if best is None or vertical_gap < best[1]:
                    best = (index, vertical_gap)
        if best is not None:
            lines[best[0]] = _union(lines[best[0]], mark)
        elif mark.width >= char_height:
            # A short-but-wide run (e.g. "..." leaders) is still text.
            lines.append(mark)
    return lines


def _rows(boxes: list[LineBox]) -> list[list[LineBox]]:
    rows: list[list[LineBox]] = []
    for box in sorted(boxes, key=lambda b: b.center_y):
        if rows and _overlap_ratio(box, rows[-1][0]) >= 0.5:
            rows[-1].append(box)
        else:
            rows.append([box])
    return [sorted(row, key=lambda b: b.x0) for row in rows]


def _reading_order(boxes: list[LineBox]) -> list[LineBox]:
    return [box for row in _rows(boxes) for box in row]


def column_major_variant(boxes: list[LineBox]) -> list[LineBox] | None:
    """The same boxes with every run of consecutive two-box rows sharing one
    column gap (a signature block: "ĐẠI DIỆN BÊN A | ĐẠI DIỆN BÊN B" over
    "(Ký...) | (Ký...)") read column by column instead of row by row.
    Transcribers read such blocks down each column; a borderless table is read
    across. Returns None when the page has no such block. Callers keep
    whichever order their text actually aligns with."""
    rows = _rows(boxes)
    if not rows:
        return None
    line_height = sorted(b.height for b in boxes)[len(boxes) // 2]
    ordered: list[LineBox] = []
    changed = False
    i = 0
    while i < len(rows):
        if len(rows[i]) != 2:
            ordered.extend(rows[i])
            i += 1
            continue
        gap = (rows[i][0].x1, rows[i][1].x0)
        left, right = [rows[i][0]], [rows[i][1]]
        j = i + 1
        while j < len(rows):
            row = rows[j]
            # A block is one tight cluster: a far-away row (the page footer)
            # never joins it even if its gap happens to line up.
            if row[0].y0 - max(b.y1 for b in rows[j - 1]) > 4 * line_height:
                break
            if len(row) == 2:
                lo, hi = max(gap[0], row[0].x1), min(gap[1], row[1].x0)
                if lo >= hi:
                    break
                gap = (lo, hi)
                left.append(row[0])
                right.append(row[1])
            elif len(row) == 1 and row[0].x1 <= gap[1]:
                left.append(row[0])  # a lone signature/name under the left column
            elif len(row) == 1 and row[0].x0 >= gap[0]:
                right.append(row[0])
            else:
                break
            j += 1
        if j - i >= 2:
            ordered.extend(left)
            ordered.extend(right)
            changed = True
        else:
            ordered.extend(rows[i])
        i = j
    return ordered if changed else None


def detect_text_lines(
    image: np.ndarray, *, exclude: list[tuple[int, int, int, int]] | tuple = ()
) -> list[LineBox]:
    """Visual text-line boxes in reading order, in the image's pixel space.
    `exclude` regions (e.g. bordered table grids handled separately) are
    ignored entirely."""
    binary = _ink_mask(image)
    for x0, y0, x1, y1 in exclude:
        binary[max(0, y0) : y1, max(0, x0) : x1] = 0
    binary = _remove_rules(binary)
    char_height = _char_height(binary)
    if char_height <= 0:
        return []

    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (max(3, int(1.2 * char_height)), max(1, int(0.15 * char_height)))
    )
    dilated = cv2.dilate(binary, kernel)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(dilated, connectivity=8)

    boxes: list[LineBox] = []
    for label in range(1, count):
        x, y, w, h = stats[label, :4]
        region = (labels[y : y + h, x : x + w] == label) & (binary[y : y + h, x : x + w] > 0)
        points = cv2.findNonZero(region.astype(np.uint8))
        if points is None:
            continue
        rx, ry, rw, rh = cv2.boundingRect(points)
        box = LineBox(int(x + rx), int(y + ry), int(x + rx + rw), int(y + ry + rh))
        if box.width * box.height < 0.3 * char_height * char_height:
            continue  # speck
        boxes.append(box)

    boxes = _attach_accents(boxes, char_height)
    # Label/value pairs ("- Tên đơn vị:   CÔNG TY ...") leave a wider gap than a
    # word space but far narrower than a column gutter.
    boxes = _merge_same_row(boxes, max_gap=4.0 * char_height)
    # Anything much taller than a text line is a graphic (stamp, signature,
    # logo): it has no transcribed text to align with.
    boxes = [b for b in boxes if b.height <= 3.0 * char_height]
    return _reading_order(boxes)
