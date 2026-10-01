"""Vietnamese-locale numeric parsing. Decimal only — never float, ever."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from .types import LogicalRow

_CURRENCY_SUFFIX_RE = re.compile(r"(?i)\s*(đồng|vnđ|vnd|đ)\s*$")
_VN_NUMBER_BODY_RE = re.compile(r"\d{1,3}(\.\d{3})*(,\d+)?|\d+(,\d+)?")
_TOTAL_KEYWORD_RE = re.compile(r"(tổng\s*cộng|tổng|cộng|total)", re.IGNORECASE)

# Digit words. "mốt"/"lăm"/"tư" are the forms used after "mươi"/"mười" for
# 1/5/4 respectively; they map to the same digit as their plain form.
_DIGIT_WORDS = {
    "không": 0,
    "một": 1,
    "mốt": 1,
    "hai": 2,
    "ba": 3,
    "bốn": 4,
    "tư": 4,
    "năm": 5,
    "lăm": 5,
    "sáu": 6,
    "bảy": 7,
    "tám": 8,
    "chín": 9,
}
_SCALE_WORDS = {"nghìn": 1_000, "ngàn": 1_000, "triệu": 1_000_000, "tỷ": 1_000_000_000}
# Trailing currency/exactness markers that carry no numeric value of their own.
_IGNORED_WORDS = {"đồng", "chẵn", "chẳn"}


def parse_vn_number(text: str) -> Decimal:
    """Parse a Vietnamese-formatted number: "." groups thousands, "," is the
    decimal separator (the reverse of the US convention). Raises
    `ValueError` for anything that isn't a clean Vietnamese number literal —
    callers that expect free text to sometimes not be a number should catch
    it rather than pre-validate.
    """
    if not isinstance(text, str):
        raise TypeError("parse_vn_number expects a string")

    cleaned = _CURRENCY_SUFFIX_RE.sub("", text.strip())
    cleaned = cleaned.replace(" ", "").replace(" ", "")
    if not cleaned:
        raise ValueError(f"empty numeric string: {text!r}")

    negative = cleaned.startswith("-")
    body = cleaned[1:] if negative else cleaned
    if not _VN_NUMBER_BODY_RE.fullmatch(body):
        raise ValueError(f"not a valid Vietnamese number: {text!r}")

    normalized = body.replace(".", "").replace(",", ".")
    try:
        value = Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"not a valid Vietnamese number: {text!r}") from exc
    return -value if negative else value


def vn_words_to_number(text: str) -> Decimal:
    """Parse a Vietnamese number-words phrase (e.g. "Một tỷ năm trăm triệu
    đồng chẵn") into a `Decimal`. Supports tỷ/triệu/nghìn-ngàn/trăm scale
    words, "mươi"/"mười" tens, the "mốt/lăm/tư" unit variants used after
    them, "linh"/"lẻ" as a zero-tens filler, and ignores trailing
    "đồng"/"chẵn". Raises `ValueError` on anything it can't fully consume.
    """
    if not isinstance(text, str):
        raise TypeError("vn_words_to_number expects a string")

    tokens = [
        tok.lower()
        for tok in re.split(r"\s+", text.strip())
        if tok and tok.lower() not in _IGNORED_WORDS
    ]
    if not tokens:
        raise ValueError(f"empty Vietnamese number phrase: {text!r}")

    total = 0
    buffer: list[str] = []
    for token in tokens:
        scale = _SCALE_WORDS.get(token)
        if scale is None:
            buffer.append(token)
            continue
        total += _parse_small_group(buffer) * scale
        buffer = []

    total += _parse_small_group(buffer)
    return Decimal(total)


def _parse_small_group(tokens: list[str]) -> int:
    """Parse a 0-999 group (the part of a number between two scale words,
    e.g. the "năm trăm" in "... năm trăm triệu ...")."""
    if not tokens:
        return 0

    value = 0
    i = 0
    n = len(tokens)

    if n >= 2 and tokens[1] == "trăm" and tokens[0] in _DIGIT_WORDS:
        value += _DIGIT_WORDS[tokens[0]] * 100
        i = 2

    if i < n and tokens[i] in ("linh", "lẻ"):
        i += 1
        if i < n and tokens[i] in _DIGIT_WORDS:
            value += _DIGIT_WORDS[tokens[i]]
            i += 1
        return value

    if i < n and tokens[i] == "mười":
        value += 10
        i += 1
        if i < n and tokens[i] in _DIGIT_WORDS:
            value += _DIGIT_WORDS[tokens[i]]
            i += 1
        return value

    if i + 1 < n and tokens[i + 1] == "mươi" and tokens[i] in _DIGIT_WORDS:
        value += _DIGIT_WORDS[tokens[i]] * 10
        i += 2
        if i < n and tokens[i] in _DIGIT_WORDS:
            value += _DIGIT_WORDS[tokens[i]]
            i += 1
        return value

    if i < n and tokens[i] in _DIGIT_WORDS:
        value += _DIGIT_WORDS[tokens[i]]
        i += 1

    if i != n:
        raise ValueError(f"unrecognized Vietnamese number tokens: {tokens!r}")
    return value


def is_total_row(row: LogicalRow) -> bool:
    """True for a "Tổng cộng"/"Cộng"/"Total" row: it must both mention one
    of those keywords AND lack a normal sequential-number value in its
    first (STT) cell — a data row that merely mentions "tổng" in a
    description column should not be mistaken for the totals row.
    """
    if not row.cells:
        return False
    if not any(_TOTAL_KEYWORD_RE.search(cell.text) for cell in row.cells):
        return False
    stt_text = row.cells[0].text.strip()
    return stt_text == "" or not re.fullmatch(r"\d+", stt_text)
