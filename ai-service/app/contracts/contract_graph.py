"""Typed amendment edges of the contract graph (flow 1, operation-first).

Kept apart from ``RelationType`` on purpose (D1): ``wire.py`` serializes
``relation_type.value`` straight to the Backend, and these sub-types must never reach it
(K3: every edge leaves AI2 as ``AMENDS``). Lives in ``contracts/`` because both the pipeline
and the job store read it.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.contracts.models import Citation, EvidenceIssue, RelationSupport, ReviewState

NEW_TEXT_MAX = 2000
PAIR_SPAN_MAX = 240


class EdgeOp(str, Enum):
    INSERTION = "INSERTION"
    SUBSTITUTION = "SUBSTITUTION"
    REPEAL = "REPEAL"
    REJECTION = "REJECTION"
    SCOPE_LIMIT = "SCOPE_LIMIT"


class EdgeMethod(str, Enum):
    EXACT = "EXACT"
    ANCESTOR = "ANCESTOR"
    SELF = "SELF"
    ORDER_INFERENCE = "ORDER_INFERENCE"
    ITEM_KEY = "ITEM_KEY"


class ContractEdge(BaseModel):
    """One operation of an amending unit on an existing target node; never a legal winner."""

    model_config = ConfigDict(extra="forbid")

    edge_id: str
    op: EdgeOp
    source_node_id: str
    target_node_id: str
    target_address: str  # canonical, e.g. "khoan 5a dieu 18" for an insertion into Điều 18
    anchor_node_id: str | None = None
    method: EdgeMethod
    support: RelationSupport
    standard: bool
    implicit: bool = False
    new_text: str | None = Field(default=None, max_length=NEW_TEXT_MAX)
    scope_text: str | None = None
    source_citation: Citation
    target_citation: Citation
    review_state: ReviewState = ReviewState.NEEDS_REVIEW
    source_snapshot_digest: str


class ContractGraphResult(BaseModel):
    edges: list[ContractEdge] = Field(default_factory=list)
    issues: list[EvidenceIssue] = Field(default_factory=list)
    stats: dict[str, int | dict[str, int]] = Field(default_factory=dict)


class PairLabel(str, Enum):
    GENERAL_SPECIFIC = "GENERAL_SPECIFIC"
    CONFLICT = "CONFLICT"
    DUPLICATE = "DUPLICATE"
    REFERENCE = "REFERENCE"


class PairRelation(BaseModel):
    """A grounded pair proposal; span citations are for storage, never legal approval."""

    model_config = ConfigDict(extra="forbid")

    relation_id: str
    label: PairLabel
    node_a_id: str
    node_b_id: str
    directed: bool
    candidate_sources: list[str]
    span_a: str = Field(max_length=PAIR_SPAN_MAX)
    span_b: str = Field(max_length=PAIR_SPAN_MAX)
    citation_a: Citation
    citation_b: Citation
    classifier_model: str
    prompt_version: str
    review_state: ReviewState = ReviewState.NEEDS_REVIEW
    source_snapshot_digest: str

    @field_validator("review_state")
    @classmethod
    def needs_review_only(cls, state: ReviewState) -> ReviewState:
        if state != ReviewState.NEEDS_REVIEW:
            raise ValueError("pair relations require NEEDS_REVIEW")
        return state


class PairResult(BaseModel):
    relations: list[PairRelation] = Field(default_factory=list)
    mode: Literal["llm", "rule_only"]
    rule_only_reason: str | None = None
    classifier_model: str | None = None
    prompt_version: str
    # P2 counters + nested rejection/label counters and nullable served-model metadata.
    stats: dict[str, Any] = Field(default_factory=dict)
    node_parts: dict[str, str] = Field(default_factory=dict)
    batches_completed: int = Field(default=0, ge=0)


def pair_relation_id_for(digest: str, label: PairLabel, node_a: str, node_b: str) -> str:
    key = f"{digest}|{label.value}|{node_a}|{node_b}"
    return "cpair:" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def edge_id_for(
    digest: str, op: EdgeOp, source: str, target: str, target_address: str, source_span: str
) -> str:
    """D10: stable across retries of the same snapshot (same pattern as ``relations.py``)."""

    key = f"{digest}|{op.value}|{source}|{target}|{target_address}|{source_span}"
    return "cedge:" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
