from enum import StrEnum
from uuid import uuid4


def uid() -> str:
    return str(uuid4())


class Disposition(StrEnum):
    MATCH = "comparable_match"
    DIFFERENCE = "comparable_difference"
    AMENDMENT = "candidate_amendment"
    NOT_COMPARABLE = "not_comparable"
    INSUFFICIENT = "insufficient_evidence"


class DomainError(Exception):
    def __init__(self, code: str, status: int = 409):
        self.code = code
        self.status = status


def require(condition: bool, code: str, status: int = 409) -> None:
    if not condition:
        raise DomainError(code, status)
