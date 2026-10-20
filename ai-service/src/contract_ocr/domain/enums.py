from enum import StrEnum


class InputType(StrEnum):
    TEXT_LAYER = "TEXT_LAYER"
    SCANNED = "SCANNED"
    MIXED = "MIXED"


class Status(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class GeometryProvenance(StrEnum):
    """How a bbox was obtained — never inferred from the bbox itself downstream.

    MEASURED: directly measured by deterministic OCR/layout processing (native PDF
        glyph rects; a CV text-detector's own output, e.g. PaddleOCR's polygons).
    DERIVED: calculated from other trusted geometry (e.g. a line bbox that is the
        union of its own measured word boxes; a clause bbox unioning line boxes).
    CLAIMED: a coordinate supplied by a model (e.g. a vision LLM). Must never be
        silently promoted to MEASURED or DERIVED, and must never be produced by
        asking a model for coordinates in the first place (see word_adapters.vision,
        which assigns vision-transcribed words the caller-known crop/cell bbox
        instead of trusting any coordinate the model returns).
    """

    MEASURED = "MEASURED"
    DERIVED = "DERIVED"
    CLAIMED = "CLAIMED"
