"""Public canonical output contract; domain entities are also Pydantic schemas."""

from contract_ocr.domain.entities import Document, Line, Page, Word

__all__ = ["Document", "Line", "Page", "Word"]
