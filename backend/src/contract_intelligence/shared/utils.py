"""Tiện ích dùng chung — date/ULID/encoding helpers."""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final

_NFC_FORM: Final[str] = "NFC"

# Valid forms cho unicodedata.normalize
_NORMALIZE_FORMS: Final[frozenset[str]] = frozenset({"NFC", "NFD", "NFKC", "NFKD"})
_UNSAFE_FILENAME_CHARS: Final[re.Pattern[str]] = re.compile(r"[^\w.\-()+ ]+", re.UNICODE)


def normalize_text(text: str, form: str = _NFC_FORM) -> str:
    """Chuẩn hóa Unicode về NFC — quan trọng cho tiếng Việt có dấu.

    Tất cả text lưu DB đều đã qua hàm này (xem schema ``document_text.normalization``).
    """
    if form not in _NORMALIZE_FORMS:
        msg = f"form phải là một trong {sorted(_NORMALIZE_FORMS)}"
        raise ValueError(msg)
    return unicodedata.normalize(form, text)  # type: ignore[arg-type]


def safe_filename(name: str | None, *, fallback: str = "upload.bin") -> str:
    """Return a basename-only, path-safe filename for storage keys.

    Strips directory components (``../``, backslashes) so client-controlled
    upload names cannot escape the storage root.
    """
    raw = (name or "").strip()
    if not raw:
        return fallback
    base = Path(raw.replace("\\", "/")).name.strip().lstrip(".")
    cleaned = _UNSAFE_FILENAME_CHARS.sub("_", base).strip(" ._")
    if not cleaned or cleaned in {".", ".."}:
        return fallback
    return cleaned[:255]


def to_iso_z(dt: datetime) -> str:
    """ISO 8601 UTC với hậu tố ``Z`` — dễ đọc trong log/UI."""
    aware = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
    return aware.isoformat().replace("+00:00", "Z")


def to_iso_date(d: date) -> str:
    """ISO 8601 cho DATE — chỉ phần ngày ``YYYY-MM-DD``."""
    return d.isoformat()
