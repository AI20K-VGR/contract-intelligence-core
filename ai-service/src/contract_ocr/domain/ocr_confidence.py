"""Per-line text confidence from the evidence the OCR pipeline already has.

No engine in the verified path reports a usable probability (mistral-ocr-2512
returns none), so a line's confidence is the evidence behind its text: how many
independent readings agree, and which review flag the gate left on it. Each
evidence class maps to one score; a line takes the lowest class it falls in.

The scores are priors. Once a hand-corrected ground truth exists, replace each
with the measured share of correct lines in that class (Wilson lower bound), so
that 0.93 means "93% of such lines were read correctly".
"""

from __future__ import annotations

from collections.abc import Iterable

# Native PDF text: the glyphs themselves, nothing was read from pixels.
TEXT_LAYER = 0.99
# The text reader and an independent second reader agree on every token.
TWO_READERS_AGREE = 0.97
# The readers disagreed; a blind third reading settled it (2 of 3).
ARBITRATED = 0.90
# Only the text reader saw the page and the gate found nothing to doubt.
SINGLE_READER = 0.90

# Review flags left by the gate/arbiter, from least to most severe.
REVIEW_SCORES: dict[str, float] = {
    "spelling_unverified": 0.75,
    "critical_field_unverified": 0.70,
    "content_conflict": 0.50,
    "arbiter_unavailable": 0.50,
    "critical_field_conflict": 0.30,
    "amount_words_mismatch": 0.30,
}
# A flag this module does not know is still a doubt, never a pass.
UNKNOWN_REVIEW = 0.50


def line_text_confidence(
    *, verified: bool, arbitrated: bool, review: Iterable[str]
) -> float:
    """Confidence that a scanned line's text was read correctly."""
    base = ARBITRATED if arbitrated else TWO_READERS_AGREE if verified else SINGLE_READER
    return min([base, *(REVIEW_SCORES.get(reason, UNKNOWN_REVIEW) for reason in review)])
