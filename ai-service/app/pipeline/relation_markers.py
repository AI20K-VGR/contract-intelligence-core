"""Shared lexical markers for amendment and definition sentences.

One place for the "does this sentence operate on another provision" test, so
relations.py and compare.py stop drifting apart. An operation verb only counts
when it points at an address (Điều/khoản/điểm/Phụ lục N) or uses a fixed
operation phrase — bare "sửa", "bổ sung", "điều chỉnh" are ordinary contract
wording ("sửa chữa hàng lỗi", "bổ sung hồ sơ", "điều chỉnh theo CPI").
"""

from __future__ import annotations

import re
import unicodedata

_ADDRESS = r"(?:điều|khoản|điểm|mục|phụ lục|dieu|khoan|diem|muc|phu luc)\s+[\w.]+"
_VERB = r"(?:sửa đổi(?:,\s*bổ sung)?|bổ sung|bãi bỏ|thay thế|thay cụm từ|bỏ cụm từ|điều chỉnh|sua doi|bo sung|bai bo|thay the)"

_AMEND_PATTERNS = (
    # verb ... address within one clause, either order ("Sửa đổi khoản 1 Điều 4", "Điều 4 được sửa đổi")
    re.compile(rf"{_VERB}[^.;\n]{{0,40}}?\b{_ADDRESS}", re.I),
    re.compile(rf"\b{_ADDRESS}[^.;\n]{{0,60}}?\b(?:được|is|are)?\s*{_VERB}", re.I),
    # item-level rewrite: "sửa A thành 110000", "điều chỉnh đơn giá thành …"
    re.compile(r"\b(?:sửa(?: đổi)?|điều chỉnh|thay đổi)\s+(?:[^.;\n]{1,40}?\s+)?thành\s+\S", re.I),
    re.compile(rf"\b{_ADDRESS}[^.;\n]{{0,40}}?không còn hiệu lực", re.I),
    re.compile(r"\bamend(?:s|ed|ment)?\b[^.;\n]{0,40}?\b(?:article|clause|section|annex)\s+\w+", re.I),
)
_AMEND_EXCLUDE = re.compile(r"sửa chữa|điều chỉnh theo\s+(?:cpi|chỉ số|giá thị trường|tỷ giá)", re.I)

_DEF_MARKER = r"(?:có nghĩa là|được hiểu là|nghĩa là|shall mean|means|co nghia la|duoc hieu la)"
_DEF_QUOTED = re.compile(rf"[\"“”']([^\"“”']{{2,80}})[\"“”']\s*(?:\([^)]*\)\s*)?{_DEF_MARKER}", re.I)
_DEF_BARE = re.compile(
    rf"(?:^|[.;:\n]\s*|(?:trong hợp đồng này|in this (?:contract|agreement)),\s*)"
    rf"([^\W\d_][^,.;:\n\"“”]{{1,60}}?)\s+{_DEF_MARKER}",
    re.I,
)


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def has_amend_marker(text: str | None) -> bool:
    """True when the sentence states an operation on another provision."""

    stripped = _AMEND_EXCLUDE.sub(" ", _nfc(text))
    return any(p.search(stripped) for p in _AMEND_PATTERNS)


def defined_term(text: str | None) -> str | None:
    """The defined term (left of "có nghĩa là"), never the definition body."""

    value = _nfc(text)
    match = _DEF_QUOTED.search(value) or _DEF_BARE.search(value)
    if not match:
        return None
    term = match.group(1).strip(" \t\"“”'()")
    return term or None
