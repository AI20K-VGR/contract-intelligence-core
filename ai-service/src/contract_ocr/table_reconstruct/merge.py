"""Decide whether two table fragments are one logical table split by a page break."""

from __future__ import annotations

import re
from collections.abc import Sequence

from .columns import (
    _looks_like_anchor_value,
    _normalize_confusables,
    _row_is_header,
    column_signature,
    detect_column_bounds,
    pick_anchor_column,
    slice_lines,
)
from .config import Config
from .lines import group_physical_lines
from .types import Fragment, PhysicalLine, SlicedLine


def should_merge(
    frag_a: Fragment, frag_b: Fragment, config: Config = Config()
) -> tuple[bool, int, list[str]]:
    """Score whether `frag_b` continues `frag_a` across a page break.

    Hard gates (any one makes this `False` immediately, score 0):
      - different `doc_id`
      - either fragment has no content
      - the anchor column resets to 1 in `frag_b` (a new, unrelated table)
      - a ĐIỀU/PHỤ LỤC/BIỂU heading sits between the two fragments

    Otherwise each corroborating signal adds its configured weight
    (`config.scoring`); the fragments merge once the total reaches
    `config.scoring.merge_threshold`. Returns `(should_merge, score,
    reasons)` so the decision can be logged.
    """
    if frag_a.doc_id != frag_b.doc_id:
        return False, 0, ["different doc_id"]

    lines_a = group_physical_lines(frag_a.words, config)
    lines_b = group_physical_lines(frag_b.words, config)
    if not lines_a or not lines_b:
        return False, 0, ["fragment has no content"]

    bounds_a = detect_column_bounds(lines_a, config)
    bounds_b = detect_column_bounds(lines_b, config)
    sliced_a = slice_lines(lines_a, bounds_a)
    sliced_b = slice_lines(lines_b, bounds_b)

    preview_a = [[c.text for c in row.columns] for row in sliced_a]
    anchor_col = pick_anchor_column(preview_a, config)

    first_anchor_b = _first_numeric_anchor(sliced_b, anchor_col, config)
    if first_anchor_b == 1:
        return False, 0, ["anchor column resets to 1"]

    if _has_heading_barrier(sliced_a, sliced_b, config):
        return False, 0, ["heading barrier (ĐIỀU/PHỤ LỤC/BIỂU) between fragments"]

    weights = config.scoring
    score = 0
    reasons: list[str] = []

    page_width_a = frag_a.bbox[2] - frag_a.bbox[0]
    page_width_b = frag_b.bbox[2] - frag_b.bbox[0]
    if (
        page_width_a > 0
        and page_width_b > 0
        and _signatures_match(
            column_signature(bounds_a, page_width_a, config),
            column_signature(bounds_b, page_width_b, config),
            config,
        )
    ):
        score += weights.column_signature_match
        reasons.append(f"+{weights.column_signature_match} column signatures match")

    last_anchor_a = _last_numeric_anchor(sliced_a, anchor_col, config)
    if last_anchor_a is not None and first_anchor_b == last_anchor_a + 1:
        score += weights.anchor_continuous
        reasons.append(f"+{weights.anchor_continuous} anchor column continuous")

    if not _row_is_header([c.text for c in sliced_b[0].columns], anchor_col, config):
        score += weights.no_header_in_next_fragment
        reasons.append(f"+{weights.no_header_in_next_fragment} next fragment has no header row")

    if _has_continued_marker(sliced_a, sliced_b, config):
        score += weights.continued_marker_present
        reasons.append(f"+{weights.continued_marker_present} continuation marker present")

    if _ends_near_bottom(frag_a, lines_a, config):
        score += weights.prev_fragment_ends_near_bottom
        reasons.append(
            f"+{weights.prev_fragment_ends_near_bottom} previous fragment ends near bbox bottom"
        )

    if _starts_near_top(frag_b, lines_b, config):
        score += weights.next_fragment_starts_near_top
        reasons.append(f"+{weights.next_fragment_starts_near_top} next fragment starts near bbox top")

    return score >= weights.merge_threshold, score, reasons


def _numeric_anchor(text: str, config: Config) -> int | None:
    normalized = _normalize_confusables(text.strip(), config)
    return int(normalized) if _looks_like_anchor_value(normalized) else None


def _first_numeric_anchor(rows: Sequence[SlicedLine], anchor_col: int, config: Config) -> int | None:
    for row in rows:
        if anchor_col < len(row.columns):
            value = _numeric_anchor(row.columns[anchor_col].text, config)
            if value is not None:
                return value
    return None


def _last_numeric_anchor(rows: Sequence[SlicedLine], anchor_col: int, config: Config) -> int | None:
    for row in reversed(rows):
        if anchor_col < len(row.columns):
            value = _numeric_anchor(row.columns[anchor_col].text, config)
            if value is not None:
                return value
    return None


def _signatures_match(sig_a: Sequence[float], sig_b: Sequence[float], config: Config) -> bool:
    if len(sig_a) != len(sig_b):
        return False
    return all(abs(a - b) < config.column_signature_edge_tolerance for a, b in zip(sig_a, sig_b))


def _has_continued_marker(
    sliced_a: Sequence[SlicedLine], sliced_b: Sequence[SlicedLine], config: Config
) -> bool:
    edge_text = " ".join(c.text for c in sliced_a[-1].columns) + " " + " ".join(
        c.text for c in sliced_b[0].columns
    )
    lowered = edge_text.lower()
    return any(marker.lower() in lowered for marker in config.continued_markers)


def _has_heading_barrier(
    sliced_a: Sequence[SlicedLine], sliced_b: Sequence[SlicedLine], config: Config
) -> bool:
    pattern = re.compile(config.heading_barrier_pattern, re.IGNORECASE)
    edge_texts = [
        " ".join(c.text for c in sliced_a[-1].columns).strip(),
        " ".join(c.text for c in sliced_b[0].columns).strip(),
    ]
    return any(pattern.search(t) for t in edge_texts if t)


def _ends_near_bottom(frag: Fragment, lines: Sequence[PhysicalLine], config: Config) -> bool:
    _, top, _, bottom = frag.bbox
    height = bottom - top
    if height <= 0 or not lines:
        return False
    return (bottom - lines[-1].y1) <= config.edge_band_ratio * height


def _starts_near_top(frag: Fragment, lines: Sequence[PhysicalLine], config: Config) -> bool:
    _, top, _, bottom = frag.bbox
    height = bottom - top
    if height <= 0 or not lines:
        return False
    return (lines[0].y0 - top) <= config.edge_band_ratio * height
