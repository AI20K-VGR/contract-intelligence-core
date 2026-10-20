"""v15__run_event — outbox of pipeline progress events for SSE (DOC-11 §8).

Revision ID: v15__run_event
Revises: v14__review_item_snapshot
Create Date: 2026-09-29

One row per job/run/step status change, written in the same transaction as the
change. ``id`` gives the commit order the SSE stream resumes from
(``Last-Event-ID``). Fresh databases already get the table from ``v4`` (it
materialises the ORM), hence the existence checks.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v15__run_event"
down_revision: str | None = "v14__review_item_snapshot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "run_event"
_INDEX = "ix_run_event_run_id_id"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _TABLE not in set(inspector.get_table_names()):
        op.create_table(
            _TABLE,
            sa.Column(
                "id",
                sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
                primary_key=True,
                autoincrement=True,
            ),
            sa.Column("tenant_id", sa.Text(), nullable=False),
            sa.Column("run_id", sa.Text(), nullable=False),
            sa.Column("dossier_id", sa.Text(), nullable=True),
            sa.Column("type", sa.Text(), nullable=False),
            sa.Column("payload", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        inspector = sa.inspect(bind)
    if _INDEX not in {index["name"] for index in inspector.get_indexes(_TABLE)}:
        op.create_index(_INDEX, _TABLE, ["run_id", "id"])


def downgrade() -> None:
    bind = op.get_bind()
    if _TABLE in set(sa.inspect(bind).get_table_names()):
        op.drop_table(_TABLE)
