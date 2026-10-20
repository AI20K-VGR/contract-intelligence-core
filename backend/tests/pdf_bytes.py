"""Real (minimal) PDF bytes for upload tests — the upload endpoint counts pages."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfWriter


def make_pdf(pages: int = 1, marker: str = "") -> bytes:
    """Blank ``pages``-page PDF; ``marker`` makes the bytes (and sha256) distinct."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    if marker:
        writer.add_metadata({"/Title": marker})
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
