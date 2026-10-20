"""Tunable thresholds and weights for reconstruction-action confidence.

Kept in one place, deliberately free of business logic, so the scoring
strategy can be tuned without touching the rule engine, LLM resolver or
pipeline code.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .models import ScoreBreakdown


class ConfidenceWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule: float = 0.30
    layout: float = 0.25
    numbering: float = 0.25
    text_continuity: float = 0.10
    model: float = 0.10


DEFAULT_WEIGHTS = ConfidenceWeights()

# Confidence-band interpretation (agent spec section 13). The four
# deterministic signals (everything but `model`) sum to a weight of 0.90,
# so a rule-only match tops out at 0.90 — squarely in the "strong" band —
# and only an LLM call can push a boundary into "very strong" territory.
VERY_STRONG_THRESHOLD = 0.95
STRONG_THRESHOLD = 0.85
AMBIGUOUS_THRESHOLD = 0.70

# `requires_review` is false once a score reaches "strong" (0.85+). Below
# that ("ambiguous" or "insufficient"), section 13 is explicit: prefer
# NEEDS_REVIEW over guessing.
AUTO_ACCEPT_THRESHOLD = STRONG_THRESHOLD

# Boundary detector: how many trailing/leading meaningful blocks to consider.
BOUNDARY_WINDOW = 3

# Header/footer detector: a block counts as a repeating header/footer once
# its normalized text recurs on at least this fraction of pages within the
# same vertical band. Section 9 requires evidence across *several* pages —
# never classify from a single page's position alone.
HEADER_FOOTER_MIN_REPEAT_RATIO = 0.6

# Fraction of page height counted as the "top band" / "bottom band" for
# header/footer position matching.
HEADER_FOOTER_POSITION_BAND = 0.12

# rapidfuzz ratio (0-100) above which two header/footer candidate strings
# are considered the same recurring text after digit-normalization.
HEADER_FOOTER_TEXT_SIMILARITY = 90.0

# rapidfuzz ratio (0-100) above which two table header rows are considered
# a repeat of the same header.
TABLE_HEADER_SIMILARITY = 85.0


def compute_final_confidence(
    scores: ScoreBreakdown, weights: ConfidenceWeights = DEFAULT_WEIGHTS
) -> float:
    """Blend independent signals into one final confidence score.

    Never trusts a single signal — in particular, never trusts the agent's
    own self-reported confidence alone (section 13).
    """
    final = (
        weights.rule * scores.rule_score
        + weights.layout * scores.layout_score
        + weights.numbering * scores.numbering_score
        + weights.text_continuity * scores.text_continuity_score
        + weights.model * scores.model_score
    )
    return max(0.0, min(1.0, final))


def is_confident(final_score: float) -> bool:
    """True once a score is "strong" or better (section 13) — confident
    enough to act without flagging for human review. Used both to decide
    whether the rule engine alone is enough (skip the LLM call) and whether
    a blended rule+LLM score is enough to avoid `NEEDS_REVIEW`."""
    return final_score >= STRONG_THRESHOLD
