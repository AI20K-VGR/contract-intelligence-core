"""Persist bounded AI2 worker stage events independently from result wire."""

import sqlalchemy as sa
from alembic import op

revision = "0008_ai2_processing_trace"
down_revision = "0007_graph_receipts"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE ai2.jobs ADD COLUMN IF NOT EXISTS trace_status TEXT NOT NULL DEFAULT 'AVAILABLE'")
    op.execute("ALTER TABLE ai2.jobs ADD COLUMN IF NOT EXISTS current_execution_id TEXT")
    op.create_table(
        "ai2_processing_trace_events",
        sa.Column("tenant_id", sa.Text, nullable=False),
        sa.Column("dossier_id", sa.Text, nullable=False),
        sa.Column("job_id", sa.Text, nullable=False),
        sa.Column("snapshot_digest", sa.Text, nullable=False),
        sa.Column("execution_id", sa.Text, nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("stage_id", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("created_ms", sa.BigInteger, nullable=False),
        sa.Column("started_ms", sa.BigInteger, nullable=True),
        sa.Column("duration_ms", sa.BigInteger, nullable=True),
        sa.Column("item_count", sa.Integer, nullable=True),
        sa.Column("reason_code", sa.Text, nullable=True),
        sa.PrimaryKeyConstraint(
            "tenant_id", "dossier_id", "job_id", "snapshot_digest", "execution_id", "sequence",
            name="pk_ai2_processing_trace_events",
        ),
        sa.CheckConstraint(
            "status IN ('STARTED', 'COMPLETED', 'FAILED', 'SKIPPED', 'INTERRUPTED_UNKNOWN')",
            name="ck_ai2_processing_trace_status",
        ),
        sa.CheckConstraint("duration_ms IS NULL OR duration_ms >= 0",
                           name="ck_ai2_processing_trace_duration"),
        sa.CheckConstraint("item_count IS NULL OR item_count >= 0",
                           name="ck_ai2_processing_trace_item_count"),
        schema="ai2",
    )
    op.create_index(
        "idx_ai2_processing_trace_scope", "ai2_processing_trace_events",
        ["tenant_id", "dossier_id", "job_id", "snapshot_digest", "sequence"], schema="ai2",
    )


def downgrade():
    op.drop_index("idx_ai2_processing_trace_scope", table_name="ai2_processing_trace_events", schema="ai2")
    op.drop_table("ai2_processing_trace_events", schema="ai2")
    op.drop_column("jobs", "current_execution_id", schema="ai2")
    op.drop_column("jobs", "trace_status", schema="ai2")
