"""Canonical AI2 domain objects for segmentation and evidence-bound reasoning.

The models in this module are an internal, versioned domain projection.  They
retain the upstream JSON separately from derived objects so later review or
compatibility projections cannot rewrite AI1 evidence.
"""

from __future__ import annotations

from copy import deepcopy
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.contracts.models import ReviewState


class DocumentRole(str, Enum):
    BODY = "body"
    ANNEX = "annex"
    UNKNOWN = "unknown"


class BoundaryStatus(str, Enum):
    PROPOSED = "PROPOSED"
    CONFIRMED = "CONFIRMED"
    AMBIGUOUS = "AMBIGUOUS"
    REJECTED = "REJECTED"


class EvidenceState(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIABLE = "UNVERIFIABLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class CanonicalCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_ref: str
    text: str = ""
    status: Literal["VALID", "MISMATCH", "MISSING"] = "MISSING"


class InputSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    schema_version: str
    raw_source: dict[str, Any]


class Boundary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    boundary_id: str
    document_id: str
    start_ref: str | None = None
    end_ref: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    status: BoundaryStatus = BoundaryStatus.PROPOSED
    quality_flags: list[str] = Field(default_factory=list)


class Party(BaseModel):
    model_config = ConfigDict(extra="forbid")

    party_id: str
    name: str
    role: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class Clause(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clause_id: str
    document_id: str
    text: str
    evidence_refs: list[str] = Field(default_factory=list)
    quality_flags: list[str] = Field(default_factory=list)


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_id: str
    value: str
    evidence_refs: list[str] = Field(default_factory=list)
    citations: list[CanonicalCitation] = Field(default_factory=list)
    evidence_state: EvidenceState = EvidenceState.UNVERIFIABLE
    review_state: ReviewState = ReviewState.NEEDS_REVIEW


class Relation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation_id: str
    relation_type: str
    from_ref: str | None = None
    to_ref: str | None = None
    from_document_id: str | None = None
    to_document_id: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    evidence_state: EvidenceState = EvidenceState.INSUFFICIENT_EVIDENCE
    review_state: ReviewState = ReviewState.NEEDS_REVIEW


class LogicalDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    role: DocumentRole = DocumentRole.UNKNOWN
    raw_source: dict[str, Any]
    source_refs: list[str] = Field(default_factory=list)
    boundaries: list[Boundary] = Field(default_factory=list)
    parties: list[Party] = Field(default_factory=list)
    clauses: list[Clause] = Field(default_factory=list)


class Generation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generation_id: str
    input_snapshot_id: str
    segmentation_version: str
    state_version: int = Field(ge=0)


class DependencyArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    kind: str
    depends_on: list[str] = Field(default_factory=list)
    stale: bool = False


class DependencyGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifacts: dict[str, DependencyArtifact] = Field(default_factory=dict)

    def is_stale(self, artifact_id: str) -> bool:
        artifact = self.artifacts.get(artifact_id)
        return bool(artifact and artifact.stale)

    def invalidate(self, artifact_ids: set[str]) -> list[str]:
        """Mark transitive dependants stale without mutating raw input nodes."""

        stale = set(artifact_ids)
        changed = True
        while changed:
            changed = False
            for artifact in self.artifacts.values():
                if artifact.artifact_id in stale:
                    continue
                if set(artifact.depends_on) & stale:
                    stale.add(artifact.artifact_id)
                    changed = True
        for artifact_id in stale:
            if artifact_id in self.artifacts and self.artifacts[artifact_id].kind != "input":
                self.artifacts[artifact_id].stale = True
        return sorted(
            artifact_id
            for artifact_id in stale
            if artifact_id in self.artifacts and self.artifacts[artifact_id].kind != "input"
        )


class EditImpact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edit_kind: str
    artifact_id: str
    stale_artifact_ids: list[str] = Field(default_factory=list)


class AI2Run(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    run_id: str
    input_snapshot: InputSnapshot
    documents: list[LogicalDocument] = Field(default_factory=list)
    boundaries: list[Boundary] = Field(default_factory=list)
    parties: list[Party] = Field(default_factory=list)
    clauses: list[Clause] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    generation: Generation
    dependencies: DependencyGraph
    quality_flags: list[str] = Field(default_factory=list)
    review_state: ReviewState = ReviewState.PASS
    user_context: dict[str, Any] | None = None

    def mark_edit(self, edit_kind: str, artifact_id: str) -> EditImpact:
        """Return and record derived staleness for a review edit.

        Annotation edits are presentation/review metadata and do not invalidate
        source evidence. Boundary, fact, and relation edits invalidate derived
        generations; the immutable input artifact is deliberately excluded.
        """

        if edit_kind == "annotation":
            return EditImpact(edit_kind=edit_kind, artifact_id=artifact_id)
        if edit_kind not in {"boundary", "fact", "relation"}:
            raise ValueError(f"unsupported canonical edit kind: {edit_kind}")
        target = f"{edit_kind}:{artifact_id}"
        if target not in self.dependencies.artifacts:
            self.dependencies.artifacts[target] = DependencyArtifact(
                artifact_id=target,
                kind=edit_kind,
            )
        stale_ids = self.dependencies.invalidate({target})
        if f"generation:{self.input_snapshot.snapshot_id}" not in stale_ids:
            # A reviewer may edit a not-yet-materialized fact/relation. The
            # current generation is still no longer safe to reuse.
            stale_ids = self.dependencies.invalidate(
                {target, f"generation:{self.input_snapshot.snapshot_id}"}
            )
        return EditImpact(edit_kind=edit_kind, artifact_id=artifact_id, stale_artifact_ids=stale_ids)


def clone_source(value: Any) -> Any:
    """Copy upstream JSON before any derived model is built."""

    return deepcopy(value)


__all__ = [
    "AI2Run",
    "Boundary",
    "BoundaryStatus",
    "CanonicalCitation",
    "Clause",
    "DependencyArtifact",
    "DependencyGraph",
    "DocumentRole",
    "EditImpact",
    "EvidenceState",
    "Fact",
    "Generation",
    "InputSnapshot",
    "LogicalDocument",
    "Party",
    "Relation",
    "ReviewState",
]
