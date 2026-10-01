import cv2
import numpy as np

from .preprocessing import rotate

VARIANTS = [
    "rotation+2",
    "rotation-2",
    "rotation+5",
    "rotation-5",
    "blur_mild",
    "blur_medium",
    "blur_strong",
    "motion_blur",
    "low_contrast",
    "brightness_dark",
    "brightness_light",
    "jpeg70",
    "jpeg50",
    "jpeg30",
    "gaussian_noise",
    "salt_pepper",
    "dpi300",
    "dpi200",
    "dpi150",
]


def degrade(image: np.ndarray, variant: str, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    rng, matrix = np.random.default_rng(seed), np.eye(3)
    if variant.startswith("rotation"):
        return rotate(image, float(variant.removeprefix("rotation")))
    if variant.startswith("blur_"):
        sigma = {"blur_mild": 1.0, "blur_medium": 2.0, "blur_strong": 3.5}[variant]
        result = cv2.GaussianBlur(image, (0, 0), sigma)
    elif variant == "motion_blur":
        kernel = np.zeros((15, 15))
        kernel[7, :] = 1 / 15
        result = cv2.filter2D(image, -1, kernel)
    elif variant == "low_contrast":
        result = np.clip(128 + (image.astype(float) - 128) * 0.35, 0, 255).astype(np.uint8)
    elif variant.startswith("brightness_"):
        result = np.clip(
            image.astype(float) + (45 if variant.endswith("light") else -45), 0, 255
        ).astype(np.uint8)
    elif variant.startswith("jpeg"):
        ok, encoded = cv2.imencode(
            ".jpg",
            cv2.cvtColor(image, cv2.COLOR_RGB2BGR),
            [cv2.IMWRITE_JPEG_QUALITY, int(variant[4:])],
        )
        if not ok:
            raise RuntimeError("JPEG encoding failed")
        result = cv2.cvtColor(cv2.imdecode(encoded, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    elif variant == "gaussian_noise":
        result = np.clip(image.astype(float) + rng.normal(0, 15, image.shape), 0, 255).astype(
            np.uint8
        )
    elif variant == "salt_pepper":
        mask = rng.random(image.shape[:2])
        result = image.copy()
        result[mask < 0.01] = 0
        result[mask > 0.99] = 255
    elif variant.startswith("dpi"):
        scale = int(variant[3:]) / 300
        result = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        matrix[0, 0], matrix[1, 1] = (
            result.shape[1] / image.shape[1],
            result.shape[0] / image.shape[0],
        )
    else:
        raise ValueError(f"unknown degradation: {variant}")
    return result, matrix
