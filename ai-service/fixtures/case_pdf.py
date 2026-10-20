"""Generate document-backed PDFs for synthetic/evaluation cases.

The catalog is an AI2 handoff fixture, so many cases historically contained
only ``PageSnapshot``/``TableSnapshot`` objects.  The demo still needs a
realistic source artifact to render and highlight.  This module creates a
stable, local PDF preview from that handoff without changing the raw evidence
or pretending it came from OCR.
"""

from __future__ import annotations

from hashlib import sha256
from html import escape
from io import BytesIO
from pathlib import Path
import os
import re
from typing import Any

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from app.contracts.models import SourceFile
from fixtures.catalog import CasePack


GENERATED_PDF_DIR = Path(__file__).resolve().parent / "generated_pdfs"


def _font_names() -> tuple[str, str]:
    """Register a Unicode Windows font, with a portable Helvetica fallback."""
    windows = Path(os.getenv("WINDIR", r"C:\Windows")) / "Fonts"
    regular = next(
        (path for path in (windows / "arial.ttf", windows / "segoeui.ttf", windows / "tahoma.ttf") if path.exists()),
        None,
    )
    bold = next(
        (path for path in (windows / "arialbd.ttf", windows / "segoeuib.ttf", windows / "tahomabd.ttf") if path.exists()),
        None,
    )
    if not regular or not bold:
        return "Helvetica", "Helvetica-Bold"
    try:
        pdfmetrics.registerFont(TTFont("AI2Unicode", str(regular)))
        pdfmetrics.registerFont(TTFont("AI2Unicode-Bold", str(bold)))
        return "AI2Unicode", "AI2Unicode-Bold"
    except Exception:
        return "Helvetica", "Helvetica-Bold"


def _safe(value: Any) -> str:
    return escape("" if value is None else str(value)).replace("\n", "<br/>")


def _table_page_map(pack: CasePack) -> dict[int, list[Any]]:
    nodes = {node.node_id: node for node in pack.record.nodes}
    by_page: dict[int, list[Any]] = {}
    for table in pack.record.tables:
        node = nodes.get(table.node_id or "")
        pages = list(node.page_range) if node and node.page_range else []
        if not pages and table.page_revision_id:
            pages = [
                page.page_number
                for page in pack.record.pages
                if page.page_revision_id == table.page_revision_id
            ]
        target = pages[0] if pages else (pack.record.pages[0].page_number if pack.record.pages else 1)
        by_page.setdefault(target, []).append(table)
    return by_page


def build_case_pdf(pack: CasePack) -> bytes:
    """Render all snapshot pages and tables into one demo PDF."""
    regular, bold = _font_names()
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "AI2Title", parent=styles["Heading2"], fontName=bold, fontSize=13, leading=16,
        textColor=colors.HexColor("#17324d"), spaceAfter=5,
    )
    body = ParagraphStyle(
        "AI2Body", parent=styles["BodyText"], fontName=regular, fontSize=9.5, leading=13,
        spaceAfter=4, wordWrap="CJK",
    )
    table_title = ParagraphStyle(
        "AI2TableTitle", parent=body, fontName=bold, fontSize=9.5, leading=12,
        textColor=colors.HexColor("#17324d"), spaceBefore=5, spaceAfter=3,
    )
    cell = ParagraphStyle("AI2Cell", parent=body, fontName=regular, fontSize=7.5, leading=9)
    head = ParagraphStyle("AI2Head", parent=cell, fontName=bold, textColor=colors.white, alignment=TA_CENTER)

    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"AI2 demo {pack.case_id}",
        author="VSF AI2 demo fixture renderer",
    )
    table_by_page = _table_page_map(pack)
    story: list[Any] = []
    pages = pack.record.pages or []
    for page_index, page in enumerate(pages):
        story.append(Paragraph(f"{_safe(pack.case_id)} — trang {_safe(page.page_number)}", title))
        story.append(Paragraph(f"Nguồn demo: {_safe(pack.title)}", body))
        if page.quality != "OK" or page.table_coverage.value != "UNKNOWN":
            story.append(
                Paragraph(
                    f"Chất lượng: {_safe(page.quality)} · Table coverage: {_safe(page.table_coverage.value)}",
                    body,
                )
            )
        text = page.text or "(trang không có text)"
        for block in re.split(r"\n\s*\n", text):
            if block.strip():
                story.append(Paragraph(_safe(block.strip()), body))

        for table in table_by_page.get(page.page_number, []):
            story.append(Paragraph(f"Bảng: {_safe(table.title or table.table_id)}", table_title))
            rows = [[Paragraph(_safe(value), head) for value in table.header]]
            rows.extend(
                [[Paragraph(_safe(value), cell) for value in row] for row in table.rows]
            )
            if len(rows) == 1:
                rows.append([Paragraph("(không có dòng)", cell)])
            widths = [(178 * mm) / max(1, len(table.header)) for _ in table.header]
            table_flowable = LongTable(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
            table_flowable.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d607f")),
                        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#9bb2c2")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f7fa")]),
                    ]
                )
            )
            story.append(table_flowable)
        if page_index < len(pages) - 1:
            story.append(PageBreak())

    if not story:
        story.append(Paragraph(f"{_safe(pack.case_id)} — không có trang", title))

    def footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont(regular, 7)
        canvas.setFillColor(colors.HexColor("#687b88"))
        canvas.drawString(16 * mm, 8 * mm, f"AI2 demo preview · {pack.case_id}")
        canvas.drawRightString(194 * mm, 8 * mm, f"PDF page {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


def generated_pdf_path(case_id: str, output_dir: Path | None = None) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", case_id)
    return (output_dir or GENERATED_PDF_DIR) / f"{safe}.pdf"


def attach_case_pdf(pack: CasePack, pdf_bytes: bytes | None = None) -> tuple[dict[str, bytes], Path]:
    """Attach one generated source file and align page/node mapping for UI."""
    path = generated_pdf_path(pack.case_id)
    if pdf_bytes is None:
        if path.exists():
            pdf_bytes = path.read_bytes()
        else:
            pdf_bytes = build_case_pdf(pack)
    file_id = f"case_pdf_{re.sub(r'[^A-Za-z0-9]+', '_', pack.case_id).lower()}"
    try:
        n_pages = len(PdfReader(BytesIO(pdf_bytes)).pages)
    except Exception:
        n_pages = len(pack.record.pages)
    digest = "sha256:" + sha256(pdf_bytes).hexdigest()[:32]
    pack.record.source_files = [
        SourceFile(file_id=file_id, filename=f"{pack.case_id}.pdf", role="body", digest=digest, n_pages=n_pages)
    ]
    for page in pack.record.pages:
        page.source_file_id = file_id
        page.page_in_file = page.page_number
    for node in pack.record.nodes:
        node.source_file_id = file_id
        node.page_in_file = node.page_range[0] if node.page_range else 1
    return {file_id: pdf_bytes}, path


def materialize_all_case_pdfs(output_dir: Path | None = None) -> list[dict[str, Any]]:
    from fixtures.eval_suite import all_eval_cases

    target = output_dir or GENERATED_PDF_DIR
    target.mkdir(parents=True, exist_ok=True)
    rows = []
    for case_id, pack in all_eval_cases().items():
        pdf = build_case_pdf(pack)
        path = generated_pdf_path(case_id, target)
        path.write_bytes(pdf)
        try:
            display_path = path.relative_to(Path(__file__).resolve().parents[1]).as_posix()
        except ValueError:
            display_path = path.name
        rows.append({"case_id": case_id, "path": display_path, "bytes": len(pdf), "pdf_pages": len(PdfReader(BytesIO(pdf)).pages)})
    return rows
