"""The adapter interface, and the small pluggable engine seams inside it.

`WordSource` is the only interface `table_reconstruct` or a caller needs to
know about — `NativeAdapter`, `OcrAdapter` and `VisionAdapter` all implement
it and are interchangeable. `LineDetector`/`TextRecognizer`/`VisionClient`
are narrower Protocols used internally by `OcrAdapter`/`VisionAdapter` so
their real (PaddleOCR/VietOCR/OpenAI) backends can be swapped for a fake in
tests, the same way `reconstruction.llm_resolver.BoundaryLLMResolver` keeps
that pipeline free of a hard vendor-SDK dependency.
"""

from __future__ import annotations

from typing import Any, Protocol

from contract_ocr.table_reconstruct.types import Bbox, Word

from .types import Region


class WordSource(Protocol):
    def extract(self, page_img_or_pdf: Any, region: Region) -> list[Word]: ...


class LineDetector(Protocol):
    """Text-LINE detection only — no recognition. Returns each detected
    line's bbox, in the same coordinate space as the image it was given."""

    def detect(self, image: Any) -> list[Bbox]: ...


class TextRecognizer(Protocol):
    """Reads the text inside one already-cropped image."""

    def recognize(self, crop: Any) -> str: ...


class VisionClient(Protocol):
    """Sends one or more images plus a prompt to a vision-capable LLM and
    returns its raw text response (JSON text when `json_mode=True`, plain
    transcribed text otherwise). Never returns coordinates — callers of
    `VisionClient` never ask for any and never trust it if it appeared."""

    def complete(
        self, *, images: list[Any], system_prompt: str, user_prompt: str, json_mode: bool
    ) -> str: ...
