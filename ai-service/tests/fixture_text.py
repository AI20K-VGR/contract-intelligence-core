"""Helpers for clean-clone text fixtures used by the AI1/AI2 tests.

The repository keeps contract-shaped fixtures as Markdown so the source tree
does not carry binary contract documents.  AI1's PDF path receives OCR-like
plain text, so these helpers remove presentation markers while retaining the
document content and ordering.
"""

from __future__ import annotations

import re
from pathlib import Path

CONTRACTS = Path(__file__).resolve().parents[1] / "fixtures" / "contracts"


def plain_fixture_bytes(filename: str) -> bytes:
    """Return a Markdown contract fixture as deterministic OCR-like bytes."""

    text = (CONTRACTS / filename).read_text(encoding="utf-8")
    text = re.sub(r"\*\*|__|`", "", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-*]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    return text.encode("utf-8")
