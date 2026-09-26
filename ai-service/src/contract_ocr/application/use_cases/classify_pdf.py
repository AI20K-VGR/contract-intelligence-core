from contract_ocr.domain.entities import Evidence
from contract_ocr.domain.enums import InputType
from contract_ocr.word_adapters.text_quality import garbage_char_ratio


class PdfPageClassifier:
    """Routes a page to native extraction, full OCR, or native+OCR (MIXED).

    A usable, non-garbled native text layer is necessary for the native-only fast
    path, but it is not sufficient: a page can have perfectly good text *and* a
    large embedded image the text layer says nothing about (a signed/stamped page
    photographed and re-inserted next to its own transcript, a watermark scan,
    etc.). Section 3's rule is that `has_text_layer == true` must never by itself
    decide routing — `requires_ocr_regions` is the flag callers must check instead
    of `usable_text` alone; it is set for MIXED pages too, not only unusable ones.
    """

    def __init__(
        self,
        min_chars: int = 20,
        min_words: int = 3,
        image_threshold: float = 0.5,
        garbled_threshold: float = 0.15,
    ) -> None:
        if (
            min_chars < 0
            or min_words < 0
            or not 0 <= image_threshold <= 1
            or not 0 <= garbled_threshold <= 1
        ):
            raise ValueError("invalid classifier thresholds")
        self.min_chars = min_chars
        self.min_words = min_words
        self.image_threshold = image_threshold
        self.garbled_threshold = garbled_threshold

    def classify(
        self,
        page: int,
        text_length: int,
        word_count: int,
        span_count: int,
        image_coverage: float,
        text_sample: str = "",
    ) -> Evidence:
        reason_codes: list[str] = []
        length_ok = text_length >= self.min_chars
        words_ok = word_count >= self.min_words
        spans_ok = span_count > 0
        if not length_ok:
            reason_codes.append("TEXT_TOO_SHORT")
        if not words_ok:
            reason_codes.append("TOO_FEW_WORDS")
        if not spans_ok:
            reason_codes.append("NO_TEXT_SPANS")

        # A garbled text layer (legacy TCVN3/VNI encoding, mojibake) can satisfy the
        # length/word/span thresholds above with content that isn't real text at
        # all; it must not be trusted as a usable native source.
        garbled_ratio = garbage_char_ratio(text_sample) if text_sample else 0.0
        garbled = garbled_ratio >= self.garbled_threshold
        if garbled:
            reason_codes.append("GARBLED_TEXT_LAYER")

        usable = length_ok and words_ok and spans_ok and not garbled
        heavy_image = image_coverage >= self.image_threshold

        if usable and heavy_image:
            kind = InputType.MIXED
            requires_ocr_regions = True
            reason_codes.append("TEXT_LAYER_WITH_HEAVY_IMAGE_OVERLAY")
        elif usable:
            kind = InputType.TEXT_LAYER
            requires_ocr_regions = False
            reason_codes.append("NATIVE_TEXT_USABLE")
        else:
            kind = InputType.SCANNED
            requires_ocr_regions = True
            if spans_ok and text_length > 0 and not garbled and image_coverage == 0:
                # Too little text to trust on counts alone ("PHỤ LỤC 01"), but clean
                # and with no image beside it: ProcessDocument checks the rendered
                # page for ink the text layer does not cover before paying for OCR.
                reason_codes.append("SHORT_NATIVE_TEXT")
            if not reason_codes:
                reason_codes.append("NO_USABLE_NATIVE_TEXT")

        return Evidence(
            page=page,
            input_type=kind,
            native_word_count=word_count,
            native_text_length=text_length,
            native_span_count=span_count,
            image_coverage_ratio=image_coverage,
            usable_text=usable,
            garbled_text_ratio=garbled_ratio,
            requires_ocr_regions=requires_ocr_regions,
            reason_codes=reason_codes,
        )
