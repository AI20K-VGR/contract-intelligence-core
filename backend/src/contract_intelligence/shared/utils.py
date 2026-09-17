"""Tiện ích dùng chung — date/ULID/encoding helpers."""

from __future__ import annotations

import unicodedata
from datetime import date, datetime
from typing import Final


_NFC_FORM: Final[str] = "NFC"


def normalize_text(text: str, form: str = _NFC_FORM) -> str:
    """Chuẩn hóa Unicode về NFC — quan trọng cho tiếng Việt có dấu.

    Tất cả text lưu DB đều đã qua hàm này (xem schema ``document_text.normalization``).
    """
    return unicodedata.normalize(form, text)


def to_iso_z(dt: datetime) -> str:
    """ISO 8601 UTC với hậu tố ``Z`` — dễ đọc trong log/UI."""
    return dt.astimezone().isoformat().replace("+00:00", "Z")


def to_iso_date(d: date) -> str:
    """ISO 8601 cho DATE — chỉ phần ngày ``YYYY-MM-DD``."""
    return d.isoformat()
