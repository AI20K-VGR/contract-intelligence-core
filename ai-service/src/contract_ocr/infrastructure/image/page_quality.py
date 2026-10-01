"""How readable a rendered scan is, measured before the OCR call -- pure OpenCV.

Runs before any paid call. A document with too many failing pages is refused
unread; otherwise a failing page is read once, without the extra readers that
noise would keep triggering. Each check names what is wrong, so the user or a
reviewer sees why:

- `blur`: stroke edges are soft for the ink contrast available (out-of-focus
  scan, or a low-resolution scan scaled up).
- `low_contrast`: ink barely darker than the paper (faded print, pale scan).
- `noise`: grain over the paper, the kind that breaks thin strokes apart.
- `speckle`: dirt, toner dust and salt-and-pepper dots; tolerated far longer
  when the ink contrast is good (`max_speckle`).

Thresholds were set on the labelled local scans at 150 DPI (the backend
default): clean scans measured sharpness 0.86-1.00, ink contrast >= 170, noise
0 and <= 150 speckles per megapixel; the `scanned_bad` scan measured 410-716
speckles per megapixel with everything else clean. Synthetic degradations
(`degradation.py`) land clearly past each threshold: mild blur 0.74, a 75 DPI
scan scaled up 0.76, low contrast 81, grain sigma 15 noise 5.9. Horizontal
motion blur is not caught.
"""

from __future__ import annotations

import cv2
import numpy as np

# Below this share of dark pixels there is too little ink to judge (a heading
# or a signature on an empty sheet); such a page is not flagged.
MIN_INK_SHARE = 0.002
# A pixel this much darker than the paper is ink candidate.
INK_OFFSET = 20
MIN_SHARPNESS = 0.80
MIN_CONTRAST = 120.0
MAX_NOISE = 3.5
MAX_SPECKLE_PER_MEGAPIXEL = 300.0
# With crisp dark ink a 1-2 px dot cannot pass for a stroke or a diacritic, so
# speckle is tolerated much longer: the `scanned_bad` scan (contrast 197-217,
# 410-716 speckles/MP) is read, salt-and-pepper noise (7,966/MP) is not.
GOOD_CONTRAST = 190.0
MAX_SPECKLE_GOOD_CONTRAST = 1000.0
# Dots of at most this many pixels count as speckle: smaller than any glyph
# part at 150 DPI, the size of dust and JPEG/scanner specks.
SPECKLE_MAX_AREA = 2
# Every threshold above was set on pages rendered at this resolution. A page
# rendered finer is scaled down to it first: rendering a 150-200 DPI scan at
# 300 DPI only enlarges it, softening every edge in pixel terms (a clean scan
# measured sharpness 0.98 at 150 DPI and 0.69 at 300 DPI).
REFERENCE_DPI = 150


def _gray(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if image.ndim == 3 else image


def measure(image: np.ndarray, dpi: int = REFERENCE_DPI) -> dict[str, float] | None:
    """The four signals behind `assess` for a page rendered at `dpi`, or None
    when the page has too little ink."""
    gray = _gray(image)
    if dpi > REFERENCE_DPI:
        scale = REFERENCE_DPI / dpi
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    paper = float(np.median(gray))
    candidate = gray < paper - INK_OFFSET
    if candidate.mean() < MIN_INK_SHARE:
        return None
    # The core of the strokes, not their anti-aliased edges.
    contrast = max(paper - float(np.percentile(gray[candidate], 10)), 1.0)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = np.hypot(gx, gy)
    # A 3x3 Sobel over a crisp step of height `contrast` peaks at 4x the step.
    edges = magnitude[magnitude > contrast]
    sharpness = float(np.percentile(edges, 90)) / (4 * contrast) if edges.size else 0.0
    residual = gray.astype(np.int16) - cv2.medianBlur(gray, 5).astype(np.int16)
    background = gray > paper - INK_OFFSET
    # Median absolute deviation, scaled to a Gaussian sigma: text edges barely move it.
    noise = float(np.median(np.abs(residual[background]))) * 1.4826
    dark = (gray < paper - contrast / 2).astype(np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    specks = int((stats[1:count, cv2.CC_STAT_AREA] <= SPECKLE_MAX_AREA).sum())
    return {
        "sharpness": sharpness,
        "contrast": contrast,
        "noise": noise,
        "speckle": specks / (gray.size / 1e6),
    }


def max_speckle(contrast: float) -> float:
    """Speckles per megapixel a page with this ink contrast may have."""
    return MAX_SPECKLE_GOOD_CONTRAST if contrast >= GOOD_CONTRAST else MAX_SPECKLE_PER_MEGAPIXEL


def assess(image: np.ndarray, dpi: int = REFERENCE_DPI) -> list[str]:
    """What makes this page, rendered at `dpi`, hard to read; empty when nothing does."""
    signals = measure(image, dpi)
    if signals is None:
        return []
    reasons = []
    if signals["sharpness"] < MIN_SHARPNESS:
        reasons.append("blur")
    if signals["contrast"] < MIN_CONTRAST:
        reasons.append("low_contrast")
    if signals["noise"] > MAX_NOISE:
        reasons.append("noise")
    if signals["speckle"] > max_speckle(signals["contrast"]):
        reasons.append("speckle")
    return reasons


class OpenCvPageQuality:
    """`PageQualityAssessor` port implementation."""

    def assess(self, image: np.ndarray, dpi: int) -> list[str]:
        return assess(image, dpi)
