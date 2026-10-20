"""Word-level agreement between two independent readings of the same page.

A single reader can substitute one valid word for another: mistral-ocr-2512
read "tồn tại tại thời điểm" as "tồn tại thì điểm" -- perfectly spelled, so no
spelling check can see it. A second reading exposes it, but that second reader
(mistral-ocr-4.x) garbles accents and sometimes letters ("t ur", "dans",
"hàngh"). Readings are therefore compared on accent-free skeletons, and a
disagreement only counts when the second reader's side of it is itself
plausible Vietnamese: garbage from a known-noisy reader is not evidence.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from contract_ocr.domain.vn_text import foreign_letters, is_vn_syllable, skeleton

_TOKEN = re.compile(r"[^\W_]+")


@dataclass(frozen=True)
class Token:
    text: str
    skeleton: str
    owner: int  # index of the segment/line this token came from


def tokens(text: str, owner: int = 0) -> list[Token]:
    return [
        Token(word, skeleton(word), owner)
        for word in _TOKEN.findall(unicodedata.normalize("NFC", text))
    ]


def implausible(word: str) -> bool:
    """As a *disputed* token from the noisy reader: foreign letters, or a
    lowercase/capitalized non-syllable ("dans", "ur", "hàngh", "Vietc"). A
    genuine foreign word would be read identically by both readers and never
    reach a dispute; ALL-CAPS tokens are abbreviations/codes and are left to be
    judged as real text."""
    if word.isdigit():
        return False
    if foreign_letters(word):
        return True
    if len(word) > 1 and word == word.upper():
        return False
    return not is_vn_syllable(word)


@dataclass(frozen=True)
class Dispute:
    owners: frozenset[int]  # segments of the first reading involved
    first: tuple[str, ...]
    second: tuple[str, ...]


def disputes(first: list[Token], second: list[Token]) -> list[Dispute]:
    """Spans where the two readings name different words, ignoring spans where
    the second reading's words are all implausible (it misread, not evidence)."""
    matcher = SequenceMatcher(
        None, [t.skeleton for t in first], [t.skeleton for t in second], autojunk=False
    )
    found: list[Dispute] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        theirs = second[j1:j2]
        if theirs and all(implausible(t.text) for t in theirs):
            continue
        mine = first[i1:i2]
        if mine:
            owners = frozenset(t.owner for t in mine)
        elif first:
            owners = frozenset({first[max(0, i1 - 1)].owner})
        else:
            continue
        found.append(Dispute(owners, tuple(t.text for t in mine), tuple(t.text for t in theirs)))
    return found
