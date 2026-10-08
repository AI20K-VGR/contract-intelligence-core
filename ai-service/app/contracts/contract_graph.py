"""Typed amendment edges of the contract graph (flow 1, operation-first).

Kept apart from ``RelationType`` on purpose (D1): ``wire.py`` serializes
``relation_type.value`` straight to the Backend, and these sub-types must never reach it
(K3: every edge leaves AI2 as ``AMENDS``). Lives in ``contracts/`` because both the pipeline
and the job store read it.
"""

from __future__ import annotations

import hashlib
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.models import Citation, EvidenceIssue, RelationSupport, ReviewState

NEW_TEXT_MAX = 2000


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


def edge_id_for(
    digest: str, op: EdgeOp, source: str, target: str, target_address: str, source_span: str
) -> str:
    """D10: stable across retries of the same snapshot (same pattern as ``relations.py``)."""

    key = f"{digest}|{op.value}|{source}|{target}|{target_address}|{source_span}"
    return "cedge:" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
