import cv2
import numpy as np
import pytest

from contract_ocr.infrastructure.image.degradation import degrade
from contract_ocr.infrastructure.image.page_quality import assess, measure

WIDTH, HEIGHT = 1240, 1754  # A4 at 150 DPI, the backend render default


def _page() -> np.ndarray:
    image = np.full((HEIGHT, WIDTH, 3), 245, dtype=np.uint8)
    for row in range(30):
        cv2.putText(
            image,
            f"Dieu {row + 1}. Ben A thanh toan 1.286.400.000 dong trong 15 ngay",
            (90, 120 + row * 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (20, 20, 20),
            2,
        )
    return image


def test_a_clean_scan_passes():
    assert assess(_page()) == []


@pytest.mark.parametrize(
    ("variant", "reason"),
    [
        ("blur_mild", "blur"),
        ("blur_strong", "blur"),
        ("low_contrast", "low_contrast"),
        ("gaussian_noise", "noise"),
        ("salt_pepper", "speckle"),
    ],
)
def test_each_degradation_is_named(variant, reason):
    degraded, _ = degrade(_page(), variant)
    assert reason in assess(degraded)


def test_a_low_resolution_scan_scaled_up_reads_as_blur():
    page = _page()
    small = cv2.resize(page, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    assert "blur" in assess(cv2.resize(small, (WIDTH, HEIGHT)))


def test_mild_jpeg_and_brightness_changes_are_not_flagged():
    for variant in ("jpeg50", "brightness_dark", "brightness_light"):
        assert assess(degrade(_page(), variant)[0]) == [], variant


def test_a_page_with_almost_no_ink_is_not_judged():
    image = np.full((HEIGHT, WIDTH, 3), 245, dtype=np.uint8)
    cv2.putText(image, "Trang 3", (1000, 1700), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 1)
    blurred = cv2.GaussianBlur(image, (0, 0), 3)
    assert measure(blurred) is None
    assert assess(blurred) == []
