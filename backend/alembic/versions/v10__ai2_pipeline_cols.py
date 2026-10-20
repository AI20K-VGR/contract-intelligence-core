"""v10__ai2_pipeline_cols — AI2 durable columns + table continuity.

Revision ID: v10__ai2_pipeline_cols
Revises: v9__deletion_ledger_align
Create Date: 2026-09-26

ORM added AI2 result fields on ``pipeline_run`` and multi-page continuity
fields on ``doc_table`` without a migration. Existing local/staging DBs that
were created from older ``create_all`` / v4 stay at alembic head but are
missing columns — worker then fails after OCR with UndefinedColumnError.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v10__ai2_pipeline_cols"
down_revision: str | None = "v9__deletion_ledger_align"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "pipeline_run" in tables:
        cols = {c["name"] for c in inspector.get_columns("pipeline_run")}
        with op.batch_alter_table("pipeline_run") as batch:
            if "ai2_result_json" not in cols:
                batch.add_column(sa.Column("ai2_result_json", sa.Text(), nullable=True))
            if "ai2_result_digest" not in cols:
                batch.add_column(sa.Column("ai2_result_digest", sa.Text(), nullable=True))
            if "ai2_idempotency_key" not in cols:
                batch.add_column(sa.Column("ai2_idempotency_key", sa.Text(), nullable=True))
            if "ai2_job_status" not in cols:
                batch.add_column(sa.Column("ai2_job_status", sa.Text(), nullable=True))
            if "ai2_review_state" not in cols:
                batch.add_column(sa.Column("ai2_review_state", sa.Text(), nullable=True))
            if "ai2_completeness_state" not in cols:
                batch.add_column(sa.Column("ai2_completeness_state", sa.Text(), nullable=True))
            if "ai2_reason_code" not in cols:
                batch.add_column(sa.Column("ai2_reason_code", sa.Text(), nullable=True))
            if "ai2_evidence_ready" not in cols:
                batch.add_column(
                    sa.Column(
                        "ai2_evidence_ready",
                        sa.Boolean(),
                        nullable=False,
                        server_default=sa.text("false"),
                    )
                )
            if "ai2_input_counts" not in cols:
                batch.add_column(sa.Column("ai2_input_counts", sa.Text(), nullable=True))
            if "ai2_output_counts" not in cols:
                batch.add_column(sa.Column("ai2_output_counts", sa.Text(), nullable=True))
            if "ai2_dropped_records" not in cols:
                batch.add_column(
                    sa.Column(
                        "ai2_dropped_records",
                        sa.Integer(),
                        nullable=False,
                        server_default="0",
                    )
                )
            if "ai2_evidence_issue_count" not in cols:
                batch.add_column(
                    sa.Column(
                        "ai2_evidence_issue_count",
                        sa.Integer(),
                        nullable=False,
                        server_default="0",
                    )
                )
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_pipeline_run_ai2_result_digest "
                "ON pipeline_run (ai2_result_digest)"
            )
        )
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_pipeline_run_ai2_idempotency_key "
                "ON pipeline_run (ai2_idempotency_key)"
            )
        )

    if "doc_table" in tables:
        cols = {c["name"] for c in inspector.get_columns("doc_table")}
        with op.batch_alter_table("doc_table") as batch:
            if "is_multi_page" not in cols:
                batch.add_column(
                    sa.Column(
                        "is_multi_page",
                        sa.Boolean(),
                        nullable=False,
                        server_default=sa.text("false"),
                    )
                )
            if "continued_from" not in cols:
                batch.add_column(sa.Column("continued_from", sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "doc_table" in tables:
        cols = {c["name"] for c in inspector.get_columns("doc_table")}
        with op.batch_alter_table("doc_table") as batch:
            if "continued_from" in cols:
                batch.drop_column("continued_from")
            if "is_multi_page" in cols:
                batch.drop_column("is_multi_page")

    if "pipeline_run" in tables:
        op.execute(sa.text("DROP INDEX IF EXISTS ix_pipeline_run_ai2_idempotency_key"))
        op.execute(sa.text("DROP INDEX IF EXISTS ix_pipeline_run_ai2_result_digest"))
        cols = {c["name"] for c in inspector.get_columns("pipeline_run")}
        with op.batch_alter_table("pipeline_run") as batch:
            for name in (
                "ai2_evidence_issue_count",
                "ai2_dropped_records",
                "ai2_output_counts",
                "ai2_input_counts",
                "ai2_evidence_ready",
                "ai2_reason_code",
                "ai2_completeness_state",
                "ai2_review_state",
                "ai2_job_status",
                "ai2_idempotency_key",
                "ai2_result_digest",
                "ai2_result_json",
            ):
                if name in cols:
                    batch.drop_column(name)
