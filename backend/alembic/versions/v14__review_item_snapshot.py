"""v14__review_item_snapshot — add review_item.target_snapshot to existing databases.

Revision ID: v14__review_item_snapshot
Revises: v13__review_action_unique
Create Date: 2026-09-28

The ORM gained ``target_snapshot`` (clause review) without a migration; databases
created before that miss the column and every review-item query fails. Fresh
databases already have it from ``v4``, hence IF NOT EXISTS.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v14__review_item_snapshot"
down_revision: str | None = "v13__review_action_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "review_item" not in set(inspector.get_table_names()):
        return
    if "target_snapshot" in {c["name"] for c in inspector.get_columns("review_item")}:
        return
    op.add_column("review_item", sa.Column("target_snapshot", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "review_item" not in set(inspector.get_table_names()):
        return
    if "target_snapshot" in {c["name"] for c in inspector.get_columns("review_item")}:
        op.drop_column("review_item", "target_snapshot")
