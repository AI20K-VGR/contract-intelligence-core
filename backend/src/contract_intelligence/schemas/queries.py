"""Pydantic schemas for dossier Q&A (query path)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DossierQueryRequest(BaseModel):
    """POST /dossiers/{id}/query request body.

    AI2 policy flags (egress, vector) are server configuration and are rejected here.
    """

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, max_length=4000)


class DossierQueryResponse(BaseModel):
    """AI2 query answer envelope returned to the frontend."""

    model_config = ConfigDict(extra="ignore")

    state: str
    answer: str
    citations: list[Any] = Field(default_factory=list)
    retrieval_layer: dict[str, Any] = Field(default_factory=dict)
    reasoning_trace: list[Any] = Field(default_factory=list)
    trace_id: str | None = Field(default=None, description="Persisted QueryTrace id.")
    acl_decision: str | None = Field(
        default=None, description="Second-pass ACL on citations: passed | filtered | denied."
    )


__all__ = [
    "DossierQueryRequest",
    "DossierQueryResponse",
]
