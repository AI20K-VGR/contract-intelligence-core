"""v20__ai2_schema — pgvector and the ``ai2`` schema for AI2 state (ADR-14).

Revision ID: v20__ai2_schema
Revises: v19__purge_unique_sha
Create Date: 2026-10-02

ADR-14 lets AI2 keep its own state (job, query, run stores, vectors) in schema
``ai2`` of the shared PostgreSQL, through a login role limited to that schema.
AI2 owns the tables there with its own alembic; the backend only provides the
extension and the schema. Only a superuser can create the extension, so it runs
here as ``ci``. The ``ai2`` role and its password are set at every start by
``contract_intelligence.infrastructure.ai2_db_role`` (issue #52).

Needs an image that ships pgvector (``pgvector/pgvector:pg16``).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "v20__ai2_schema"
down_revision: str | None = "v19__purge_unique_sha"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE SCHEMA IF NOT EXISTS ai2")


def downgrade() -> None:
    # Deliberately forward-only for live safety. Dropping ``ai2 CASCADE`` or
    # the vector extension would destroy runs, findings and embeddings. A
    # reviewed backup/data migration is required for any eventual retirement.
    return
