"""Deterministic, code-only text merging (section 10).

Never rewrites spelling, grammar, legal wording, numbers, dates, currency or
party names. The only transformation ever applied is joining two fragments
with a single space, or — only under a strict, narrow condition — dropping a
line-break hyphen that clearly split one word across a page break.
"""

from __future__ import annotations

import re

from .models import SourceBlockRef
from .provenance import TextFragment

_HYPHENS = ("-", "‐", "­")  # hyphen, hyphen (unicode), soft hyphen
_WORD_CHAR_RE = re.compile(r"[^\W\d_]", re.UNICODE)


def _last_word(text: str) -> str:
    return re.split(r"\s+", text.strip())[-1] if text.strip() else ""


def is_hyphenated_break(previous_text: str, next_text: str) -> bool:
    """True only when `previous_text` ends in a hyphen that clearly split a
    single word across the page break, and it is safe to drop it.

    Requires: the hyphen is attached directly to a real word (>= 2 letters
    before it, no preceding whitespace — ruling out list-marker "-" bullets),
    and the next fragment starts with a lowercase letter continuing that
    word (ruling out a hyphen that was just end-of-sentence punctuation).
    """
    prev_stripped = previous_text.rstrip()
    if not prev_stripped or prev_stripped[-1] not in _HYPHENS:
        return False
    word_before = _last_word(prev_stripped[:-1])
    if len(word_before) < 2 or not _WORD_CHAR_RE.search(word_before):
        return False
    next_stripped = next_text.lstrip()
    if not next_stripped:
        return False
    first_char = next_stripped[0]
    return first_char.isalpha() and first_char.islower()


def merge_texts(previous_text: str, next_text: str) -> str:
    """Join two raw OCR fragments with no rewriting of their content."""
    prev_stripped = previous_text.rstrip()
    next_stripped = next_text.lstrip()
    if is_hyphenated_break(previous_text, next_text):
        return prev_stripped[:-1] + next_stripped
    if not prev_stripped:
        return next_stripped
    if not next_stripped:
        return prev_stripped
    return prev_stripped + " " + next_stripped


def extend_merge(
    text: str, refs: list[SourceBlockRef], fragment: TextFragment
) -> tuple[str, list[SourceBlockRef]]:
    """Append one more fragment onto an in-progress merge.

    This is the single step `merge_fragments` repeats; it is exposed on its
    own so a paragraph that keeps continuing across three or more pages can
    be extended one page-boundary at a time (each extension sees the
    already-merged text so far, not just the immediately previous block).
    """
    if not refs:
        merged = fragment.text.strip()
        return merged, [
            SourceBlockRef(page=fragment.page, block_id=fragment.block_id, char_start=0, char_end=len(merged))
        ]

    hyphenated = is_hyphenated_break(text, fragment.text)
    merged = merge_texts(text, fragment.text)
    appended_len = len(fragment.text.lstrip())
    next_start = len(merged) - appended_len

    new_refs = list(refs)
    if hyphenated:
        previous = new_refs[-1]
        new_refs[-1] = previous.model_copy(update={"char_end": previous.char_end - 1})
    new_refs.append(
        SourceBlockRef(
            page=fragment.page, block_id=fragment.block_id, char_start=next_start, char_end=len(merged)
        )
    )
    return merged, new_refs


def merge_fragments(fragments: list[TextFragment]) -> tuple[str, list[SourceBlockRef]]:
    """Merge fragments in order, returning the merged text plus a
    `SourceBlockRef` per fragment carrying its exact `char_start`/`char_end`
    span inside the merged text.
    """
    text = ""
    refs: list[SourceBlockRef] = []
    for fragment in fragments:
        text, refs = extend_merge(text, refs, fragment)
    return text, refs
