"""Running headers/footers/page numbers must stay out of clause text."""

from contract_ocr.application.use_cases.build_structure import BuildStructure
from contract_ocr.application.use_cases.running_text import detect_running_lines
from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import Document, Line, Page
from contract_ocr.domain.enums import GeometryProvenance, Status

HEADER = "HỢP ĐỒNG CUNG CẤP DỊCH VỤ (tiếp theo)"
CONTRACT_NO = "25/2026/HĐDV-MH-TT"


def _page(number: int, texts: list[str], *, boxes: list[BBox | None] | None = None) -> Page:
    page = Page(page_number=number, width=1, height=1, engine="e", model="m", status=Status.SUCCESS)
    boxes = boxes or [None] * len(texts)
    page.lines = [
        Line(
            line_id=f"p{number}-l{i}",
            text=text,
            bbox=box,
            geometry_provenance=GeometryProvenance.MEASURED if box else None,
        )
        for i, (text, box) in enumerate(zip(texts, boxes, strict=True), 1)
    ]
    return page


def _twelve_page_contract() -> Document:
    """Mirrors the real scan: header on pages 2+, footer contract number and
    "Trang N/12" on every page, and clause 4.3 ending right before page 3's footer."""
    pages = []
    for n in range(1, 13):
        body = [f"Điều {n}. Nội dung điều {n}", f"{n}.1. Khoản thứ nhất của điều {n}."]
        if n == 3:
            body = ["Điều 4. YÊU CẦU CHẤT LƯỢNG VÀ NGHIỆM THU", "4.3. Nghiệm thu căn cứ trên bộ mẫu."]
        if n == 4:
            body = ["Điều 5. QUYỀN VÀ NGHĨA VỤ CỦA BÊN A", "5.1. Cung cấp tài liệu đúng hạn."]
        header = ["HỢP ĐỒNG CUNG CẤP DỊCH VỤ"] if n == 1 else [HEADER]
        pages.append(_page(n, header + body + [CONTRACT_NO, f"Trang {n}/12"]))
    return Document(document_id="doc", source_file="unused.pdf", pages=pages)


def test_repeated_header_footer_and_page_numbers_are_detected():
    running = detect_running_lines(_twelve_page_contract())
    texts = {
        line.text
        for page in _twelve_page_contract().pages
        for line in page.lines
        if (page.page_number, line.line_id) in running
    }
    assert texts >= {HEADER, CONTRACT_NO, "Trang 3/12", "Trang 12/12"}


def test_first_page_title_and_clause_headings_are_not_running_text():
    doc = _twelve_page_contract()
    running = detect_running_lines(doc)
    kept = {
        line.text
        for page in doc.pages
        for line in page.lines
        if (page.page_number, line.line_id) not in running
    }
    assert "HỢP ĐỒNG CUNG CẤP DỊCH VỤ" in kept
    assert "Điều 4. YÊU CẦU CHẤT LƯỢNG VÀ NGHIỆM THU" in kept
    assert "4.3. Nghiệm thu căn cứ trên bộ mẫu." in kept


def test_clause_spanning_a_page_break_excludes_footer_and_next_header():
    nodes = {node.node_id: node for node in BuildStructure().execute(_twelve_page_contract())}
    clause = nodes["4.3"]
    assert clause.text == "4.3. Nghiệm thu căn cứ trên bộ mẫu."
    assert (clause.page_start, clause.page_end) == (3, 3)
    assert all(CONTRACT_NO not in node.text and "Trang " not in node.text for node in nodes.values())
    assert all(HEADER not in node.text for node in nodes.values())


def test_positioned_line_only_counts_inside_the_edge_band():
    top, middle, bottom = BBox(x1=0.1, y1=0.02, x2=0.9, y2=0.05), BBox(
        x1=0.1, y1=0.45, x2=0.9, y2=0.5
    ), BBox(x1=0.1, y1=0.95, x2=0.9, y2=0.98)
    pages = [
        _page(n, [HEADER, CONTRACT_NO, CONTRACT_NO], boxes=[top, middle, bottom]) for n in (1, 2, 3)
    ]
    running = detect_running_lines(Document(document_id="d", source_file="x", pages=pages))
    assert (1, "p1-l1") in running
    assert (1, "p1-l3") in running
    # Same text in the body of the page is real content, not a footer.
    assert (1, "p1-l2") not in running


def test_single_page_document_only_drops_page_numbers():
    page = _page(1, ["HỢP ĐỒNG", "Điều 1. Phạm vi", CONTRACT_NO, "Trang 1/1"])
    running = detect_running_lines(Document(document_id="d", source_file="x", pages=[page]))
    assert running == {(1, "p1-l4")}


def test_repeated_table_header_row_is_not_running_text():
    pages = [_page(n, ["| STT | Hạng mục |", f"Điều {n}. A", "Nội dung"]) for n in (1, 2, 3)]
    running = detect_running_lines(Document(document_id="d", source_file="x", pages=pages))
    assert not any(line_id.endswith("-l1") for _, line_id in running)
