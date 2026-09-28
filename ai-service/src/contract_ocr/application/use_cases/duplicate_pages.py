"""Pages that repeat an earlier page of the same document.

A scanned contract often carries one sheet twice -- fed through the scanner
twice, or re-inserted after a correction. Left alone, the repeat puts its
clauses into the structure a second time, and makes every line on it "repeat on
two pages", which the running header/footer detector must not mistake for page
furniture (running_text.py).

- Verbatim repeat (`Page.duplicate_of`): identical text once whitespace and
  markdown are normalized. The content is already in the document once, so the
  clause structure skips this page; the page itself keeps its text.
- Near repeat (`Page.near_duplicate_of`): the same digit sequence and letters
  agreeing at NEAR_DUPLICATE_RATIO. A re-scan reads slightly differently -- but
  so does a template page with only a name changed, so the page stays in the
  structure and is only flagged for review.

Pages under MIN_WORDS words are never paired: two separator pages both reading
"PHỤ LỤC" are two annex boundaries, not one sheet scanned twice.
"""

from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz

from contract_ocr.domain.entities import Document, Page
from contract_ocr.domain.enums import Status

MIN_WORDS = 20
NEAR_DUPLICATE_RATIO = 95.0

_MARKDOWN = re.compile(r"[#*_`|]+")
_DIGITS = re.compile(r"\d+")


def _text(page: Page) -> str:
    joined = "\n".join(line.text for line in page.lines)
    return " ".join(unicodedata.normalize("NFC", _MARKDOWN.sub(" ", joined)).split())


def mark_duplicate_pages(document: Document) -> None:
    """Set `duplicate_of` / `near_duplicate_of` on every successfully read page
    that repeats an earlier one, naming the earliest such page."""
    earlier: list[tuple[int, str, tuple[str, ...], str]] = []
    for page in document.pages:
        if page.status is not Status.SUCCESS:
            continue
        text = _text(page)
        if len(text.split()) < MIN_WORDS:
            continue
        digits = tuple(_DIGITS.findall(text))
        letters = _DIGITS.sub("#", text.lower())
        for number, other_text, other_digits, other_letters in earlier:
            if text == other_text:
                page.duplicate_of = number
                break
            if (
                page.near_duplicate_of is None
                and digits == other_digits
                and fuzz.ratio(letters, other_letters) >= NEAR_DUPLICATE_RATIO
            ):
                page.near_duplicate_of = number
        if page.duplicate_of is not None:
            page.near_duplicate_of = None
        else:
            earlier.append((page.page_number, text, digits, letters))
