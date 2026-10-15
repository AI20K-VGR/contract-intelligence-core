"""Contract-graph edges of the latest successful graph run per dossier (P4, D7).

Columns are spelled out here on purpose: ``app.db.tables.contract_edges`` sits on its own
``graph_metadata`` (D9) and must not be reached through 0001's ``metadata.create_all``.
Rollback (RT-03): ``python -m app.db.migrate downgrade 0004_ai2_job_indexes`` BEFORE reverting
this file; edges regenerate by re-running jobs with the flag on.
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_ai2_contract_edges"
down_revision = "0004_ai2_job_indexes"
branch_labels = None
depends_on = None

OPS = ("INSERTION", "SUBSTITUTION", "REPEAL", "REJECTION", "SCOPE_LIMIT")


def upgrade():
    def text(name, nullable=False):
        return sa.Column(name, sa.Text, nullable=nullable)

    op.create_table(
        "contract_edges",
        text("tenant_id"),
        text("dossier_id"),
        text("edge_id"),
        text("job_id"),
        text("source_snapshot_digest"),
        text("op"),
        text("source_node_id"),
        text("target_node_id"),
        text("anchor_node_id", nullable=True),
        text("target_address"),
        text("method"),
        text("support"),
        sa.Column("standard", sa.Integer, nullable=False),
        sa.Column("implicit", sa.Integer, nullable=False),
        text("review_state"),
        text("source_citation_json"),
        text("target_citation_json"),
        text("new_text", nullable=True),
        text("scope_text", nullable=True),
        text("digest"),
        sa.Column("created_ms", sa.BigInteger, nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "dossier_id", "edge_id"),
        sa.CheckConstraint(
            "op IN ({})".format(", ".join(f"'{value}'" for value in OPS)),
            name="ck_ai2_contract_edges_op",
        ),
        schema="ai2",
    )
    op.create_index(
        "idx_ai2_contract_edges_job", "contract_edges", ["tenant_id", "dossier_id", "job_id"], schema="ai2"
    )


def downgrade():
    # Only this revision's table; earlier revisions keep refusing destructive downgrades.
    op.drop_index("idx_ai2_contract_edges_job", table_name="contract_edges", schema="ai2")
    op.drop_table("contract_edges", schema="ai2")
