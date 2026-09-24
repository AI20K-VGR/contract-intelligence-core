"""Extraction bounded context — interfaces (HTTP layer)."""

from contract_intelligence.extraction.interfaces.api.dependencies import (
    ExtractionServiceDep,
    get_extraction_service,
)
from contract_intelligence.extraction.interfaces.api.dependencies_reocr import (
    ReOcrServiceDep,
    get_reocr_service,
)
from contract_intelligence.extraction.interfaces.api.routers.extraction_full_router import (
    router as extraction_full_router,
)
from contract_intelligence.extraction.interfaces.api.routers.reocr_router import (
    router as reocr_router,
)

__all__ = [
    "ExtractionServiceDep",
    "ReOcrServiceDep",
    "extraction_full_router",
    "get_extraction_service",
    "get_reocr_service",
    "reocr_router",
]
