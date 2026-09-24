"""v5__job_lease_columns — Postgres job-queue lease fields on ``job``.

Revision ID: v5__job_lease_columns
Revises: v4__create_core_schema
Create Date: 2026-09-21

Adds ``lease_owner`` / ``lease_expires_at`` for FOR UPDATE SKIP LOCKED claiming
and the async reaper. Safe on fresh installs where v4 ``create_all`` already
materialised the columns (IF NOT EXISTS / checkfirst style).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v5__job_lease_columns"
down_revision: str | None = "v4__create_core_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "job" not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns("job")}
    if "lease_owner" not in existing:
        op.add_column("job", sa.Column("lease_owner", sa.Text(), nullable=True))
    if "lease_expires_at" not in existing:
        op.add_column(
            "job",
            sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        )
    indexes = {ix["name"] for ix in inspector.get_indexes("job")}
    if "ix_job_queue_ready" not in indexes:
        op.create_index("ix_job_queue_ready", "job", ["status", "created_at"])
    if "ix_job_lease_expires_at" not in indexes:
        op.create_index("ix_job_lease_expires_at", "job", ["lease_expires_at"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "job" not in inspector.get_table_names():
        return
    indexes = {ix["name"] for ix in inspector.get_indexes("job")}
    if "ix_job_lease_expires_at" in indexes:
        op.drop_index("ix_job_lease_expires_at", table_name="job")
    if "ix_job_queue_ready" in indexes:
        op.drop_index("ix_job_queue_ready", table_name="job")
    existing = {c["name"] for c in inspector.get_columns("job")}
    if "lease_expires_at" in existing:
        op.drop_column("job", "lease_expires_at")
    if "lease_owner" in existing:
        op.drop_column("job", "lease_owner")
