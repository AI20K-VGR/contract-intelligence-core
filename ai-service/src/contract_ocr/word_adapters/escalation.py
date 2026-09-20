"""Escalation policy from `OcrAdapter` to `VisionAdapter`.

`OcrAdapter` always runs first. A specific cell or region only gets
re-read by `VisionAdapter` when either:
  - its OCR text's dictionary-shaped valid-word ratio falls below a
    threshold (`should_escalate_for_words`), or
  - `table_reconstruct.validate()` reports a checksum mismatch —
    `sum_check` or `vn_words_check` failing — for the table it belongs to
    (`should_escalate_for_checks`).

Escalation always targets one cell or one small region, never a whole
page (the caller decides that scope — this controller only decides
whether and how many times), and is hard-capped at
`max_escalations_per_page` per page.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contract_ocr.table_reconstruct.types import Word

from .text_quality import valid_word_ratio
from .types import Region
from .vision import VisionAdapter

DEFAULT_MIN_VALID_WORD_RATIO = 0.6
DEFAULT_MAX_ESCALATIONS_PER_PAGE = 2

# The `table_reconstruct.validate()` checks that represent a numeric
# cross-check ("checksum") worth escalating over. Structural checks
# (row_count_ok, anchor_continuous, arity_ok) aren't included here — no
# cell-level vision re-read can fix a missing row or wrong column count.
CHECKSUM_CHECKS = ("sum_check", "vn_words_check")


@dataclass
class EscalationResult:
    words: list[Word]
    escalated: bool
    reason: str | None = None


class EscalationController:
    def __init__(
        self,
        vision_adapter: VisionAdapter | None = None,
        *,
        min_valid_word_ratio: float = DEFAULT_MIN_VALID_WORD_RATIO,
        max_escalations_per_page: int = DEFAULT_MAX_ESCALATIONS_PER_PAGE,
    ) -> None:
        self._vision = vision_adapter or VisionAdapter(mode="cells")
        self._min_valid_word_ratio = min_valid_word_ratio
        self._max_per_page = max_escalations_per_page
        self._escalations_used: dict[int, int] = {}

    def escalations_used(self, page: int) -> int:
        return self._escalations_used.get(page, 0)

    def should_escalate_for_words(self, words: list[Word]) -> bool:
        return valid_word_ratio([w.text for w in words]) < self._min_valid_word_ratio

    def should_escalate_for_checks(self, checks: dict[str, Any]) -> bool:
        return any(not checks.get(name, {}).get("passed", True) for name in CHECKSUM_CHECKS)

    def escalate(self, image: Any, region: Region) -> EscalationResult:
        """Re-read `region` (one cell or one small region) with the vision
        adapter, provided this page hasn't hit `max_escalations_per_page`
        yet. Blocked escalations return the original (empty) word list
        rather than silently retrying or falling through to a page-level
        re-read.
        """
        used = self._escalations_used.get(region.page, 0)
        if used >= self._max_per_page:
            return EscalationResult(words=[], escalated=False, reason="escalation_cap_reached")

        words = self._vision.extract(image, region)
        self._escalations_used[region.page] = used + 1
        return EscalationResult(words=words, escalated=True, reason=None)
