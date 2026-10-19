"""Build small text-layer PDFs in memory, no third-party dependency.

The repo forbids committing PDFs (pr-guard), so test documents are generated
at run time. Text is ASCII (Helvetica, WinAnsi) so the free `pymupdf` OCR
engine reads it straight from the text layer.
"""

from __future__ import annotations

SAMPLE_CONTRACT = [
    "HOP DONG MUA BAN HANG HOA",
    "So: QA-E2E-001/2026",
    "Dieu 1. Doi tuong hop dong",
    "Ben A ban cho Ben B 100 tan thep xay dung loai CB300.",
    "Dieu 2. Gia tri hop dong",
    "Tong gia tri hop dong la 1.500.000.000 VND (da bao gom VAT).",
    "Dieu 3. Thanh toan",
    "Ben B thanh toan 30% trong 07 ngay ke tu ngay ky.",
    "Phan con lai thanh toan trong 30 ngay sau khi nghiem thu.",
    "Dieu 4. Thoi han giao hang",
    "Ben A giao hang trong 15 ngay ke tu ngay ky hop dong.",
    "Dieu 5. Phat vi pham",
    "Ben vi pham chiu phat 8% gia tri phan nghia vu bi vi pham.",
]

SAMPLE_ANNEX = [
    "PHU LUC 01 HOP DONG SO QA-E2E-001/2026",
    "Dieu 1. Sua doi thanh toan",
    "Ben B thanh toan 50% trong 10 ngay ke tu ngay ky.",
    "Dieu 2. Thoi han giao hang",
    "Ben A giao hang trong 20 ngay ke tu ngay ky hop dong.",
]


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf(pages: list[list[str]]) -> bytes:
    """Return a valid PDF with one page per list of lines."""
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    catalog = add(b"")  # patched below once the page tree id is known
    pages_id = add(b"")
    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    page_ids = []
    for lines in pages:
        ops = ["BT", "/F1 12 Tf", "16 TL", "56 780 Td"]
        for line in lines:
            ops.append(f"({_escape(line)}) Tj T*")
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        content_id = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        page_ids.append(
            add(
                b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 595 842] "
                b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
                % (pages_id, font_id, content_id)
            )
        )
    kids = b" ".join(b"%d 0 R" % pid for pid in page_ids)
    objects[catalog - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id
    objects[pages_id - 1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(page_ids))

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % off for off in offsets)
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        catalog,
        xref,
    )
    return bytes(out)


def sample_contract_pdf() -> bytes:
    return build_pdf([SAMPLE_CONTRACT])


def sample_annex_pdf() -> bytes:
    return build_pdf([SAMPLE_ANNEX])
