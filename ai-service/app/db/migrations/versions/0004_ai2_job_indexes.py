from alembic import op
from sqlalchemy import text

revision = "0004_ai2_job_indexes"
down_revision = "0003_ai2_vector_lookup_index"
branch_labels = None
depends_on = None


def upgrade():
    # Periodic sweep (every second, every process): only QUEUED/RUNNING rows.
    op.create_index("idx_ai2_jobs_active_lease", "jobs", ["status", "lease_until_ms", "updated_ms"],
                    schema="ai2", postgresql_where=text("status IN ('QUEUED', 'RUNNING')"))
    # complete_with_snapshot's newest-success lookup, run under the dossier lock.
    op.create_index("idx_ai2_jobs_owner_latest", "jobs",
                    ["tenant_id", "dossier_id", "status", text("created_ms DESC"), text("job_id DESC")],
                    schema="ai2")


def downgrade():
    op.drop_index("idx_ai2_jobs_owner_latest", table_name="jobs", schema="ai2")
    op.drop_index("idx_ai2_jobs_active_lease", table_name="jobs", schema="ai2")
