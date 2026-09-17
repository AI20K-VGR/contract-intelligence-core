"""Tiện ích dùng chung — date/ULID/encoding helpers."""

from __future__ import annotations

import unicodedata
from datetime import date, datetime
from typing import Final

_NFC_FORM: Final[str] = "NFC"

# Valid forms cho unicodedata.normalize
_NORMALIZE_FORMS: Final[frozenset[str]] = frozenset({"NFC", "NFD", "NFKC", "NFKD"})


def normalize_text(text: str, form: str = _NFC_FORM) -> str:
    """Chuẩn hóa Unicode về NFC — quan trọng cho tiếng Việt có dấu.

    Tất cả text lưu DB đều đã qua hàm này (xem schema ``document_text.normalization``).
    """
    if form not in _NORMALIZE_FORMS:
        msg = f"form phải là một trong {sorted(_NORMALIZE_FORMS)}"
        raise ValueError(msg)
    return unicodedata.normalize(form, text)  # type: ignore[arg-type]


def to_iso_z(dt: datetime) -> str:
    """ISO 8601 UTC với hậu tố ``Z`` — dễ đọc trong log/UI."""
    return dt.astimezone().isoformat().replace("+00:00", "Z")


def to_iso_date(d: date) -> str:
    """ISO 8601 cho DATE — chỉ phần ngày ``YYYY-MM-DD``."""
    return d.isoformat()
