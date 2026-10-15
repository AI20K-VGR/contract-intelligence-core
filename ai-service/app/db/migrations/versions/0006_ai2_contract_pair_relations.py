"""Grounded pair proposals of the latest successful classifier run."""
import sqlalchemy as sa
from alembic import op

revision = "0006_ai2_contract_pair_relations"
down_revision = "0005_ai2_contract_edges"
branch_labels = None
depends_on = None

LABELS = ("GENERAL_SPECIFIC", "CONFLICT", "DUPLICATE", "REFERENCE")


def upgrade():
    def text(name):
        return sa.Column(name, sa.Text, nullable=False)

    op.create_table(
        "contract_pair_relations",
        text("tenant_id"), text("dossier_id"), text("relation_id"), text("job_id"),
        text("source_snapshot_digest"), text("label"),
        sa.Column("directed", sa.Integer, nullable=False),
        text("node_a_id"), text("node_b_id"), text("candidate_sources_json"),
        text("span_a"), text("span_b"), text("citation_a_json"), text("citation_b_json"),
        text("classifier_model"), text("prompt_version"), text("review_state"), text("digest"),
        sa.Column("created_ms", sa.BigInteger, nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "dossier_id", "relation_id"),
        sa.CheckConstraint("label IN ({})".format(", ".join(f"'{label}'" for label in LABELS)),
                           name="ck_ai2_contract_pair_relations_label"),
        schema="ai2",
    )
    op.create_index("idx_ai2_contract_pair_relations_job", "contract_pair_relations",
                    ["tenant_id", "dossier_id", "job_id"], schema="ai2")


def downgrade():
    op.drop_index("idx_ai2_contract_pair_relations_job", table_name="contract_pair_relations", schema="ai2")
    op.drop_table("contract_pair_relations", schema="ai2")
