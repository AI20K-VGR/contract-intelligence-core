"""Deterministic checks for whether an OCR reading of Vietnamese text looks right.

Built from a measured failure: `mistral-ocr-4` read a clean 150-DPI page as
"Két qua bàn giao phai dam bao khà nang truy vét t ur du lieu..." with block
confidence up to 0.99 on individual wrong words, so a model's own confidence
cannot gate diacritics. What the garbled text does show, and correct text does
not, is a low share of accented syllables (0.27-0.36 vs 0.75-0.88 on that page),
letters that do not exist in Vietnamese ("dū", "uŋ", "tαi", "diēm"), syllables
Vietnamese phonotactics cannot produce ("dans", "ur", "hàngh"), and diphthongs
missing their obligatory circumflex/horn ("kiém", "nghiem", "tuong" -- before a
final consonant, "iê/yê/uô/ươ" are never written without it).
"""

from __future__ import annotations

import re
import unicodedata

_MARKED = "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
_VN_LETTERS = frozenset("abcdefghijklmnopqrstuvwxyz" + _MARKED)
_MARKED_SET = frozenset(_MARKED)
_WORD = re.compile(r"[^\W\d_]+")
_EMAIL_OR_URL = re.compile(r"\S+@\S+|https?://\S+|www\.\S+")
_CIRCUMFLEX, _HORN, _BREVE = "̂", "̛", "̆"
_SYLLABLE = re.compile(
    r"^(?:ngh|ng|nh|ch|gh|gi|kh|ph|qu|th|tr|[bcdghklmnpqrstvx])?[aeiouy]{1,3}(?:ng|nh|ch|[cmnpt])?$"
)
_ENGLISH_STOPWORDS = frozenset(
    "the of and to in for is on with by as at from this that be are or an it not "
    "shall will any all such party parties agreement".split()
)

MIN_WORDS_FOR_DENSITY = 8
MIN_DIACRITIC_DENSITY = 0.5
MIN_INVALID_SYLLABLES = 2
MAX_INVALID_SYLLABLE_RATIO = 0.25
MIN_MISSING_MODIFIERS = 2


def skeleton(text: str) -> str:
    """Lowercase, diacritic-free, whitespace-collapsed form: two readings that
    differ only in accents share a skeleton."""
    decomposed = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(stripped.lower().split())


def char_skeleton(text: str) -> str:
    """Per-character skeleton of NFC `text`, same length as it, so an index found
    by matching skeletons is also an index into the original text."""
    out = []
    for ch in unicodedata.normalize("NFC", text):
        base = "d" if ch in "đĐ" else unicodedata.normalize("NFD", ch)[0]
        out.append(base.lower() if len(base.lower()) == 1 else base)
    return "".join(out)


def _words(text: str) -> list[str]:
    return [w for w in _WORD.findall(unicodedata.normalize("NFC", text.lower())) if len(w) >= 2]


def _lowercase_words(text: str) -> list[str]:
    """Words written in lowercase in the source, emails/URLs removed: an
    uppercase token is an abbreviation or code ("TNHH", "MST", "HĐDV"), not a
    syllable a phonotactic check can judge."""
    cleaned = _EMAIL_OR_URL.sub(" ", unicodedata.normalize("NFC", text))
    return [w for w in _WORD.findall(cleaned) if len(w) >= 2 and w == w.lower()]


def _vowel_quality(ch: str) -> str:
    """Base letter plus circumflex/horn/breve, tone dropped: "ế" -> "ê", "é" -> "e"."""
    decomposed = unicodedata.normalize("NFD", ch)
    base = decomposed[0]
    modifiers = "".join(m for m in decomposed[1:] if m in (_CIRCUMFLEX, _HORN, _BREVE))
    return unicodedata.normalize("NFC", base + modifiers)


def missing_vowel_modifier(word: str) -> bool:
    """True for "iê/yê/uô" diphthongs written without their circumflex before
    another letter ("kiém", "nghiem", "tuong") -- impossible in correct spelling."""
    letters = [_vowel_quality(ch) for ch in unicodedata.normalize("NFC", word.lower())]
    for i in range(len(letters) - 2):
        pair = letters[i] + letters[i + 1]
        if pair in ("ie", "ye", "uo") and not (i > 0 and letters[i - 1] == "q"):
            return True
    return False


def foreign_letters(text: str) -> set[str]:
    return {
        ch
        for ch in unicodedata.normalize("NFC", text.lower())
        if ch.isalpha() and ch not in _VN_LETTERS
    }


def is_vn_syllable(word: str) -> bool:
    return bool(_SYLLABLE.match(skeleton(word)))


def diacritic_density(text: str) -> float | None:
    """Share of valid Vietnamese syllables that carry an accent, or None when the
    text has too few of them to judge (short lines, English, codes, numbers)."""
    syllables = [w for w in _words(text) if is_vn_syllable(w)]
    if len(syllables) < MIN_WORDS_FOR_DENSITY:
        return None
    return sum(1 for w in syllables if any(ch in _MARKED_SET for ch in w)) / len(syllables)


def _mostly_english(words: list[str]) -> bool:
    if not words or any(any(ch in _MARKED_SET for ch in w) for w in words):
        return False
    return sum(1 for w in words if w in _ENGLISH_STOPWORDS) / len(words) >= 0.15


def line_issues(text: str) -> list[str]:
    """Reason codes for a line whose reading is suspect; empty means no evidence
    of a bad reading (not proof of a good one)."""
    issues: list[str] = []
    if foreign_letters(text):
        issues.append("FOREIGN_LETTERS")
    words = _words(text)
    if _mostly_english(words):
        return issues
    density = diacritic_density(text)
    if density is not None and density < MIN_DIACRITIC_DENSITY:
        issues.append("LOW_DIACRITIC_DENSITY")
    lowercase = _lowercase_words(text)
    if sum(1 for w in lowercase if missing_vowel_modifier(w)) >= MIN_MISSING_MODIFIERS:
        issues.append("MISSING_VOWEL_MODIFIER")
    # Only syllables that cannot be a foreign word or name count: an accented
    # token ("hàngh") never is, and neither is a 2-3 letter lowercase fragment
    # ("ur"). A long unaccented token ("email", "watermark") is left alone.
    invalid = [
        w
        for w in lowercase
        if not is_vn_syllable(w) and (len(w) <= 3 or any(ch in _MARKED_SET for ch in w))
    ]
    if (
        len(invalid) >= MIN_INVALID_SYLLABLES
        and len(invalid) / max(1, len(lowercase)) >= MAX_INVALID_SYLLABLE_RATIO
    ):
        issues.append("INVALID_SYLLABLES")
    return issues
