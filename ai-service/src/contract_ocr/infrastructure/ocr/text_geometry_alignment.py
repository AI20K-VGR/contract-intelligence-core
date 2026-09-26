"""Assign transcribed text segments to measured visual-line boxes.

`mistral-ocr-2512` returns paragraph-level markdown lines (one logical line may
wrap over several visual lines) with no coordinates; `line_geometry` returns
visual-line boxes with no text. Both are in reading order, so the match is a
monotonic alignment: each segment takes a contiguous run of boxes whose total
width, at the page's own characters-per-pixel rate, best explains its length.

Boxes may be skipped (ink the transcription never covered -- a possible
omission) and segments may get no box (text with no ink behind it -- a possible
hallucination); both are penalised and reported, never hidden.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from contract_ocr.infrastructure.image.line_geometry import LineBox

MAX_RUN = 16
# A segment whose length is explained this badly by its boxes is not trusted
# as a citation anchor.
POOR_ALIGNMENT_ERROR = 0.35
# Skipped ink / box-less text shorter than this (in characters) is noise.
MIN_SIGNIFICANT_CHARS = 15
# Skipping a box / leaving a segment box-less is a rare event (a transcriber
# dropping or inventing a whole line), priced as a near-constant penalty rather
# than per character, so the solver admits it instead of shifting every
# neighbouring segment onto the wrong box to hide it.
_SKIP_PENALTY = 4.0
_EMPTY_PENALTY = 5.0
_PER_CHAR_PENALTY = 0.02
_GAP_PENALTY = 6.0
# Expected relative spread between a segment's length and its boxes' width
# (font weight, spacing, justification). Mismatch cost is quadratic in units of
# this spread, so a large mismatch costs more than admitting skipped ink.
_LENGTH_SPREAD = 0.12
# The page-wide chars-per-pixel estimate is biased by exactly the anomalies we
# want to detect (an omitted line lowers it, a hallucinated one raises it), so
# alignment is solved for a range of rates around it and the cheapest wins.
_RATE_FACTORS = (0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.35, 1.5)
# Per box placed outside the region an independent reading located this
# segment in: length alone cannot tell apart runs of similar-length lines or
# two columns, content can.
_ANCHOR_PENALTY = 25.0

Anchor = tuple[float, float, float, float]  # x0, y0, x1, y1 in the boxes' pixel space


@dataclass
class SegmentMatch:
    box_indices: list[int]
    relative_error: float

    @property
    def matched(self) -> bool:
        return bool(self.box_indices)

    @property
    def poor(self) -> bool:
        return not self.box_indices or self.relative_error > POOR_ALIGNMENT_ERROR


@dataclass
class Alignment:
    segments: list[SegmentMatch]
    unmatched_boxes: list[int]
    chars_per_pixel: float
    unread_ink: list[int] = field(default_factory=list)
    text_without_ink: list[int] = field(default_factory=list)
    cost: float = 0.0


def _char_count(text: str) -> int:
    return len(" ".join(text.split()))


def align(
    texts: list[str], boxes: list[LineBox], anchors: list[Anchor | None] | None = None
) -> Alignment:
    """`anchors[i]`, when given, is a region where an independent reading of
    the page placed text `i`; boxes outside it (by their centre, with one line
    height of tolerance) are penalised for that segment."""
    m, n = len(texts), len(boxes)
    chars = [_char_count(t) for t in texts]
    widths = [b.width for b in boxes]
    total_width = sum(widths)
    k = sum(chars) / total_width if total_width else 0.0
    if m == 0 or n == 0 or k == 0:
        return Alignment(
            segments=[SegmentMatch([], 1.0) for _ in texts],
            unmatched_boxes=list(range(n)),
            chars_per_pixel=k,
            unread_ink=[j for j in range(n) if widths[j] * k >= MIN_SIGNIFICANT_CHARS],
            text_without_ink=[i for i in range(m) if chars[i] >= MIN_SIGNIFICANT_CHARS],
        )

    line_height = sorted(b.height for b in boxes)[n // 2]
    prefix = [0.0]
    for w in widths:
        prefix.append(prefix[-1] + w)
    # A paragraph's visual lines are stacked directly under one another. Box j
    # breaks from box j-1 when it sits far beside it (another column on the
    # same row), above it (the jump to the top of the next column), or far
    # below it (a new block).
    gap_prefix = [0, 0]
    for j in range(1, n):
        previous, current = boxes[j - 1], boxes[j]
        same_row = min(previous.y1, current.y1) - max(previous.y0, current.y0) > 0
        horizontal_gap = max(previous.x0, current.x0) - min(previous.x1, current.x1)
        broken = (
            (same_row and horizontal_gap > 4.0 * line_height)
            or (not same_row and current.y1 <= previous.y0)
            or current.y0 - previous.y1 > 2.0 * line_height
        )
        gap_prefix.append(gap_prefix[-1] + int(broken))

    # outside_prefix[i][j]: boxes among the first j lying outside anchor i.
    outside_prefix: list[list[int] | None] = []
    for anchor in anchors or [None] * m:
        if anchor is None:
            outside_prefix.append(None)
            continue
        x0, y0, x1, y1 = anchor
        row = [0]
        for box in boxes:
            cx, cy = (box.x0 + box.x1) / 2, box.center_y
            inside = x0 - line_height <= cx <= x1 + line_height and (
                y0 - line_height <= cy <= y1 + line_height
            )
            row.append(row[-1] + int(not inside))
        outside_prefix.append(row)

    solutions = [
        _solve(chars, widths, prefix, gap_prefix, k * f, outside_prefix) for f in _RATE_FACTORS
    ]
    best_cost, rate, segments, unmatched = min(solutions, key=lambda s: s[0])
    return Alignment(
        segments=segments,
        unmatched_boxes=unmatched,
        chars_per_pixel=rate,
        cost=best_cost,
        unread_ink=[b for b in unmatched if widths[b] * rate >= MIN_SIGNIFICANT_CHARS],
        text_without_ink=[
            idx for idx, s in enumerate(segments) if not s.matched and chars[idx] >= MIN_SIGNIFICANT_CHARS
        ],
    )


def _solve(
    chars: list[int],
    widths: list[int],
    prefix: list[float],
    gap_prefix: list[int],
    k: float,
    outside_prefix: list[list[int] | None],
) -> tuple[float, float, list[SegmentMatch], list[int]]:
    m, n = len(chars), len(widths)

    def run_gaps(start: int, end: int) -> int:
        """Vertical breaks inside a run: a paragraph's lines are adjacent."""
        return gap_prefix[end] - gap_prefix[start + 1] if end - start > 1 else 0

    def assign_cost(i: int, start: int, end: int) -> float:
        estimate = k * (prefix[end] - prefix[start])
        spread = _LENGTH_SPREAD * max(chars[i], estimate, 10.0)
        outside = outside_prefix[i]
        anchor_cost = _ANCHOR_PENALTY * (outside[end] - outside[start]) if outside else 0.0
        return (
            0.5 * ((chars[i] - estimate) / spread) ** 2
            + _GAP_PENALTY * run_gaps(start, end)
            + anchor_cost
        )

    def skip_cost(j: int) -> float:
        return _SKIP_PENALTY + _PER_CHAR_PENALTY * k * widths[j]

    def empty_cost(i: int) -> float:
        return _EMPTY_PENALTY + _PER_CHAR_PENALTY * chars[i]

    inf = float("inf")
    cost = [[inf] * (n + 1) for _ in range(m + 1)]
    back: list[list[tuple[str, int] | None]] = [[None] * (n + 1) for _ in range(m + 1)]
    cost[0][0] = 0.0
    for i in range(m + 1):
        for j in range(n + 1):
            if i == 0 and j == 0:
                continue
            best, move = inf, None
            if j > 0 and cost[i][j - 1] + skip_cost(j - 1) < best:
                best, move = cost[i][j - 1] + skip_cost(j - 1), ("skip", j - 1)
            if i > 0:
                if cost[i - 1][j] + empty_cost(i - 1) < best:
                    best, move = cost[i - 1][j] + empty_cost(i - 1), ("empty", j)
                for start in range(max(0, j - MAX_RUN), j):
                    candidate = cost[i - 1][start] + assign_cost(i - 1, start, j)
                    if candidate < best:
                        best, move = candidate, ("assign", start)
            cost[i][j], back[i][j] = best, move

    segments: list[SegmentMatch] = [SegmentMatch([], 1.0) for _ in range(m)]
    unmatched: list[int] = []
    i, j = m, n
    while i > 0 or j > 0:
        kind, value = back[i][j]
        if kind == "skip":
            unmatched.append(value)
            j -= 1
        elif kind == "empty":
            i -= 1
        else:
            estimate = k * (prefix[j] - prefix[value])
            error = abs(chars[i - 1] - estimate) / max(chars[i - 1], estimate, 1.0)
            segments[i - 1] = SegmentMatch(list(range(value, j)), error)
            i, j = i - 1, value
    unmatched.reverse()
    return cost[m][n], k, segments, unmatched
