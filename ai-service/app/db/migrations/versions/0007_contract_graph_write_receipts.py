"""Record whether graph stages ran and whether their rows committed."""

import sqlalchemy as sa
from alembic import op

revision = "0007_graph_receipts"
down_revision = "0006_ai2_contract_pair_relations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "contract_graph_write_receipts",
        sa.Column("tenant_id", sa.Text, nullable=False),
        sa.Column("dossier_id", sa.Text, nullable=False),
        sa.Column("job_id", sa.Text, nullable=False),
        sa.Column("graph_kind", sa.Text, nullable=False),
        sa.Column("source_snapshot_digest", sa.Text, nullable=False),
        sa.Column("stage_status", sa.Text, nullable=False),
        sa.Column("write_status", sa.Text, nullable=False),
        sa.Column("row_count", sa.Integer, nullable=False),
        sa.Column("error_code", sa.Text, nullable=True),
        sa.Column("created_ms", sa.BigInteger, nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "dossier_id", "job_id", "graph_kind"),
        sa.CheckConstraint("graph_kind IN ('operation', 'pair')", name="ck_ai2_graph_receipt_kind"),
        sa.CheckConstraint("stage_status IN ('COMPLETED', 'SKIPPED', 'FAILED', 'UNKNOWN')",
                           name="ck_ai2_graph_receipt_stage"),
        sa.CheckConstraint("write_status IN ('COMMITTED', 'SKIPPED', 'FAILED')",
                           name="ck_ai2_graph_receipt_write"),
        sa.CheckConstraint("row_count >= 0", name="ck_ai2_graph_receipt_row_count"),
        schema="ai2",
    )
    op.create_index("idx_ai2_graph_receipts_scope", "contract_graph_write_receipts",
                    ["tenant_id", "dossier_id", "job_id"], schema="ai2")


def downgrade():
    op.drop_index("idx_ai2_graph_receipts_scope", table_name="contract_graph_write_receipts", schema="ai2")
    op.drop_table("contract_graph_write_receipts", schema="ai2")
