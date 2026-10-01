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


def test_a_clean_scan_rendered_finer_than_it_was_scanned_is_not_blur():
    # Rendering a 150 DPI scan at 300 DPI only enlarges it: soft edges in
    # pixel terms, same sharpness once measured back at 150 DPI.
    enlarged = cv2.resize(_page(), (WIDTH * 2, HEIGHT * 2), interpolation=cv2.INTER_LINEAR)
    assert assess(enlarged, dpi=300) == []
    blurred = cv2.resize(degrade(_page(), "blur_mild")[0], (WIDTH * 2, HEIGHT * 2))
    assert "blur" in assess(blurred, dpi=300)


def _specks(image: np.ndarray, per_megapixel: float, shade: int) -> np.ndarray:
    rng = np.random.default_rng(7)
    count = int(per_megapixel * image.shape[0] * image.shape[1] / 1e6)
    ys = rng.integers(20, image.shape[0] - 20, count)
    xs = rng.integers(20, image.shape[1] - 20, count)
    image[ys, xs] = shade
    return image


def test_speckle_is_tolerated_longer_when_the_ink_contrast_is_good():
    # Dark ink, ~600 dots/MP: the dirty-but-readable `scanned_bad` case.
    assert assess(_specks(_page(), 600, 20)) == []
    # The same dots on a pale scan are flagged.
    pale = np.full((HEIGHT, WIDTH, 3), 245, dtype=np.uint8)
    for row in range(30):
        cv2.putText(
            pale,
            f"Dieu {row + 1}. Ben A thanh toan",
            (90, 120 + row * 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (85, 85, 85),
            2,
        )
    assert "speckle" in assess(_specks(pale, 600, 85))


def test_a_page_with_almost_no_ink_is_not_judged():
    image = np.full((HEIGHT, WIDTH, 3), 245, dtype=np.uint8)
    cv2.putText(image, "Trang 3", (1000, 1700), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 1)
    blurred = cv2.GaussianBlur(image, (0, 0), 3)
    assert measure(blurred) is None
    assert assess(blurred) == []
