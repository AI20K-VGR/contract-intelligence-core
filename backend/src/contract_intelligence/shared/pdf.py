"""PDF inspection at upload time (page count), before anything is sent to AI1."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader
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


__all__ = ["InvalidPdfError", "count_pdf_pages"]
