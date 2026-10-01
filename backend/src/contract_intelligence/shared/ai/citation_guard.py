"""Citation Guard — verify AI citations against stored OCR spans.

Mentor finding: ``quote_sha256`` was hashing the model's quote blindly, and
span lookups returned empty stubs. Before accepting a citation we reconstruct
the OCR text for ``[doc_char_start, doc_char_end)`` from persisted ``ocr_line``
rows and only accept when the model quote matches that span (NFC + sha256).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.extraction.infrastructure.persistence.orm import OcrLineORM
from contract_intelligence.shared.ai.schemas import CitationItem
from contract_intelligence.shared.utils import normalize_text

logger = structlog.get_logger(__name__)


@dataclass(slots=True, frozen=True)
class CitationGuardResult:
    accepted: bool
    quote: str
    quote_sha256: str
    reason: str = ""


async def reconstruct_ocr_span(
    session: AsyncSession,
    *,
    document_id: str,
    doc_char_start: int,
    doc_char_end: int,
) -> str | None:
    """Rebuild document text for a char span from stored OCR lines.

    Returns ``None`` when no overlapping OCR lines exist (cannot verify).
    """
    if doc_char_end <= doc_char_start:
        return None

    result = await session.execute(
        select(OcrLineORM)
        .where(
            OcrLineORM.document_id == document_id,
            OcrLineORM.doc_char_end > doc_char_start,
            OcrLineORM.doc_char_start < doc_char_end,
        )
        .order_by(OcrLineORM.doc_char_start.asc(), OcrLineORM.line_no.asc())
    )
    lines = list(result.scalars().all())
    if not lines:
        return None

    # Prefer contiguous reconstruction when lines cover a continuous range.
    pieces: list[str] = []
    for line in lines:
        text = line.text or ""
        # Map absolute doc offsets → offsets within this line's text.
        local_start = max(0, doc_char_start - int(line.doc_char_start))
        local_end = min(len(text), doc_char_end - int(line.doc_char_start))
        if local_end > local_start:
            pieces.append(text[local_start:local_end])
    if not pieces:
        return None
    return normalize_text("".join(pieces))


def sha256_hex(value: str) -> str:
    return hashlib.sha256(normalize_text(value).encode("utf-8")).hexdigest()


async def verify_citation(
    session: AsyncSession,
    *,
    document_id: str,
    citation: CitationItem,
) -> CitationGuardResult:
    """Accept citation only when quote matches the stored OCR span."""
    ocr_span = await reconstruct_ocr_span(
        session,
        document_id=document_id,
        doc_char_start=citation.doc_char_start,
        doc_char_end=citation.doc_char_end,
    )
    if ocr_span is None:
        logger.warning(
            "citation_guard.no_ocr_span",
            document_id=document_id,
            start=citation.doc_char_start,
            end=citation.doc_char_end,
        )
        return CitationGuardResult(
            accepted=False,
            quote=citation.quote,
            quote_sha256="",
            reason="no_ocr_span",
        )

    model_quote = normalize_text(citation.quote or "")
    ocr_norm = normalize_text(ocr_span)
    expected_sha = sha256_hex(ocr_norm)

    # Primary check: model quote must equal OCR span text.
    if model_quote != ocr_norm:
        logger.warning(
            "citation_guard.quote_mismatch",
            document_id=document_id,
            start=citation.doc_char_start,
            end=citation.doc_char_end,
            model_len=len(model_quote),
            ocr_len=len(ocr_norm),
        )
        return CitationGuardResult(
            accepted=False,
            quote=ocr_norm,
            quote_sha256=expected_sha,
            reason="quote_mismatch",
        )

    # Secondary: if model supplied quote_sha256, it must match OCR-derived hash.
    if citation.quote_sha256 and citation.quote_sha256 != expected_sha:
        logger.warning(
            "citation_guard.sha_mismatch",
            document_id=document_id,
            expected=expected_sha,
            got=citation.quote_sha256,
        )
        return CitationGuardResult(
            accepted=False,
            quote=ocr_norm,
            quote_sha256=expected_sha,
            reason="sha_mismatch",
        )

    return CitationGuardResult(
        accepted=True,
        quote=ocr_norm,
        quote_sha256=expected_sha,
        reason="ok",
    )


__all__ = [
    "CitationGuardResult",
    "reconstruct_ocr_span",
    "sha256_hex",
    "verify_citation",
]
