"""Append-only audit trail: actor/action/object per dossier-scoped mutation."""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade():
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dossier_id", sa.String(36), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("object_type", sa.String(40), nullable=False),
        sa.Column("object_id", sa.String(80), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=True),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_audit_events_dossier_id", "audit_events", ["dossier_id"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE TRIGGER immutable_audit_events BEFORE UPDATE OR DELETE ON audit_events "
            "FOR EACH ROW EXECUTE FUNCTION reject_immutable_change()"
        )


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore a verified backup instead.")
