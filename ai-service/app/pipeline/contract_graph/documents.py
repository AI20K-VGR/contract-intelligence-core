"""Which document an operation acts on, when the text names one by number.

"Sửa đổi điểm a khoản 8 Điều 11" resolves by number alone, so an operation on another document
("…Thông tư số 156/2013/TT-BTC", "…Hợp đồng số 15/2023/HĐKT") would land on the same-numbered
unit of the dossier file. The named document is taken from the sentence itself, else from its
parent unit / article heading; ``builder.plan_edges`` refuses a named document that is not one
of the dossier's known identities (BL-005, direction B: unknown identity ⇒ refuse).
"""

from __future__ import annotations

import re
import unicodedata

_DOC_TYPE = r"(?:thông\s+tư(?:\s+liên\s+tịch)?|nghị\s+định|nghị\s+quyết|luật|pháp\s+lệnh|quyết\s+định|hợp\s+đồng|thỏa\s+thuận|thoả\s+thuận)"
# "số 156/2013/TT-BTC", "15/2023/HĐKT": a number with at least one '/' segment; "Hợp đồng này" has none
_NAMED = re.compile(
    rf"(?<![\wđ]){_DOC_TYPE}\s+(?:số\s*:?\s*)?(?P<num>\d+(?:/[\wđĐ.\-]+)+)",
    re.I,
)
_QUOTED = re.compile(r"[“\"][^”\"]*[”\"]")


def named_document(text: str | None) -> str | None:
    """Normalised number of the first document named outside quotes, e.g. ``156/2013/tt-btc``."""

    if not text:
        return None
    value = _QUOTED.sub(" ", unicodedata.normalize("NFC", text))  # quoted wording is new text, not a target
    m = _NAMED.search(value)
    return normalize_document(m.group("num")) if m else None


def normalize_document(number: str) -> str:
    return unicodedata.normalize("NFC", number).strip().rstrip(".,;:").casefold()
