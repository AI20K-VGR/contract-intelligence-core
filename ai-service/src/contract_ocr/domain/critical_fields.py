"""Critical tokens -- money, percentages, dates, tax/account numbers, contract
numbers -- whose misreading changes a contract's legal meaning.

Extraction runs on the diacritic-free skeleton so two readers can be compared
even when one of them (mistral-ocr-4.x) drops accents: "1.286.400.000 dong" and
"1.286.400.000 đồng" yield the same token. Tokens keep only digits (and the
contract-number suffix), so a single misread digit is a mismatch.
"""

from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal

from contract_ocr.domain.vn_text import skeleton
from contract_ocr.table_reconstruct.numbers import parse_vn_number, vn_words_to_number

_MONEY = re.compile(r"(?<![\d.,])(\d{1,3}(?:[.,]\d{3})+|\d{4,})(?:,\d{1,2})?\s*(?:dong|vnd|d\b|usd)")
_GROUPED_NUMBER = re.compile(r"(?<![\d.,/])\d{1,3}(?:\.\d{3}){2,}(?![\d.,]*\d)")
_PERCENT = re.compile(r"(?<![\d.,])(\d{1,3}(?:[.,]\d+)?)\s*%")
_DATE = re.compile(r"(?<!\d)(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?!\d)")
_DATE_WORDS = re.compile(r"ngay\s+(\d{1,2})\s+thang\s+(\d{1,2})\s+nam\s+(\d{4})")
_CONTRACT_NO = re.compile(r"(?<![\d/])(\d{1,5}/\d{4}/[a-z0-9-]+)")
_LONG_NUMBER = re.compile(r"(?<![\d.,/-])(\d{9,16}(?:-\d{3})?)(?![\d/]|[.,]\d)")
_AMOUNT_IN_WORDS = re.compile(r"\(\s*bằng\s*chữ\s*:?\s*([^)]+)\)", re.IGNORECASE)


def critical_tokens(text: str) -> Counter[str]:
    """Normalized critical tokens in `text` (a multiset: the same amount twice
    on a line is two tokens)."""
    s = skeleton(text)
    tokens: Counter[str] = Counter()
    for match in _MONEY.finditer(s):
        tokens[f"money:{re.sub(r'[.,]', '', match.group(1))}"] += 1
    money_spans = [m.span(1) for m in _MONEY.finditer(s)]
    for match in _GROUPED_NUMBER.finditer(s):
        if not any(start <= match.start() < end for start, end in money_spans):
            tokens[f"number:{match.group(0).replace('.', '')}"] += 1
    for match in _PERCENT.finditer(s):
        tokens[f"percent:{match.group(1).replace(',', '.')}"] += 1
    for match in [*_DATE.finditer(s), *_DATE_WORDS.finditer(s)]:
        day, month, year = (int(g) for g in match.groups())
        tokens[f"date:{day:02d}/{month:02d}/{year}"] += 1
    for match in _CONTRACT_NO.finditer(s):
        tokens[f"contract:{match.group(1)}"] += 1
    for match in _LONG_NUMBER.finditer(s):
        tokens[f"id:{match.group(1)}"] += 1
    return tokens


def amount_words_mismatch(text: str) -> bool:
    """True when a line states an amount in digits and in words ("1.286.400.000
    đồng (Bằng chữ: Một tỷ hai trăm tám mươi sáu triệu bốn trăm nghìn đồng)")
    and the two disagree. A reading whose digits and words agree is internally
    consistent evidence for that amount; one that disagrees misread one of them."""
    words_match = _AMOUNT_IN_WORDS.search(text)
    digits = [m.group(1) for m in _MONEY.finditer(skeleton(text[: words_match.start()]))] if words_match else []
    if not words_match or not digits:
        return False
    try:
        in_words = vn_words_to_number(words_match.group(1).strip().rstrip(".").strip())
        in_digits = parse_vn_number(digits[-1])
    except ValueError:
        # Unparseable words are not evidence of a mismatch, only of a phrase
        # the parser doesn't cover.
        return False
    return in_words != in_digits and in_words != Decimal(0)
