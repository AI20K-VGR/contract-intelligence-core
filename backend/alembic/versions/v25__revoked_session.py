"""v25__revoked_session — Keycloak sessions ended by back-channel logout.

Revision ID: v25__revoked_session
Revises: v24__pipeline_step_progress
Create Date: 2026-10-18

One row per ended session (``sid``). The API refuses access tokens of that
session until ``expires_at``, after which the row is deleted.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v25__revoked_session"
down_revision: str | None = "v24__pipeline_step_progress"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("revoked_session"):
        return
    op.create_table(
        "revoked_session",
        sa.Column("sid", sa.Text(), primary_key=True),
        sa.Column("sub", sa.Text(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_revoked_session_expires_at", "revoked_session", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_revoked_session_expires_at", table_name="revoked_session")
    op.drop_table("revoked_session")
