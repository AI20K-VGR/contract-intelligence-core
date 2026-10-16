"""v24__pipeline_step_progress — in-step progress of a pipeline step.

Revision ID: v24__pipeline_step_progress
Revises: f6b54410fb6d
Create Date: 2026-10-16

``progress`` holds {"done", "total", "unit"} as JSON text, like ``metrics``;
``progress_at`` is when it was last written, so updates can be throttled.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v24__pipeline_step_progress"
down_revision: str | None = "f6b54410fb6d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("pipeline_step")}
    with op.batch_alter_table("pipeline_step") as batch:
        if "progress" not in columns:
            batch.add_column(sa.Column("progress", sa.Text(), nullable=True))
        if "progress_at" not in columns:
            batch.add_column(sa.Column("progress_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("pipeline_step") as batch:
        batch.drop_column("progress_at")
        batch.drop_column("progress")
