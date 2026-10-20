"""v18__query_answer — answer text of each Q&A, next to the append-only trace.

Revision ID: v18__query_answer
Revises: v17__ocr_line_conf_nullable
Create Date: 2026-09-29

query_trace is append-only (UPDATE/DELETE forbidden by trigger) and is the
audit trail. The answer quotes the contract, so it goes in its own table,
one row per trace, which the dossier purge can delete. Fresh databases
already get the table from ``v4`` (it materialises the ORM), hence the check.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v18__query_answer"
down_revision: str | None = "v17__ocr_line_conf_nullable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "query_answer"


def upgrade() -> None:
    bind = op.get_bind()
    if _TABLE in set(sa.inspect(bind).get_table_names()):
        return
    op.create_table(
        _TABLE,
        sa.Column("trace_id", sa.Text(), sa.ForeignKey("query_trace.id"), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("dossier_id", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_query_answer_dossier_id", _TABLE, ["dossier_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if _TABLE in set(sa.inspect(bind).get_table_names()):
        op.drop_table(_TABLE)
