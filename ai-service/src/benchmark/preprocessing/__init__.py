from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from contract_ocr.infrastructure.image.preprocessing import ImagePreprocessor


def preprocess(source: Path, target: Path, steps: list[str]) -> Path:
    """Create one immutable image for a Mistral benchmark experiment."""
    target.parent.mkdir(parents=True, exist_ok=True)
    image = np.asarray(Image.open(source).convert("RGB"))
    result, _ = ImagePreprocessor().apply(image, steps)
    Image.fromarray(result).save(target, format="PNG")
    return target
