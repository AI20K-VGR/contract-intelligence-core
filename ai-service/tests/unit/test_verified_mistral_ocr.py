"""VerifiedMistralOCREngine with fake readers on a synthetic rendered page."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import Context, Line, OCRResult
from contract_ocr.domain.enums import GeometryProvenance
from contract_ocr.infrastructure.ocr.verified_mistral_ocr import VerifiedMistralOCREngine

WIDTH, HEIGHT = 1200, 1600
PARA = "4.1. Ket qua ban giao phai dam bao kha nang truy vet tu du lieu trich xuat ve"
PARA_2 = "trang, dong hoac vung nguon tuong ung tren tai lieu."
MONEY = "3.1. Tong gia tri hop dong la 1.286.400.000 dong theo pham vi."
CLEAN_VN = [
    "ĐIỀU 4. YÊU CẦU CHẤT LƯỢNG VÀ NGHIỆM THU",
    "4.1. Kết quả bàn giao phải đảm bảo khả năng truy vết từ dữ liệu trích xuất về "
    "trang, dòng hoặc vùng nguồn tương ứng trên tài liệu.",
]
MONEY_VN = "3.1. Tổng giá trị hợp đồng là 1.286.400.000 đồng theo phạm vi."
GARBLED = (
    "4.1. Két qua bàn giao phai dam bao khà nang truy vét t ur du lieu trich xuát vê "
    "trang, dong hoac vùng nguôn tuong ung trèn tai lieu."
)


def _page(lines: list[str], *, grid: bool = False) -> np.ndarray:
    image = np.full((HEIGHT, WIDTH, 3), 255, dtype=np.uint8)
    y = 120
    for text in lines:
        cv2.putText(image, text, (60, y), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (0, 0, 0), 2)
        y += 48
    if grid:
        top, rows, cols = 700, [700, 760, 820, 880], [60, 400, 800, 1140]
        for yy in rows:
            cv2.line(image, (cols[0], yy), (cols[-1], yy), (0, 0, 0), 2)
        for xx in cols:
            cv2.line(image, (xx, top), (xx, rows[-1]), (0, 0, 0), 2)
        for r, yy in enumerate(rows[:-1]):
            for c, xx in enumerate(cols[:-1]):
                cv2.putText(image, f"r{r}c{c}", (xx + 10, yy + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    return image


class FakeReader:
    def __init__(self, markdown: str | None = None, *, lines=None, tables=None, error=None):
        self.markdown, self.lines, self.tables, self.error = markdown, lines or [], tables or [], error
        self.calls = 0
        self.name, self.model, self.runtime_info = "fake", "fake-model", {}

    def recognize_page(self, image, context):
        self.calls += 1
        if self.error:
            raise self.error
        return OCRResult(lines=self.lines, tables=self.tables, raw_markdown=self.markdown)


class FakeArbiter:
    def __init__(self, answer):
        self.answer, self.crops = answer, None
        self.runtime_info = {}

    def read_regions(self, crops, context):
        self.crops = crops
        return {key: self.answer for key in crops}

    def recognize_page(self, image, context):
        return OCRResult(raw_markdown=self.answer)


def _ctx(tmp_path) -> Context:
    return Context(document_id="doc", page=3, output_dir=str(tmp_path))


def _verifier_line(text: str) -> Line:
    return Line(
        line_id="v1",
        text=text,
        bbox=BBox(x1=0.05, y1=0.05, x2=0.9, y2=0.1),
        geometry_provenance=GeometryProvenance.MEASURED,
    )


def test_selective_mode_clean_page_needs_no_second_reader_and_gets_measured_geometry(tmp_path):
    verifier, arbiter = FakeReader("unused"), FakeArbiter("unused")
    engine = VerifiedMistralOCREngine(
        FakeReader("\n".join(CLEAN_VN)), verifier, arbiter, verify_all_pages=False
    )
    result = engine.recognize_page(_page(["DIEU 4. YEU CAU CHAT LUONG VA NGHIEM THU", PARA, PARA_2]), _ctx(tmp_path))

    assert [line.text for line in result.lines] == CLEAN_VN
    assert verifier.calls == 0 and arbiter.crops is None
    heading, paragraph = result.lines
    assert heading.geometry_provenance == GeometryProvenance.MEASURED
    # The paragraph wraps over two visual lines: its box is their union.
    assert paragraph.geometry_provenance == GeometryProvenance.DERIVED
    assert paragraph.bbox.y2 > heading.bbox.y2
    assert not result.warnings


def test_critical_digits_confirmed_by_verifier_need_no_arbiter(tmp_path):
    verifier = FakeReader(MONEY, lines=[_verifier_line(MONEY)])
    arbiter = FakeArbiter("unused")
    engine = VerifiedMistralOCREngine(FakeReader(MONEY_VN), verifier, arbiter)
    result = engine.recognize_page(_page([MONEY]), _ctx(tmp_path))
    assert verifier.calls == 1
    assert arbiter.crops is None
    assert result.lines[0].text == MONEY_VN
    assert not result.warnings


@pytest.mark.parametrize(
    ("arbiter_reading", "expected_text", "expect_review"),
    [
        # arbiter agrees with the text reader: 2 of 3, keep it
        (MONEY_VN, MONEY_VN, False),
        # arbiter agrees with the verifier's digits: 2 of 3 against the text reader
        (MONEY_VN.replace("286", "236"), MONEY_VN.replace("286", "236"), False),
        # three different readings: never guess, flag for review
        (MONEY_VN.replace("286", "999"), MONEY_VN, True),
    ],
)
def test_digit_conflict_is_decided_by_blind_vote(tmp_path, arbiter_reading, expected_text, expect_review):
    verifier_text = MONEY.replace("286", "236")
    verifier = FakeReader(verifier_text, lines=[_verifier_line(verifier_text)])
    arbiter = FakeArbiter(arbiter_reading)
    engine = VerifiedMistralOCREngine(FakeReader(MONEY_VN), verifier, arbiter)
    result = engine.recognize_page(_page([MONEY]), _ctx(tmp_path))
    assert arbiter.crops is not None and len(arbiter.crops) == 1
    assert result.lines[0].text == expected_text
    flagged = any(w.startswith("needs_review:critical_field_conflict:") for w in result.warnings)
    assert flagged is expect_review


TRUTH_43 = (
    "4.3. Nghiệm thu căn cứ trên bộ mẫu hai bên thống nhất, biên bản kiểm tra và danh sách "
    "lỗi còn tồn tại tại thời điểm nghiệm thu."
)
READ_2512_43 = TRUTH_43.replace("tại tại thời", "tại thì")
READ_41_43 = (
    "4.3. Nghiem thu can cu trén bô mau hai bèn thong nhát, biên bàn kiém tra và dans sách "
    "lói còn tón tãi tói thói diém nghiem thu."
)
IMG_43 = [
    "4.3. Nghiem thu can cu tren bo mau hai ben thong nhat, bien ban kiem tra va danh sach",
    "loi con ton tai tai thoi diem nghiem thu.",
]


@pytest.mark.parametrize(
    ("arbiter_reading", "expected_text", "expect_review"),
    [
        (TRUTH_43, TRUTH_43, False),  # arbiter sides with the verifier's words
        (READ_2512_43, READ_2512_43, False),  # arbiter confirms the text reader
        (TRUTH_43.replace("tại tại thời", "vào lúc"), READ_2512_43, True),  # all differ
    ],
)
def test_valid_word_substitution_is_caught_by_the_always_on_second_reading(
    tmp_path, arbiter_reading, expected_text, expect_review
):
    verifier = FakeReader(READ_41_43, lines=[_verifier_line(READ_41_43)])
    arbiter = FakeArbiter(arbiter_reading)
    engine = VerifiedMistralOCREngine(FakeReader(READ_2512_43), verifier, arbiter)
    result = engine.recognize_page(_page(IMG_43), _ctx(tmp_path))
    assert verifier.calls == 1 and arbiter.crops is not None
    assert result.lines[0].text == expected_text
    flagged = any(w.startswith("needs_review:content_conflict:") for w in result.warnings)
    assert flagged is expect_review


def test_verifier_noise_alone_triggers_no_arbitration(tmp_path):
    garbled_41 = (
        "4.1. Két qua bàn giao phai dam bao khà nang truy vét t ur du lieu trich xuát vê trang, "
        "dong hoac vùng nguôn tuong ung trèn tai lieu."
    )
    verifier = FakeReader(garbled_41, lines=[_verifier_line(garbled_41)])
    arbiter = FakeArbiter("unused")
    engine = VerifiedMistralOCREngine(FakeReader(CLEAN_VN[1]), verifier, arbiter)
    result = engine.recognize_page(_page([PARA, PARA_2]), _ctx(tmp_path))
    assert verifier.calls == 1
    assert arbiter.crops is None
    assert result.lines[0].text == CLEAN_VN[1]
    assert not result.warnings


def test_misspelled_line_is_replaced_by_a_clean_blind_reading(tmp_path):
    arbiter = FakeArbiter(CLEAN_VN[1])
    engine = VerifiedMistralOCREngine(FakeReader(GARBLED), FakeReader("unused"), arbiter)
    result = engine.recognize_page(_page([PARA, PARA_2]), _ctx(tmp_path))
    assert result.lines[0].text == CLEAN_VN[1]
    assert not result.warnings


def test_misspelled_line_without_a_clean_alternative_is_flagged_not_guessed(tmp_path):
    engine = VerifiedMistralOCREngine(FakeReader(GARBLED), FakeReader("unused"), FakeArbiter(GARBLED))
    result = engine.recognize_page(_page([PARA, PARA_2]), _ctx(tmp_path))
    assert result.lines[0].text == GARBLED
    assert any(w.startswith("needs_review:spelling_unverified:") for w in result.warnings)


def test_text_reader_failure_falls_back_to_the_fallback_reader(tmp_path):
    fallback = FakeReader("\n".join(CLEAN_VN))
    engine = VerifiedMistralOCREngine(
        FakeReader(error=RuntimeError("402 insufficient credits")),
        FakeReader("unused"),
        FakeArbiter("unused"),
        fallback_reader=fallback,
    )
    result = engine.recognize_page(_page(["DIEU 4. YEU CAU", PARA, PARA_2]), _ctx(tmp_path))
    assert fallback.calls == 1
    assert [line.text for line in result.lines] == CLEAN_VN
    assert "ocr:text_reader_fallback:RuntimeError" in result.warnings


def test_footer_emitted_first_is_realigned_to_the_bottom_of_the_page(tmp_path):
    # Measured on the real scan: 2512 put page 4's footer above its header.
    footer = ["25/2026/HDDV-MH-TT", "Trang 4/12"]
    body = [CLEAN_VN[0], CLEAN_VN[1]]
    markdown = "\n".join(footer + body)
    image = _page(["DIEU 4. YEU CAU CHAT LUONG VA NGHIEM THU", PARA, PARA_2] + [""] * 20 + footer)
    engine = VerifiedMistralOCREngine(
        FakeReader(markdown), FakeReader("unused"), FakeArbiter("unused"), verify_all_pages=False
    )
    result = engine.recognize_page(image, _ctx(tmp_path))
    assert [line.text for line in result.lines] == body + footer
    assert result.lines[-1].bbox.y1 > result.lines[0].bbox.y2


@pytest.mark.parametrize(
    ("arbiter_name", "expect_review"),
    # The real case: under the seal the arbiter read "Thị" where the verifier read "Thu".
    [("Nguyễn Văn An", False), ("Nguyễn Văn Anh", True)],
)
def test_ink_the_text_reader_skipped_is_recovered_when_the_verifier_saw_it(
    tmp_path, arbiter_name, expect_review
):
    # Measured on the real scan: 2512 dropped the signer's name under the signature.
    text = "4.1. Ket qua ban giao phai dam bao kha nang truy vet tu du lieu trich xuat ve"
    verifier_md = f"{CLEAN_VN[1]}\nNguyễn Văn An"
    verifier = FakeReader(verifier_md, lines=[_verifier_line(CLEAN_VN[1])])
    arbiter = FakeArbiter(arbiter_name)
    engine = VerifiedMistralOCREngine(FakeReader(CLEAN_VN[1]), verifier, arbiter)
    result = engine.recognize_page(_page([text, PARA_2, "", "Nguyen Van An"]), _ctx(tmp_path))
    assert [line.text for line in result.lines] == [CLEAN_VN[1], arbiter_name]
    assert "ocr:recovered_unread_ink:1" in result.warnings
    flagged = any(w.startswith("needs_review:recovered_text_unconfirmed:") for w in result.warnings)
    assert flagged is expect_review


def test_skipped_ink_is_not_reread_when_the_verifier_saw_nothing_extra(tmp_path):
    verifier = FakeReader(CLEAN_VN[1], lines=[_verifier_line(CLEAN_VN[1])])
    arbiter = FakeArbiter("anything")
    engine = VerifiedMistralOCREngine(FakeReader(CLEAN_VN[1]), verifier, arbiter)
    result = engine.recognize_page(_page([PARA, PARA_2, "", "some stray scribble"]), _ctx(tmp_path))
    assert arbiter.crops is None
    assert [line.text for line in result.lines] == [CLEAN_VN[1]]


def test_bordered_table_takes_real_cell_boxes_from_its_grid(tmp_path):
    markdown = "\n".join(
        [
            "PHỤ LỤC 01 - ĐƠN GIÁ",
            "| A | B | C |",
            "| --- | --- | --- |",
            "| a1 | b1 | c1 |",
            "| a2 | b2 | c2 |",
        ]
    )
    engine = VerifiedMistralOCREngine(FakeReader(markdown), FakeReader("unused"), FakeArbiter("unused"))
    result = engine.recognize_page(_page(["PHU LUC 01 - DON GIA"], grid=True), _ctx(tmp_path))
    assert len(result.tables) == 1
    table = result.tables[0]
    assert table.header == ["A", "B", "C"]
    assert [[cell.text for cell in row.cells] for row in table.rows] == [["a1", "b1", "c1"], ["a2", "b2", "c2"]]
    assert all(cell.geometry_provenance == GeometryProvenance.DERIVED for row in table.rows for cell in row.cells)
    assert table.heading_before == "PHỤ LỤC 01 - ĐƠN GIÁ"
    # table rows stay in the line stream, positioned on their grid row
    row_lines = [line for line in result.lines if line.text.startswith("|")]
    assert len(row_lines) == 3 and all(line.bbox is not None for line in row_lines)
