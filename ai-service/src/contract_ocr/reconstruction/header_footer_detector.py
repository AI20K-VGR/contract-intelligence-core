"""Detect running headers/footers, page numbers and watermarks.

These blocks must never leak into clause text, but raw OCR is immutable —
so this module only *classifies*, it never deletes anything (section 12).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from .config import HEADER_FOOTER_MIN_REPEAT_RATIO, HEADER_FOOTER_POSITION_BAND
from .models import (
    Action,
    EntityType,
    ReasonCode,
    ReconstructionAction,
    ResolutionMethod,
    SourceBlockRef,
)
from .schemas.block import FIGURE, FOOTER, HEADER, PAGE_NUMBER, TABLE_ROW, WATERMARK, Block
from .schemas.page import Page

_DIGIT_RE = re.compile(r"\d+")
_PAGE_NUMBER_RE = re.compile(r"^(?:page\s*)?-?\s*\d+\s*(?:(?:of|/)\s*\d+)?\s*-?$", re.IGNORECASE)


def _normalize_for_repeat_matching(text: str) -> str:
    """Collapse whitespace and mask digits so "Page 12 of 100" on every page
    is recognized as the same recurring pattern regardless of page number."""
    collapsed = " ".join(text.strip().split())
    return _DIGIT_RE.sub("#", collapsed).lower()


def _band(block: Block, page: Page) -> str | None:
    top_edge = HEADER_FOOTER_POSITION_BAND * page.height
    bottom_edge = (1 - HEADER_FOOTER_POSITION_BAND) * page.height
    if block.y1 <= top_edge:
        return "top"
    if block.y0 >= bottom_edge:
        return "bottom"
    return None


@dataclass(frozen=True)
class _Pattern:
    band: str
    normalized: str


class HeaderFooterProfile:
    """Answers "is this block a header/footer/page-number?" for one document."""

    def __init__(self, recurring_patterns: frozenset[_Pattern]) -> None:
        self._recurring = recurring_patterns

    def classify(self, block: Block, page: Page) -> tuple[bool, bool]:
        """Return (is_header, is_footer) for a block on a given page."""
        if block.type in (HEADER, WATERMARK):
            return True, False
        if block.type == FOOTER:
            return False, True
        if block.type == PAGE_NUMBER:
            band = _band(block, page)
            return band == "top", band != "top"

        band = _band(block, page)
        if band is None:
            return False, False

        if block.type == TABLE_ROW:
            # A table header row legitimately repeats at the top of every
            # page it spans — that repetition is handled by `table_merger`
            # (section 11), not by generic running-header detection.
            return False, False

        if _PAGE_NUMBER_RE.match(block.text.strip()):
            return band == "top", band == "bottom"

        normalized = _normalize_for_repeat_matching(block.text)
        if not normalized:
            return False, False
        for pattern in self._recurring:
            if pattern.band != band:
                continue
            if normalized == pattern.normalized or fuzz.ratio(normalized, pattern.normalized) >= (
                90.0
            ):
                return band == "top", band == "bottom"
        return False, False

    def is_noise(self, block: Block, page: Page) -> bool:
        """True if the block should be excluded from clause/table text and
        from boundary-detection candidates: headers, footers, page numbers,
        watermarks, figures, or blocks with no text."""
        if block.is_empty:
            return True
        if block.type in (FIGURE,):
            return True
        is_header, is_footer = self.classify(block, page)
        return is_header or is_footer

    def action_for(self, block: Block, page: Page) -> ReconstructionAction | None:
        """The explicit `IGNORE_HEADER`/`IGNORE_FOOTER` action for a block
        classified as a running header/footer (section 9), or `None` if it
        isn't one. Confidence is high because classification itself already
        required the text to repeat across multiple pages — section 9 is
        explicit that position on a single page is never enough evidence.
        """
        is_header, is_footer = self.classify(block, page)
        if not is_header and not is_footer:
            return None
        return ReconstructionAction(
            action=Action.IGNORE_HEADER if is_header else Action.IGNORE_FOOTER,
            relationship=None,
            entity_type=EntityType.HEADER if is_header else EntityType.FOOTER,
            source_blocks=[SourceBlockRef(page=page.page, block_id=block.block_id)],
            reason_codes=[ReasonCode.REPEATED_HEADER if is_header else ReasonCode.REPEATED_FOOTER],
            confidence=0.97,
            requires_review=False,
            method=ResolutionMethod.RULE,
        )


def detect_header_footer(
    pages: list[Page], min_repeat_ratio: float = HEADER_FOOTER_MIN_REPEAT_RATIO
) -> HeaderFooterProfile:
    """Scan every page once to learn which (band, normalized-text) patterns
    repeat often enough across the document to count as a running
    header/footer, then return a profile that classifies individual blocks."""
    total_pages = len(pages)
    seen_per_pattern: dict[_Pattern, set[int]] = {}

    for page in pages:
        for block in page.meaningful_blocks:
            if block.type == TABLE_ROW:
                continue
            band = _band(block, page)
            if band is None:
                continue
            normalized = _normalize_for_repeat_matching(block.text)
            if not normalized:
                continue
            pattern = _Pattern(band=band, normalized=normalized)
            seen_per_pattern.setdefault(pattern, set()).add(page.page)

    recurring: set[_Pattern] = set()
    if total_pages > 1:
        for pattern, page_numbers in seen_per_pattern.items():
            if len(page_numbers) / total_pages >= min_repeat_ratio:
                recurring.add(pattern)

    return HeaderFooterProfile(frozenset(recurring))
