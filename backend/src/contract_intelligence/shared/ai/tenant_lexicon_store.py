"""Append-only governance records; một head row duy nhất làm CAS lock cho tenant."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKeyConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from contract_intelligence.shared.persistence import Base


class LexiconHeadORM(Base):
    __tablename__ = "tenant_lexicon_head"
    tenant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ExpertAssignmentORM(Base):
    __tablename__ = "tenant_lexicon_assignment"
    tenant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    expert_id: Mapped[str] = mapped_column(String(128), nullable=False)
    designated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    expertise_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AliasProposalORM(Base):
    __tablename__ = "tenant_lexicon_proposal"
    tenant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    proposal_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    producer_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class LexiconVersionORM(Base):
    __tablename__ = "tenant_lexicon_version"
    tenant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    # Immutable JSON is a typed profile projection, never raw contract text.
    profile: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class AliasEntryORM(Base):
    __tablename__ = "tenant_lexicon_alias"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "version"],
            ["tenant_lexicon_version.tenant_id", "tenant_lexicon_version.version"],
        ),
    )
    tenant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    source: Mapped[str] = mapped_column(String(120), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    proposal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    method: Mapped[str] = mapped_column(String(32), nullable=False)


class LexiconAuditORM(Base):
    __tablename__ = "tenant_lexicon_audit"
    tenant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    command_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    receipt: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


LEXICON_TABLES = [
    model.__table__
    for model in (
        LexiconHeadORM,
        ExpertAssignmentORM,
        AliasProposalORM,
        LexiconVersionORM,
        AliasEntryORM,
        LexiconAuditORM,
    )
]
