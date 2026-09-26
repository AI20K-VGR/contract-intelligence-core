"""A page repeating an earlier page is marked, never a page that only looks alike."""

from contract_ocr.application.use_cases.duplicate_pages import mark_duplicate_pages
from contract_ocr.domain.entities import Document, Line, Page
from contract_ocr.domain.enums import Status

CLAUSE = (
    "Điều 2. Giá trị hợp đồng và phương thức thanh toán. Tổng giá trị hợp đồng là "
    "1.286.400.000 đồng, đã bao gồm thuế giá trị gia tăng. Bên A thanh toán cho Bên B "
    "thành hai đợt bằng hình thức chuyển khoản trong vòng 15 ngày làm việc."
)


def _page(number: int, text: str, *, status: Status = Status.SUCCESS) -> Page:
    page = Page(page_number=number, width=1, height=1, engine="e", model="m", status=status)
    page.lines = [
        Line(line_id=f"p{number}-l{i}", text=part) for i, part in enumerate(text.split(". "), 1)
    ]
    return page


def _mark(*pages: Page) -> list[Page]:
    document = Document(document_id="d", source_file="x", pages=list(pages))
    mark_duplicate_pages(document)
    return document.pages


def test_verbatim_repeat_is_a_duplicate_of_the_first_occurrence():
    pages = _mark(_page(1, "Điều 1. Phạm vi " * 12), _page(2, CLAUSE), _page(3, CLAUSE))
    assert [(p.duplicate_of, p.near_duplicate_of) for p in pages] == [
        (None, None),
        (None, None),
        (2, None),
    ]


def test_rescan_with_a_few_misread_letters_is_only_a_near_duplicate():
    rescan = CLAUSE.replace("thanh toán cho", "thanh toan cho").replace("chuyển", "chuyến")
    pages = _mark(_page(1, CLAUSE), _page(2, rescan))
    assert (pages[1].duplicate_of, pages[1].near_duplicate_of) == (None, 1)


def test_template_page_with_different_numbers_is_not_a_duplicate():
    pages = _mark(_page(1, CLAUSE), _page(2, CLAUSE.replace("1.286.400.000", "2.000.000.000")))
    assert (pages[1].duplicate_of, pages[1].near_duplicate_of) == (None, None)


def test_short_pages_are_never_paired():
    pages = _mark(_page(1, "PHỤ LỤC"), _page(2, "PHỤ LỤC"))
    assert all(p.duplicate_of is None and p.near_duplicate_of is None for p in pages)


def test_failed_pages_are_ignored():
    pages = _mark(_page(1, CLAUSE, status=Status.FAILED), _page(2, CLAUSE))
    assert pages[1].duplicate_of is None
