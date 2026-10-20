"""v16__processed_event — Kafka records the worker already handled (DOC-11 §4.2 #8).

Revision ID: v16__processed_event
Revises: v15__run_event
Create Date: 2026-09-30

One row per (handler, event key) the worker finished, so a redelivered record
after a restart is skipped. Fresh databases already get the table from ``v4``
(it materialises the ORM), hence the existence check.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v16__processed_event"
down_revision: str | None = "v15__run_event"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "processed_event"


def upgrade() -> None:
    bind = op.get_bind()
    if _TABLE in set(sa.inspect(bind).get_table_names()):
        return
    op.create_table(
        _TABLE,
        sa.Column("consumer", sa.Text(), primary_key=True),
        sa.Column("event_key", sa.Text(), primary_key=True),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("partition", sa.Integer(), nullable=False),
        sa.Column("offset", sa.Integer(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_processed_event_processed_at", _TABLE, ["processed_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if _TABLE in set(sa.inspect(bind).get_table_names()):
        op.drop_table(_TABLE)
