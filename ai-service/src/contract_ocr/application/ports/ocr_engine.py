from abc import ABC, abstractmethod
from typing import Any

from contract_ocr.domain.entities import Context, OCRResult


class EngineUnavailable(RuntimeError):
    """Optional dependency, hardware or model is unavailable."""


class OCREngine(ABC):
    name: str
    model: str
    initialization_ms: float = 0
    runtime_info: dict[str, Any]

    @abstractmethod
    def recognize_page(self, page_image: Any, context: Context) -> OCRResult: ...
