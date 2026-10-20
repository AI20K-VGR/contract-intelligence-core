"""Character/word-level text-quality heuristics.

Used both to route a page between `NativeAdapter`/`OcrAdapter`
(`routing.choose_adapter`) and to decide when `OcrAdapter` output is
untrustworthy enough to escalate to `VisionAdapter`
(`escalation.EscalationController`).

No Vietnamese dictionary/word-list is bundled with this codebase (there
isn't one anywhere else in it to reuse either — see the survey in this
package's design notes). `valid_word_ratio` therefore uses a syllable-SHAPE
heuristic instead of a real lookup: a token counts as "valid" when it's
composed entirely of Vietnamese letters (with diacritics), digits, and a
small set of in-word punctuation. This catches OCR garbage — mojibake,
TCVN3/VNI legacy-encoding artifacts, stray symbol runs — without needing a
bundled word list, at the cost of not catching a real-word-but-wrong-word
misread; that class of error is exactly what `table_reconstruct.validate`'s
checksum checks exist to catch instead.
"""

from __future__ import annotations

import re
import unicodedata

_VOWELS = "aàáảãạăằắẳẵặâầấẩẫậeèéẻẽẹêềếểễệiìíỉĩịoòóỏõọôồốổỗộơờớởỡợuùúủũụưừứửữựyỳýỷỹỵ"
_CONSONANTS = "bcdđghklmnpqrstvx"
_VIETNAMESE_LETTERS = _VOWELS + _VOWELS.upper() + _CONSONANTS + _CONSONANTS.upper()
_IN_WORD_PUNCTUATION = r".,;:!?()\-\/%\"'@"

_ALLOWED_CHAR_RE = re.compile(
    r"[" + re.escape(_VIETNAMESE_LETTERS) + r"0-9\s" + _IN_WORD_PUNCTUATION + r"]"
)
_VALID_TOKEN_RE = re.compile(
    r"^[" + re.escape(_VIETNAMESE_LETTERS) + r"0-9" + _IN_WORD_PUNCTUATION + r"]+$"
)
# A token of punctuation alone (e.g. "@@@", "---") matches _VALID_TOKEN_RE
# but isn't a word — require at least one real letter or digit too.
_HAS_ALNUM_RE = re.compile(r"[" + re.escape(_VIETNAMESE_LETTERS) + r"0-9]")

# Common Vietnamese contract words that are *never* written without their
# diacritics in real text. `garbage_char_ratio`/`valid_word_ratio` treat bare
# ASCII vowels as "valid" (see module docstring), so a page whose diacritics
# were silently dropped — a legacy TCVN3/VNI-encoded native PDF text layer,
# or a vision-model transcription that under-produced diacritics — passes
# both heuristics undetected: the letters are all Vietnamese-alphabet shapes,
# just missing their marks. Matching these bare-ASCII forms catches that
# failure mode without needing a full dictionary.
_UNACCENTED_SIGNATURE_WORDS = {
    "hop dong", "dieu", "khoan", "ben a", "ben b", "cong ty", "trach nhiem",
    "nghia vu", "thanh toan", "gia tri", "hieu luc", "cham dut", "vi pham",
    "boi thuong", "thong bao", "chu ky", "ky ket", "quyen loi", "dieu khoan",
    "phap luat", "giai quyet", "tranh chap", "van de", "ky thuat", "du lieu",
    "rui ro", "anh huong", "ket qua", "kip thoi",
}
_UNACCENTED_SIGNATURE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in sorted(_UNACCENTED_SIGNATURE_WORDS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def has_missing_diacritics_signature(text: str) -> bool:
    """True when `text` contains the bare-ASCII form of a word that is
    always accented in real Vietnamese contract text — a strong signal that
    diacritics were lost somewhere upstream, even though `garbage_char_ratio`
    and `valid_word_ratio` see nothing wrong (see comment above).
    """
    return bool(_UNACCENTED_SIGNATURE_RE.search(unicodedata.normalize("NFC", text)))


def garbage_char_ratio(text: str) -> float:
    """Fraction of characters in `text` that fall outside Vietnamese
    letters (with diacritics), digits, punctuation and whitespace.

    High values catch scanned pages with a garbage text layer and
    legacy TCVN3/VNI-encoded fonts, whose bytes decode to unrelated
    Unicode code points rather than the intended Vietnamese letters.
    """
    normalized = unicodedata.normalize("NFC", text)
    if not normalized:
        return 0.0
    allowed = sum(1 for ch in normalized if _ALLOWED_CHAR_RE.match(ch))
    return (len(normalized) - allowed) / len(normalized)


def valid_word_ratio(words: list[str]) -> float:
    """Fraction of `words` that look like well-formed Vietnamese/numeric
    tokens (see module docstring for why this is a shape heuristic rather
    than a real dictionary lookup). Returns 0.0 for an empty/blank list —
    no evidence of validity is treated the same as no valid words.
    """
    tokens = [w for w in words if w.strip()]
    if not tokens:
        return 0.0
    normalized = [unicodedata.normalize("NFC", w) for w in tokens]
    valid = sum(1 for w in normalized if _VALID_TOKEN_RE.match(w) and _HAS_ALNUM_RE.search(w))
    return valid / len(tokens)
