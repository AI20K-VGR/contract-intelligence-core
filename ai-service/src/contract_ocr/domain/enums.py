from enum import StrEnum


class InputType(StrEnum):
    TEXT_LAYER = "TEXT_LAYER"
    SCANNED = "SCANNED"
    MIXED = "MIXED"


class Status(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
