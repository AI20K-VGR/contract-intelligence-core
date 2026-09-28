"""Internal domain models shared across the reconstruction pipeline.

These mirror the Document Reconstruction Agent specification name-for-name:
`Action`, `Relationship`, `EntityType` and `ReasonCode` are its enums, and
`ReconstructionAction` is its section-15 JSON schema (plus a couple of
internal-only bookkeeping fields — `method` and `scores` — that the agent
itself never emits; they are added when this codebase wraps the agent's raw
JSON, not part of what the LLM is asked to produce).

`schemas/` holds the separate external input/output JSON contracts (the
page/block OCR input, and `document_structure.json` output) — this module
is what the algorithm reasons about internally between those two.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from .schemas.block import Block


class Action(str, Enum):
    """What the deterministic executor should do (section 3). The agent
    only ever proposes one of these — it never performs the mutation
    itself: "LLM decides relationship. Code performs mutation." (section 1)
    """

    NO_ACTION = "NO_ACTION"
    MERGE_BLOCKS = "MERGE_BLOCKS"
    CONTINUE_CLAUSE = "CONTINUE_CLAUSE"
    NEW_CLAUSE = "NEW_CLAUSE"
    NEW_SECTION = "NEW_SECTION"
    NEW_PARAGRAPH = "NEW_PARAGRAPH"
    ATTACH_CHILD = "ATTACH_CHILD"
    CONTINUE_LIST = "CONTINUE_LIST"
    MERGE_TABLE = "MERGE_TABLE"
    CONTINUE_TABLE = "CONTINUE_TABLE"
    CONTINUE_ROW = "CONTINUE_ROW"
    IGNORE_HEADER = "IGNORE_HEADER"
    IGNORE_FOOTER = "IGNORE_FOOTER"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class Relationship(str, Enum):
    """The classified relationship between the end of page N and the start
    of page N+1 (section 4)."""

    CONTINUE_PARAGRAPH = "CONTINUE_PARAGRAPH"
    NEW_PARAGRAPH = "NEW_PARAGRAPH"
    CONTINUE_CLAUSE = "CONTINUE_CLAUSE"
    NEW_CLAUSE = "NEW_CLAUSE"
    NEW_SECTION = "NEW_SECTION"
    LIST_CONTINUE = "LIST_CONTINUE"
    TABLE_CONTINUE = "TABLE_CONTINUE"
    ROW_CONTINUE = "ROW_CONTINUE"
    UNKNOWN = "UNKNOWN"


class EntityType(str, Enum):
    """What kind of structural entity a `ReconstructionAction` concerns."""

    SECTION = "SECTION"
    CLAUSE = "CLAUSE"
    PARAGRAPH = "PARAGRAPH"
    LIST_ITEM = "LIST_ITEM"
    TABLE = "TABLE"
    TABLE_ROW = "TABLE_ROW"
    HEADER = "HEADER"
    FOOTER = "FOOTER"


class ResolutionMethod(str, Enum):
    """Internal bookkeeping: which resolver produced the action. Not part
    of the agent's own JSON output — used for logging (section 18) only."""

    RULE = "RULE"
    LLM = "LLM"
    HUMAN = "HUMAN"


class ReasonCode(str, Enum):
    """Only these codes may ever be attached to a `ReconstructionAction`
    (section 12) — concise machine-readable evidence, never free-form
    chain-of-thought."""

    BOTTOM_TO_TOP = "BOTTOM_TO_TOP"
    NO_END_PUNCTUATION = "NO_END_PUNCTUATION"
    HAS_END_PUNCTUATION = "HAS_END_PUNCTUATION"
    NEW_NUMBERING = "NEW_NUMBERING"
    NUMBERING_SEQUENCE = "NUMBERING_SEQUENCE"
    SAME_INDENTATION = "SAME_INDENTATION"
    DIFFERENT_INDENTATION = "DIFFERENT_INDENTATION"
    SAME_STYLE = "SAME_STYLE"
    NEW_HEADING = "NEW_HEADING"
    SAME_ACTIVE_CLAUSE = "SAME_ACTIVE_CLAUSE"

    TABLE_COLUMN_MATCH = "TABLE_COLUMN_MATCH"
    TABLE_HEADER_MATCH = "TABLE_HEADER_MATCH"
    TABLE_LAYOUT_MATCH = "TABLE_LAYOUT_MATCH"
    INCOMPLETE_TABLE_ROW = "INCOMPLETE_TABLE_ROW"
    REPEATED_TABLE_HEADER = "REPEATED_TABLE_HEADER"

    LIST_SEQUENCE = "LIST_SEQUENCE"

    REPEATED_HEADER = "REPEATED_HEADER"
    REPEATED_FOOTER = "REPEATED_FOOTER"

    LOW_OCR_CONFIDENCE = "LOW_OCR_CONFIDENCE"
    AMBIGUOUS_STRUCTURE = "AMBIGUOUS_STRUCTURE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ClauseMarker(BaseModel):
    """A parsed clause/numbering marker, e.g. "5.2.1" or "(a)"."""

    model_config = ConfigDict(extra="forbid")

    raw: str
    normalized: str
    level_hint: int | None
    marker_type: str


class SourceBlockRef(BaseModel):
    """A pointer back to the exact raw OCR span a piece of text came from
    (section 11). `block_id` identifies a plain block; a table reference
    instead carries `table_id`/`row_id`/(optionally) `cell_id` and no
    `block_id` of its own."""

    model_config = ConfigDict(extra="forbid")

    page: int
    block_id: str | None = None
    bbox: tuple[float, float, float, float] | None = None
    table_id: str | None = None
    row_id: str | None = None
    cell_id: str | None = None
    char_start: int | None = None
    char_end: int | None = None


class DocumentState(BaseModel):
    """The reconstruction pipeline's live hierarchy state (section 2,
    section 6): which section/clause/list/table is currently open. `None`
    means nothing of that kind is open yet."""

    model_config = ConfigDict(extra="forbid")

    active_section: str | None = None
    active_clause: str | None = None
    active_list: str | None = None
    active_table: str | None = None


class ReconstructionTarget(BaseModel):
    """Where a reconstruction action attaches, when applicable (section 6,
    section 16)."""

    model_config = ConfigDict(extra="forbid")

    node_id: str | None = None
    parent_id: str | None = None
    table_id: str | None = None


class BoundaryContext(BaseModel):
    """The small, page-boundary-local slice handed to the rule engine / LLM
    (section 2) — including the live `document_state` so both can reason
    about whether the next block attaches to the clause/list/table that is
    currently open, not just about the two blocks in isolation."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    document_state: DocumentState
    previous_page: int
    previous_page_height: float
    next_page: int
    next_page_height: float
    previous_blocks: list[Block]
    next_blocks: list[Block]


class ScoreBreakdown(BaseModel):
    """The independent signals a confidence value blends (section 13): the
    agent's own confidence is only one of these, never trusted alone."""

    model_config = ConfigDict(extra="forbid")

    rule_score: float = Field(default=0.0, ge=0, le=1)
    layout_score: float = Field(default=0.0, ge=0, le=1)
    numbering_score: float = Field(default=0.0, ge=0, le=1)
    text_continuity_score: float = Field(default=0.0, ge=0, le=1)
    model_score: float = Field(default=0.0, ge=0, le=1)


class ReconstructionAction(BaseModel):
    """The agent's proposed action — section 15's JSON schema.

    `method`, `scores` and `possible_relationships` are this codebase's own
    bookkeeping (which resolver produced it, why, and — when
    `requires_review` is true — what it was torn between). They are not
    part of the wire schema the LLM itself is prompted to return (see
    `llm_resolver.SYSTEM_PROMPT`); they are attached when this codebase
    wraps the agent's raw JSON into this model.
    """

    model_config = ConfigDict(extra="forbid")

    action: Action
    # `None` for actions with no cross-page boundary relationship to speak
    # of — IGNORE_HEADER/IGNORE_FOOTER classify a single block, not a
    # relationship between two pages.
    relationship: Relationship | None
    entity_type: EntityType
    source_blocks: list[SourceBlockRef]
    target: ReconstructionTarget | None = None
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    requires_review: bool = False

    method: ResolutionMethod = ResolutionMethod.RULE
    scores: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    possible_relationships: list[Relationship] = Field(default_factory=list)
