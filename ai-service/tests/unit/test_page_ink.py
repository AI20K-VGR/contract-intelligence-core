import cv2
import numpy as np

from contract_ocr.domain.bbox import BBox
from contract_ocr.infrastructure.image.page_ink import is_blank, unexplained_lines

WIDTH, HEIGHT = 1240, 1754  # A4 at 150 DPI


def _sheet(paper: int = 245) -> np.ndarray:
    return np.full((HEIGHT, WIDTH, 3), paper, dtype=np.uint8)


def _text(image: np.ndarray, text: str, y: int, *, shade: int = 0, x: int = 120) -> np.ndarray:
    cv2.putText(image, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (shade,) * 3, 2)
    return image


def test_white_sheet_is_blank():
    assert is_blank(_sheet())


def test_dust_and_edge_shadow_do_not_make_a_scan_non_blank():
    image = _sheet()
    rng = np.random.default_rng(0)
    for y, x in zip(rng.integers(100, HEIGHT - 100, 60), rng.integers(100, WIDTH - 100, 60)):
        image[y : y + 2, x : x + 2] = 30
    image[:, :15] = 40  # scanner shadow along the left edge
    assert is_blank(image)


def test_a_single_printed_digit_is_not_blank():
    assert not is_blank(_text(_sheet(), "5", HEIGHT // 2, x=WIDTH // 2))


def test_faded_text_is_ink_but_show_through_is_not():
    assert not is_blank(_text(_sheet(), "Dieu 1. Pham vi", 400, shade=170))
    assert is_blank(_text(_sheet(), "Dieu 1. Pham vi", 400, shade=215))


def test_lines_outside_the_native_text_are_unexplained():
    image = _text(_text(_sheet(), "PHU LUC 01", 200), "Text drawn as vector outlines", 700)
    heading = BBox(x1=110 / WIDTH, y1=180 / HEIGHT, x2=300 / WIDTH, y2=205 / HEIGHT)
    missing = unexplained_lines(image, [heading])
    assert len(missing) == 1 and 680 <= missing[0].y1 <= 710
    assert unexplained_lines(_text(_sheet(), "PHU LUC 01", 200), [heading]) == []
