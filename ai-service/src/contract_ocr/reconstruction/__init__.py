"""Document reconstruction: turn independently-OCR'd pages into one logical
document structure (clause tree + tables), without re-OCRing anything or
rewriting a single word of the contract.

Public API:
    reconstruct_document(pages) -> ReconstructedDocument
    resolve_boundary(previous_page, next_page) -> ReconstructionAction

See README.md in this package for the full pipeline diagram, and the
Document Reconstruction Agent specification for `Action`/`Relationship`/
`ReasonCode`/`ReconstructionAction`'s exact shape.
"""

from .llm_resolver import BoundaryLLMResolver, MockLLMResolver, OpenAIBoundaryResolver
from .models import (
    Action,
    BoundaryContext,
    ClauseMarker,
    DocumentState,
    EntityType,
    ReasonCode,
    ReconstructionAction,
    ReconstructionTarget,
    Relationship,
    ResolutionMethod,
    ScoreBreakdown,
    SourceBlockRef,
)
from .pipeline import reconstruct_document, resolve_boundary
from .schemas.block import Block
from .schemas.document import (
    Clause,
    DocumentMetadata,
    ReconstructedDocument,
    ReconstructionInfo,
    ReviewItem,
    Table,
    TableRow,
)
from .schemas.page import Page

__all__ = [
    "reconstruct_document",
    "resolve_boundary",
    "Block",
    "Page",
    "Clause",
    "DocumentMetadata",
    "ReconstructedDocument",
    "ReconstructionInfo",
    "ReviewItem",
    "Table",
    "TableRow",
    "Action",
    "BoundaryContext",
    "ClauseMarker",
    "DocumentState",
    "EntityType",
    "ReasonCode",
    "ReconstructionAction",
    "ReconstructionTarget",
    "Relationship",
    "ResolutionMethod",
    "ScoreBreakdown",
    "SourceBlockRef",
    "BoundaryLLMResolver",
    "MockLLMResolver",
    "OpenAIBoundaryResolver",
]
