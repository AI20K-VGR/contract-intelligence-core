"""Durable actor-scoped idempotency for dossier reprocessing.

Revision ID: v22__reprocess_idempotency
Revises: v21__tenant_lexicon
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v22__reprocess_idempotency"
down_revision: str | None = "v21__tenant_lexicon"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "pipeline_run" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("pipeline_run")}
    with op.batch_alter_table("pipeline_run") as batch:
        for name in (
            "reprocess_idempotency_key",
            "reprocess_actor_id",
            "reprocess_base_run_id",
            "reprocess_source_digest",
        ):
            if name not in columns:
                batch.add_column(sa.Column(name, sa.Text(), nullable=True))

    constraints = {
        constraint.get("name")
        for constraint in sa.inspect(connection).get_unique_constraints("pipeline_run")
    }
    if "uq_pipeline_run_reprocess_idempotency" not in constraints:
        op.create_unique_constraint(
            "uq_pipeline_run_reprocess_idempotency",
            "pipeline_run",
            [
                "tenant_id",
                "dossier_id",
                "reprocess_actor_id",
                "reprocess_idempotency_key",
            ],
        )


def downgrade() -> None:
    # Preserve idempotency history during rollback. Removing the unique key
    # or columns would permit duplicate reprocess runs after an older binary
    # is restored. Older code safely ignores additive columns.
    return
