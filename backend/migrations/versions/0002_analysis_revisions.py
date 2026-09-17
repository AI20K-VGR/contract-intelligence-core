"""Persist immutable human-derived analysis revisions."""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade():
    op.create_table("analysis_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("review_version", sa.Integer(), nullable=False),
        sa.Column("result_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.UniqueConstraint("job_id", "review_version"))
    op.create_index("ix_analysis_revisions_job_id", "analysis_revisions", ["job_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE TRIGGER immutable_analysis_revisions BEFORE UPDATE OR DELETE "
                   "ON analysis_revisions FOR EACH ROW EXECUTE FUNCTION reject_immutable_change()")


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore a verified backup instead.")
