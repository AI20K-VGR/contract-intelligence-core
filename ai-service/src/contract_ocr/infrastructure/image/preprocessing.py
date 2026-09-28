import cv2
import numpy as np

from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import Line

STEPS = {
    "orientation90",
    "orientation180",
    "orientation270",
    "deskew",
    "grayscale",
    "contrast",
    "denoise",
    "threshold",
}


def validate_steps(steps: list[str]) -> None:
    unknown = set(steps) - STEPS
    if unknown or len(steps) != len(set(steps)):
        raise ValueError(f"invalid or repeated preprocessing steps: {steps}")
    if sum(s.startswith("orientation") for s in steps) > 1:
        raise ValueError("choose only one orientation correction")


def gray(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if image.ndim == 3 else image


def rotate(image: np.ndarray, angle: float) -> tuple[np.ndarray, np.ndarray]:
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
    new_width, new_height = (
        int(np.ceil(height * sin + width * cos)),
        int(np.ceil(height * cos + width * sin)),
    )
    matrix[0, 2] += (new_width - width) / 2
    matrix[1, 2] += (new_height - height) / 2
    result = cv2.warpAffine(image, matrix, (new_width, new_height), borderValue=(255, 255, 255))
    return result, np.vstack([matrix, [0, 0, 1]])


class ImagePreprocessor:
    def apply(self, image: np.ndarray, steps: list[str]) -> tuple[np.ndarray, np.ndarray]:
        validate_steps(steps)
        result, transform = image.copy(), np.eye(3)
        for step in steps:
            if step.startswith("orientation"):
                result, matrix = rotate(result, int(step.removeprefix("orientation")))
                transform = matrix @ transform
            elif step == "deskew":
                edges = cv2.Canny(gray(result), 50, 150)
                lines = cv2.HoughLinesP(
                    edges,
                    1,
                    np.pi / 1800,
                    threshold=80,
                    minLineLength=max(30, result.shape[1] // 10),
                    maxLineGap=20,
                )
                angles = (
                    []
                    if lines is None
                    else [
                        np.degrees(np.arctan2(y2 - y1, x2 - x1)) for x1, y1, x2, y2 in lines[:, 0]
                    ]
                )
                angles = [a for a in angles if abs(a) <= 10]
                if angles:
                    result, matrix = rotate(result, float(np.median(angles)))
                    transform = matrix @ transform
            elif step == "grayscale":
                result = gray(result)
            elif step == "contrast":
                result = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray(result))
            elif step == "denoise":
                result = cv2.fastNlMeansDenoising(gray(result), None, 10, 7, 21)
            elif step == "threshold":
                result = cv2.adaptiveThreshold(
                    gray(result), 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
                )
        return result, transform

    def restore(
        self, lines: list[Line], transform: np.ndarray, shape: tuple, original_shape: tuple
    ) -> None:
        """Inverse-map all four box corners to the original rendered-page frame."""
        inverse = np.linalg.inv(transform)
        height, width = shape[:2]
        for line in lines:
            for item in [line, *line.words]:
                if item.bbox is not None:
                    box = item.bbox
                    item.bbox = restore_pixel_bbox(
                        (box.x1 * width, box.y1 * height, box.x2 * width, box.y2 * height),
                        inverse,
                        original_shape,
                    )


def restore_pixel_bbox(
    pixel_box: tuple[float, float, float, float],
    inverse_transform: np.ndarray,
    original_shape: tuple,
) -> BBox:
    """Inverse-map one pixel-space `(x0, y0, x1, y1)` box (in whatever frame
    `inverse_transform` was built from) back into a bbox normalized against
    `original_shape`. Shared by `ImagePreprocessor.restore` (lines/words, converting
    from their own normalized frame first) and table-grid cell geometry, which is
    already pixel-space and has no `Line` object to hang it on."""
    x0, y0, x1, y1 = pixel_box
    points = np.array([[x0, y0, 1], [x1, y0, 1], [x1, y1, 1], [x0, y1, 1]]) @ inverse_transform.T
    return BBox.normalize(
        [points[:, 0].min(), points[:, 1].min(), points[:, 0].max(), points[:, 1].max()],
        original_shape[1],
        original_shape[0],
    )
