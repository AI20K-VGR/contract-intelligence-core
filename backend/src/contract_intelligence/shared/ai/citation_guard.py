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
    # AI2 canonical citations currently carry page-local offsets.  Keep the
    # resolved document offsets beside the decision so persistence can store a
    # span that points at the same OCR text that was verified.
    resolved_doc_char_start: int | None = None
    resolved_doc_char_end: int | None = None


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


async def _page_local_candidates(
    session: AsyncSession,
    *,
    document_id: str,
    citation: CitationItem,
) -> list[tuple[int, int]]:
    """Translate AI2 page-local segment offsets into document offsets.

    The canonical AI2 response describes ``char_start``/``char_end`` from the
    beginning of the cited page.  Backend OCR rows store document-global
    offsets.  The first OCR line on a page is the anchor because AI1 computes
    every line's global offset as ``page_base + page_char_start``.  We only use
    this fallback when the supplied document span does not already match, so
    producers that send global offsets remain compatible.
    """
    if not citation.segments:
        return []

    pages = sorted({int(segment.page_no) for segment in citation.segments})
    page_bases: dict[int, int] = {}
    for page_no in pages:
        result = await session.execute(
            select(OcrLineORM.doc_char_start)
            .where(
                OcrLineORM.document_id == document_id,
                OcrLineORM.page_no == page_no,
            )
            .order_by(OcrLineORM.doc_char_start.asc(), OcrLineORM.line_no.asc())
        )
        first = result.scalars().first()
        if first is not None:
            page_bases[page_no] = int(first)

    candidates: list[tuple[int, int]] = []
    # A citation normally has one segment.  Grouping segments by page also
    # handles a multi-line citation without changing the wire contract.
    for page_no in pages:
        base = page_bases.get(page_no)
        if base is None:
            continue
        segments = [item for item in citation.segments if int(item.page_no) == page_no]
        if not segments:
            continue
        local_start = min(int(item.char_start) for item in segments)
        local_end = max(int(item.char_end) for item in segments)
        if local_end > local_start:
            candidates.append((base + local_start, base + local_end))
    return candidates


def sha256_hex(value: str) -> str:
    return hashlib.sha256(normalize_text(value).encode("utf-8")).hexdigest()


async def verify_citation(
    session: AsyncSession,
    *,
    document_id: str,
    citation: CitationItem,
) -> CitationGuardResult:
    """Accept citation only when quote matches the stored OCR span."""
    model_quote = normalize_text(citation.quote or "")

    ocr_span = await reconstruct_ocr_span(
        session,
        document_id=document_id,
        doc_char_start=citation.doc_char_start,
        doc_char_end=citation.doc_char_end,
    )
    candidates: list[tuple[int, int, str]] = []
    if ocr_span is not None:
        candidates.append(
            (citation.doc_char_start, citation.doc_char_end, normalize_text(ocr_span))
        )

    # Primary check: model quote must equal OCR span text.  If AI2 sent
    # page-local offsets, try a page anchored translation before rejecting it.
    if not any(model_quote == candidate_quote for _, _, candidate_quote in candidates):
        for start, end in await _page_local_candidates(
            session, document_id=document_id, citation=citation
        ):
            page_span = await reconstruct_ocr_span(
                session,
                document_id=document_id,
                doc_char_start=start,
                doc_char_end=end,
            )
            if page_span is not None:
                candidates.append((start, end, normalize_text(page_span)))

    matching = next(
        (
            (start, end, candidate_quote)
            for start, end, candidate_quote in candidates
            if model_quote == candidate_quote
        ),
        None,
    )
    if matching is None:
        if ocr_span is None and not candidates:
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
        ocr_norm = candidates[0][2] if candidates else ""
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
            quote_sha256=sha256_hex(ocr_norm) if ocr_norm else "",
            reason="quote_mismatch",
        )

    resolved_start, resolved_end, ocr_norm = matching
    expected_sha = sha256_hex(ocr_norm)

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
            resolved_doc_char_start=resolved_start,
            resolved_doc_char_end=resolved_end,
        )

    if (resolved_start, resolved_end) != (
        citation.doc_char_start,
        citation.doc_char_end,
    ):
        logger.info(
            "citation_guard.page_local_offset_resolved",
            document_id=document_id,
            source_start=citation.doc_char_start,
            source_end=citation.doc_char_end,
            resolved_start=resolved_start,
            resolved_end=resolved_end,
        )

    return CitationGuardResult(
        accepted=True,
        quote=ocr_norm,
        quote_sha256=expected_sha,
        reason="ok",
        resolved_doc_char_start=resolved_start,
        resolved_doc_char_end=resolved_end,
    )


__all__ = [
    "CitationGuardResult",
    "reconstruct_ocr_span",
    "sha256_hex",
    "verify_citation",
]
