from contract_ocr.domain.entities import Evidence
from contract_ocr.domain.enums import InputType


class PdfPageClassifier:
    """A usable text layer wins routing; MIXED describes text plus substantial imagery."""

    def __init__(
        self, min_chars: int = 20, min_words: int = 3, image_threshold: float = 0.5
    ) -> None:
        if min_chars < 0 or min_words < 0 or not 0 <= image_threshold <= 1:
            raise ValueError("invalid classifier thresholds")
        self.min_chars, self.min_words, self.image_threshold = min_chars, min_words, image_threshold

    def classify(
        self, page: int, text_length: int, word_count: int, span_count: int, image_coverage: float
    ) -> Evidence:
        usable = text_length >= self.min_chars and word_count >= self.min_words and span_count > 0
        kind = InputType.TEXT_LAYER if usable else InputType.SCANNED
        if text_length > 0 and image_coverage >= self.image_threshold:
            kind = InputType.MIXED
        return Evidence(
            page=page,
            input_type=kind,
            native_word_count=word_count,
            native_text_length=text_length,
            native_span_count=span_count,
            image_coverage_ratio=image_coverage,
            usable_text=usable,
        )
