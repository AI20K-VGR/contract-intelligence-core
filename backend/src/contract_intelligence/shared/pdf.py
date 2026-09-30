"""PDF inspection at upload time (page count), before anything is sent to AI1."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PyPdfError


class InvalidPdfError(ValueError):
    """The uploaded bytes are not a readable PDF with at least one page."""


def count_pdf_pages(data: bytes) -> int:
    """Return the page count of ``data``; raise :class:`InvalidPdfError` if unreadable.

    CPU-bound on large files — call it via ``asyncio.to_thread`` from async code.
    """
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            # Owner-password-only PDFs open with an empty user password.
            reader.decrypt("")
        pages = len(reader.pages)
    except (PyPdfError, ValueError, KeyError, TypeError, OSError) as exc:
        msg = f"not a readable PDF: {type(exc).__name__}"
        raise InvalidPdfError(msg) from exc
    if pages < 1:
        raise InvalidPdfError("PDF has no pages")
    return pages


def extract_pdf_pages(data: bytes, page_start: int, page_end: int) -> bytes:
    """Pages ``page_start``..``page_end`` (1-based, inclusive) as a new PDF.

    CPU-bound — call it via ``asyncio.to_thread`` from async code.
    """
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")
        if not 1 <= page_start <= page_end <= len(reader.pages):
            msg = f"pages {page_start}-{page_end} outside 1-{len(reader.pages)}"
            raise InvalidPdfError(msg)
        writer = PdfWriter()
        for index in range(page_start - 1, page_end):
            writer.add_page(reader.pages[index])
        out = BytesIO()
        writer.write(out)
    except (PyPdfError, KeyError, TypeError, OSError) as exc:
        msg = f"cannot cut PDF: {type(exc).__name__}"
        raise InvalidPdfError(msg) from exc
    return out.getvalue()


__all__ = ["InvalidPdfError", "count_pdf_pages", "extract_pdf_pages"]
