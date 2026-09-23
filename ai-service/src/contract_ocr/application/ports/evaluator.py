from typing import Protocol


class Evaluator(Protocol):
    def text(self, reference: str, hypothesis: str) -> dict: ...
