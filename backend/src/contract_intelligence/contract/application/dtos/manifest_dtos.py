"""Manifest confirmation DTOs — GET/POST /dossiers/{id}/manifest*.

Aligns with the Manifest Confirmation API contract (members + relations + version).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ManifestDocumentRole(StrEnum):
    """Role of a document inside a manifest membership."""

    CONTRACT = "contract"
    ANNEX = "annex"


class RelationType(StrEnum):
    """Allowed document-to-document relation kinds."""

    ANNEX_OF = "annex_of"
    AMENDS = "amends"
    SUPERSEDES = "supersedes"
    SUPPLEMENTS = "supplements"


class RelationConfirmation(StrEnum):
    """Operator decision on a proposed relation."""

    UNCONFIRMED = "unconfirmed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ManifestStatus(StrEnum):
    """Lifecycle of a dossier manifest."""

    PENDING = "pending"
    CONFIRMED = "confirmed"


class ManifestMemberDTO(BaseModel):
    """One document membership row in the manifest."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    filename: str
    role: ManifestDocumentRole
    included: bool
    order_index: int
    page_count: int = 0
    file_size_bytes: int = 0


class ManifestRelationDTO(BaseModel):
    """One directed relation between two members."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    source_document_id: str
    target_document_id: str
    relation_type: RelationType
    confirmation: RelationConfirmation


class ManifestDTO(BaseModel):
    """Full manifest payload returned by GET and POST confirm."""

    model_config = ConfigDict(extra="forbid")

    dossier_id: str
    status: ManifestStatus
    version: int
    latest_job_status: str | None = None
    members: list[ManifestMemberDTO] = Field(default_factory=list)
    relations: list[ManifestRelationDTO] = Field(default_factory=list)
    confirmed_at: datetime | None = None


class ConfirmManifestRequest(BaseModel):
    """Body for POST /dossiers/{dossier_id}/manifest/confirm."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(..., ge=1, description="Optimistic concurrency token")
    members: list[ManifestMemberDTO] = Field(default_factory=list)
    relations: list[ManifestRelationDTO] = Field(default_factory=list)


def normalize_manifest_status(raw: str) -> ManifestStatus:
    """Map legacy DRAFT/CONFIRMED (and mixed case) onto pending|confirmed."""
    value = (raw or "").strip().lower()
    if value in {"confirmed", "confirm"}:
        return ManifestStatus.CONFIRMED
    return ManifestStatus.PENDING


def normalize_document_role(raw: str) -> ManifestDocumentRole:
    """Map CONTRACT/ANNEX (and mixed case) onto contract|annex."""
    value = (raw or "").strip().lower()
    if value == ManifestDocumentRole.ANNEX.value:
        return ManifestDocumentRole.ANNEX
    if value == ManifestDocumentRole.CONTRACT.value:
        return ManifestDocumentRole.CONTRACT
    # Legacy uppercase stored in older rows
    if value == "annex":
        return ManifestDocumentRole.ANNEX
    return ManifestDocumentRole.CONTRACT


def iso_or_none(value: datetime | None) -> str | None:
    """Serialize datetime to ISO-8601 or null."""
    if value is None:
        return None
    return value.isoformat()


__all__ = [
    "ConfirmManifestRequest",
    "ManifestDTO",
    "ManifestDocumentRole",
    "ManifestMemberDTO",
    "ManifestRelationDTO",
    "ManifestStatus",
    "RelationConfirmation",
    "RelationType",
    "iso_or_none",
    "normalize_document_role",
    "normalize_manifest_status",
]
