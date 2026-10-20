"""Confidence of an AI2 (IDP) fact, from evidence rather than self-report.

A fact is only as trustworthy as its two weakest links: whether its value is
actually in the quote it cites (grounding), and whether that quote was read
correctly by OCR (the cited lines' own confidence, see AI1's
``domain/ocr_confidence.py``). An LLM's self-reported confidence is not used.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Collection, Iterable
from difflib import SequenceMatcher

# Grounding: how the fact's value appears in its cited quote.
EXACT = 1.0  # verbatim (after Unicode/space/case normalisation)
SEPARATORS_ONLY = 0.95  # same once number separators are ignored (1.286.400 vs 1286400)
NEAR = 0.60  # most of the value is there, not all of it
NOT_FOUND = 0.20  # the quote does not support the value: possibly invented

NEAR_MATCH_RATIO = 0.9
# Window starts tried on each side of the anchor: absorbs a few inserted or
# dropped characters before the longest common run.
_ANCHOR_SLACK = 8
# Fact values are short; a longer one is judged on its head so matching stays
# within a few milliseconds whatever AI2 sends.
MAX_COMPARED_CHARS = 400
# Lines shorter than this ("b)", "10", "ngày") occur all over a page, so a
# text match on them says nothing about where the quote came from.
MIN_MATCH_CHARS = 12
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
    # Compare the value with quote windows of its own length, anchored on the
    # longest run they share: a scattered character overlap with a long quote
    # does not count, and only a handful of windows are ever compared.
    value = value[:MAX_COMPARED_CHARS]
    width = len(value)
    matcher = SequenceMatcher(None, value, quote, autojunk=False)
    match = matcher.find_longest_match(0, width, 0, len(quote))
    if match.size == 0:
        return NOT_FOUND
    anchor = match.b - match.a
    best = 0.0
    for start in range(anchor - _ANCHOR_SLACK, anchor + _ANCHOR_SLACK + 1):
        window = quote[max(0, start) : max(0, start) + width]
        matcher.set_seq2(window)
        if matcher.real_quick_ratio() < NEAR_MATCH_RATIO:
            continue
        if matcher.quick_ratio() < NEAR_MATCH_RATIO:
            continue
        best = max(best, matcher.ratio())
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


def cited_lines(
    quote: str,
    lines: Iterable[tuple[int, str, float | None]],
    line_nos: Collection[int] = (),
) -> list[float | None]:
    """Confidences of the page's OCR lines the quote was taken from.

    ``lines`` are ``(line_no, text, confidence)``. When the citation names its
    lines (``line_nos``) those are used; otherwise lines are matched on text,
    ignoring lines too short to identify the quote.
    """
    if line_nos:
        return [confidence for line_no, _, confidence in lines if line_no in line_nos]
    target = _norm(quote)
    if not target:
        return []
    return [
        confidence
        for _, text, confidence in lines
        if (line := _norm(text))
        and ((len(line) >= MIN_MATCH_CHARS and line in target) or target in line)
    ]
