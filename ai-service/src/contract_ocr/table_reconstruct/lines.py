"""Group words into physical lines by y-coordinate."""

from __future__ import annotations

import statistics
from collections.abc import Sequence

from .config import Config
from .types import PhysicalLine, Word


def group_physical_lines(words: Sequence[Word], config: Config = Config()) -> list[PhysicalLine]:
    """Cluster words sharing a page into physical lines using a tolerance of
    `config.line_grouping_tolerance_ratio` times the median word height.

    Clustering runs independently per page (an OCR/PyMuPDF word never
    belongs to two pages at once) and uses each cluster's running mean
    y-center rather than its first word's, so a line doesn't drift as words
    are added to it.
    """
    if not words:
        return []

    heights = [w.y1 - w.y0 for w in words if w.y1 > w.y0]
    median_height = statistics.median(heights) if heights else 1.0
    tolerance = max(config.line_grouping_tolerance_ratio * median_height, 1e-6)

    by_page: dict[int, list[Word]] = {}
    for word in words:
        by_page.setdefault(word.page, []).append(word)

    lines: list[PhysicalLine] = []
    for page in sorted(by_page):
        page_words = sorted(by_page[page], key=lambda w: ((w.y0 + w.y1) / 2, w.x0))

        clusters: list[list[Word]] = []
        cluster_centers: list[float] = []
        for word in page_words:
            center = (word.y0 + word.y1) / 2
            if clusters and abs(center - cluster_centers[-1]) <= tolerance:
                clusters[-1].append(word)
                cluster_centers[-1] = sum((w.y0 + w.y1) / 2 for w in clusters[-1]) / len(
                    clusters[-1]
                )
            else:
                clusters.append([word])
                cluster_centers.append(center)

        for cluster in clusters:
            cluster.sort(key=lambda w: w.x0)
            y0 = min(w.y0 for w in cluster)
            y1 = max(w.y1 for w in cluster)
            lines.append(
                PhysicalLine(page=page, words=cluster, y0=y0, y1=y1, y_center=(y0 + y1) / 2)
            )

    return lines
