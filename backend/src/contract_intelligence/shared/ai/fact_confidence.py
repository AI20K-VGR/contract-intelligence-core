"""Confidence of an AI2 (IDP) fact, from evidence rather than self-report.

A fact is only as trustworthy as its two weakest links: whether its value is
actually in the quote it cites (grounding), and whether that quote was read
correctly by OCR (the cited lines' own confidence, see AI1's
``domain/ocr_confidence.py``). An LLM's self-reported confidence is not used.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from difflib import SequenceMatcher

# Grounding: how the fact's value appears in its cited quote.
EXACT = 1.0  # verbatim (after Unicode/space/case normalisation)
SEPARATORS_ONLY = 0.95  # same once number separators are ignored (1.286.400 vs 1286400)
NEAR = 0.60  # most of the value is there, not all of it
NOT_FOUND = 0.20  # the quote does not support the value: possibly invented

NEAR_MATCH_RATIO = 0.9
# AI2 flagged the fact (citation not validated etc.): never auto-accepted.
NEEDS_REVIEW_CAP = 0.80

_SEPARATORS = re.compile(r"[\s.,]")


def _norm(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def grounding_score(value: str, quote: str) -> float:
    value, quote = _norm(value), _norm(quote)
    if not value or not quote:
        return NOT_FOUND
    if value in quote:
        return EXACT
    bare_value = _SEPARATORS.sub("", value)
    if bare_value and bare_value in _SEPARATORS.sub("", quote):
        return SEPARATORS_ONLY
    # Best similarity against every quote window of the value's length: a
    # scattered character overlap with a long quote does not count.
    width = len(value)
    best = max(
        SequenceMatcher(None, value, quote[start : start + width], autojunk=False).ratio()
        for start in range(max(1, len(quote) - width + 1))
    )
    return NEAR if best >= NEAR_MATCH_RATIO else NOT_FOUND


def fact_confidence(
    *,
    value: str,
    quote: str,
    review_passed: bool,
    line_confidences: Iterable[float | None] = (),
) -> float:
    score = grounding_score(value, quote)
    known = [c for c in line_confidences if c is not None]
    if known:
        score = min(score, *known)
    if not review_passed:
        score = min(score, NEEDS_REVIEW_CAP)
    return score


def cited_lines(quote: str, lines: Iterable[tuple[str, float | None]]) -> list[float | None]:
    """Confidences of the page's OCR lines the quote was taken from."""
    target = _norm(quote)
    if not target:
        return []
    return [
        confidence
        for text, confidence in lines
        if (line := _norm(text)) and (line in target or target in line)
    ]
