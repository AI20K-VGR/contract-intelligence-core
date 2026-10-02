from alembic import op

revision = "0003_ai2_vector_lookup_index"
down_revision = "0002_ai2_vector"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("idx_ai2_vector_lookup", "vector_segments",
                    ["snapshot_digest", "embedding_model", "dimensions"], schema="ai2")


def downgrade():
    op.drop_index("idx_ai2_vector_lookup", table_name="vector_segments", schema="ai2")
