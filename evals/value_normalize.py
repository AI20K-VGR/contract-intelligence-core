"""Conservative, deterministic normalization for values checked against evidence."""

from __future__ import annotations

import re
import unicodedata

_DATE_WORDS = re.compile(r"^ngay\s+(\d{1,2})\s+thang\s+(\d{1,2})\s+nam\s+(\d{4})$", re.IGNORECASE)
_DATE_SLASH = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_CONTRACT_ID = re.compile(r"^(?:so\s+)?(\d{1,})/(\d{4})/([a-z0-9.-]+)$", re.IGNORECASE)
_NUMBER = re.compile(r"(?<![\w/])([+-]?\d[\d., ]*\d|[+-]?\d)(?:\s*)(%|vnd|dong|đồng|usd|eur|ngay|thang|nam)?(?![/\w])", re.IGNORECASE)
_DIGIT_GROUPING = re.compile(r"\s+")


def normalize_value(value: object) -> str:
    """Normalize visible numeric/date formatting without inventing word numbers."""

    text = unicodedata.normalize("NFKC", str(value)).strip()
    folded = _fold(text)
    contract_id = _CONTRACT_ID.fullmatch(folded)
    if contract_id:
        return "/".join(contract_id.groups())
    date = _DATE_WORDS.fullmatch(folded)
    if date:
        return f"date:{int(date.group(3)):04d}-{int(date.group(2)):02d}-{int(date.group(1)):02d}"
    date = _DATE_SLASH.fullmatch(folded)
    if date and 1 <= int(date.group(1)) <= 31 and 1 <= int(date.group(2)) <= 12:
        return f"date:{int(date.group(3)):04d}-{int(date.group(2)):02d}-{int(date.group(1)):02d}"

    normalized = _NUMBER.sub(_normalize_number_match, folded)
    normalized = _DIGIT_GROUPING.sub(" ", normalized)
    return normalized.strip()


def _normalize_number_match(match: re.Match[str]) -> str:
    raw = match.group(1).replace(" ", "")
    unit = (match.group(2) or "").casefold()
    if unit in {"ngay", "thang", "nam"}:
        return match.group(0)
    number = _canonical_number(raw)
    if number is None:
        return match.group(0).strip()
    normalized_unit = {"dong": "vnd"}.get(unit, unit)
    if normalized_unit == "%":
        return f"{number}%"
    if normalized_unit:
        return f"{number} {normalized_unit}"
    return number


def _canonical_number(raw: str) -> str | None:
    sign = ""
    if raw[:1] in "+-":
        sign, raw = raw[0], raw[1:]
    if not raw or not any(character.isdigit() for character in raw):
        return None
    if "." in raw and "," in raw:
        decimal = "." if raw.rfind(".") > raw.rfind(",") else ","
        grouping = "," if decimal == "." else "."
        integer, fraction = raw.rsplit(decimal, 1)
        integer = integer.replace(grouping, "")
        if not integer.isdigit() or not fraction.isdigit():
            return None
        return f"{sign}{int(integer)}.{fraction.rstrip('0') or '0'}"
    separator = "." if "." in raw else "," if "," in raw else None
    if separator is None:
        digits = raw
        fraction = ""
    else:
        pieces = raw.split(separator)
        if len(pieces) > 2 and all(len(piece) == 3 for piece in pieces[1:]) or len(pieces) == 2 and len(pieces[1]) == 3 and len(pieces[0]) >= 1:
            digits, fraction = "".join(pieces), ""
        elif len(pieces) == 2:
            digits, fraction = pieces
        else:
            return None
    if not digits.isdigit() or (fraction and not fraction.isdigit()):
        return None
    integer = str(int(digits))
    return f"{sign}{integer}.{fraction.rstrip('0') or '0'}" if fraction else f"{sign}{integer}"


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.replace("đ", "d").replace("Đ", "D")).casefold()
    return "".join(character for character in decomposed if not unicodedata.combining(character))
