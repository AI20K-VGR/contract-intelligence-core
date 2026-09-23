"""Helpers for tracking exactly which raw block(s) a merged string came from.

Every merge must be able to answer "which characters of this text came from
which (page, block_id)?" — that mapping is what makes reconstruction
auditable instead of a black box (section 16).
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import SourceBlockRef


@dataclass(frozen=True)
class TextFragment:
    page: int
    block_id: str
    text: str


def source_ref(page: int, block_id: str) -> SourceBlockRef:
    return SourceBlockRef(page=page, block_id=block_id)
