"""v13__review_action_unique — one review action per (item, base_version).

Revision ID: v13__review_action_unique
Revises: v12__audit_query_trace_immutable
Create Date: 2026-09-28

DB backstop for the optimistic lock on ``review_item.version``. Fresh databases
already get the index from ``v4`` (it materialises the ORM), hence IF NOT EXISTS.
Revision ids must fit ``alembic_version.version_num`` (varchar(32)).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v13__review_action_unique"
down_revision: str | None = "v12__audit_query_trace_immutable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX = "uq_review_action_item_base_version"


def upgrade() -> None:
    bind = op.get_bind()
    if "review_action" not in set(sa.inspect(bind).get_table_names()):
        return
    op.execute(
        sa.text(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {_INDEX} "
            "ON review_action (review_item_id, base_version)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"DROP INDEX IF EXISTS {_INDEX}"))
