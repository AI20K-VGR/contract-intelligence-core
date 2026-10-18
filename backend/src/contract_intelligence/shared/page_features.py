"""Read the ``page.features`` value AI1 writes (``shared/ai/ai1_adapter.py``).

One place for its shape, so the dossier list, the page DTO and the worker read
``ai1_page_status`` and ``error`` the same way.
"""

from __future__ import annotations

import json
from typing import Any


def parse_page_features(raw: object) -> dict[str, Any] | None:
    """``features`` as a dict: Postgres may return a dict, SQLite and raw SQL JSON text."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except ValueError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def page_ocr_status(raw: object) -> tuple[str, str | None]:
    """``(ai1_page_status upper-cased, error)``; ``("", None)`` when unreadable."""
    features = parse_page_features(raw)
    if features is None:
        return "", None
    error = features.get("error")
    return str(features.get("ai1_page_status") or "").upper(), (str(error) if error else None)
