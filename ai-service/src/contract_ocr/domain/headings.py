"""Recognizing a new section/annex heading, shared by the Mistral markdown-table
builder (infrastructure/ocr/markdown_tables.py, to compute a table's own
`heading_before`) and the table continuity use case (application/use_cases/
table_continuity.py, to hard-guard against joining two tables that a heading like
"Phụ lục 02" clearly separates). Kept in `domain` (no I/O, no OCR SDK import) so
both an infrastructure and an application module can depend on it without an
inverted import direction.

Mirrors `backend/app/table_continuity.py`'s own `is_annex_heading`, except matched
against the heading's real Vietnamese diacritics directly rather than a
diacritic-stripped form: unlike Tesseract, Mistral's OCR endpoint reliably keeps
Vietnamese accents (see ai-service/README.md), so there is no garbled-diacritics
case to defend against here.
"""

from __future__ import annotations

import re

_ANNEX_HEADING_PATTERN = re.compile(
    r"^(Phụ\s*lục|Biểu(?:\s+số)?|Chương|Mục|Điều|Article)\b", re.IGNORECASE
)


def is_annex_heading(text: str) -> bool:
    """True when `text` looks like a new section/annex heading (Phụ lục, Điều,
    Chương, Biểu, Mục, or their English equivalents) rather than an ordinary table
    row or caption."""
    return bool(text and _ANNEX_HEADING_PATTERN.match(text.strip()))
