import cv2
import numpy as np

from contract_ocr.infrastructure.image.line_geometry import (
    LineBox,
    column_major_variant,
    detect_text_lines,
)


def _render(lines: list[tuple[int, int, str]], *, color=(0, 0, 0)) -> np.ndarray:
    image = np.full((900, 1200, 3), 255, dtype=np.uint8)
    for x, y, text in lines:
        cv2.putText(image, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    return image


def test_each_visual_line_becomes_one_box_in_reading_order():
    image = _render([(60, 100, "First line of the clause"), (60, 150, "second line"), (60, 250, "Next")])
    boxes = detect_text_lines(image)
    assert len(boxes) == 3
    assert [b.y0 for b in boxes] == sorted(b.y0 for b in boxes)


def test_long_rules_are_not_text():
    image = _render([(60, 100, "Heading")])
    cv2.line(image, (40, 130), (1160, 130), (0, 0, 0), 2)
    assert len(detect_text_lines(image)) == 1


def test_red_seal_ink_is_ignored_so_it_cannot_swallow_a_name():
    image = _render([(60, 100, "Tran Thu Binh")])
    cv2.circle(image, (200, 90), 80, (200, 20, 20), 6)  # RGB red seal ring over the name
    boxes = detect_text_lines(image)
    assert len(boxes) == 1 and boxes[0].height < 60


def _b(x0: int, y0: int, width: int = 200) -> LineBox:
    return LineBox(x0, y0, x0 + width, y0 + 20)


def test_signature_block_reads_down_each_column():
    left_head, right_head = _b(100, 100), _b(700, 100)
    left_note, right_note = _b(100, 130), _b(700, 130)
    left_name = _b(110, 220)  # lone signer name under the left column
    footer = _b(100, 850)
    boxes = [left_head, right_head, left_note, right_note, left_name, footer]
    assert column_major_variant(boxes) == [
        left_head, left_note, left_name, right_head, right_note, footer
    ]


def test_single_column_page_has_no_column_variant():
    assert column_major_variant([_b(100, 100), _b(100, 130), _b(100, 160)]) is None
