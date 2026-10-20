"""What is on a rendered page before any OCR call is paid for -- pure OpenCV.

- `is_blank`: nothing on the sheet at all. A blank scan sent to OCR costs a page
  and comes back empty, which then reads as an extraction failure.
- `unexplained_lines`: visual text lines no native text-layer line covers. A
  page whose short text layer ("PHỤ LỤC 01") covers every line of ink needs no
  OCR; one with text drawn as vector outlines or pasted as an image does.

Both err towards OCR: a speck or shadow they cannot rule out means "not blank",
and any uncovered line means "OCR it".
"""

from __future__ import annotations

import cv2
import numpy as np

from contract_ocr.domain.bbox import BBox
from contract_ocr.infrastructure.image.line_geometry import LineBox, detect_text_lines

# Ink must be this much darker than the paper: faded or pencil text still is,
# show-through from the back of the sheet is not.
INK_CONTRAST = 60
# Scanner shadows along the sheet edge are not content.
EDGE_MARGIN = 0.02
# Smallest mark that counts, as a fraction of the page's shorter side (~1 mm on
# A4): dust and JPEG noise are smaller, a single printed digit is larger.
MIN_MARK = 0.004


def _gray(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if image.ndim == 3 else image


def is_blank(image: np.ndarray) -> bool:
    gray = _gray(image)
    height, width = gray.shape
    paper = float(np.median(gray))
    ink = (gray < paper - INK_CONTRAST).astype(np.uint8)
    margin_y, margin_x = int(EDGE_MARGIN * height), int(EDGE_MARGIN * width)
    ink[:margin_y, :] = 0
    ink[height - margin_y :, :] = 0
    ink[:, :margin_x] = 0
    ink[:, width - margin_x :] = 0
    count, _, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    if count <= 1:
        return True
    extent = np.maximum(stats[1:count, cv2.CC_STAT_WIDTH], stats[1:count, cv2.CC_STAT_HEIGHT])
    return not bool((extent >= max(4, round(MIN_MARK * min(height, width)))).any())


def unexplained_lines(image: np.ndarray, covered: list[BBox]) -> list[LineBox]:
    """Visual text lines in `image` that no normalized box in `covered` touches
    (padded by half a line height, since glyph boxes and ink extents differ)."""
    height, width = image.shape[:2]
    lines = detect_text_lines(image)
    if not lines:
        return []
    pad = sorted(b.height for b in lines)[len(lines) // 2] / 2
    regions = [
        (b.x1 * width - pad, b.y1 * height - pad, b.x2 * width + pad, b.y2 * height + pad)
        for b in covered
    ]
    return [
        line
        for line in lines
        if not any(
            line.x0 < x1 and line.x1 > x0 and line.y0 < y1 and line.y1 > y0
            for x0, y0, x1, y1 in regions
        )
    ]
