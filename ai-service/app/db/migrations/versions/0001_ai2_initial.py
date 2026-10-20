from alembic import op
from sqlalchemy import text

from app.db.tables import metadata

revision = "0001_ai2_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    cx = op.get_bind()
    metadata.create_all(cx)
    cx.execute(text("""CREATE FUNCTION ai2.reject_audit_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'durable audit is append-only'; END $$"""))
    cx.execute(text("""CREATE TRIGGER durable_audit_append_only BEFORE UPDATE OR DELETE
        ON ai2.durable_audit FOR EACH ROW EXECUTE FUNCTION ai2.reject_audit_mutation()"""))


def downgrade():
    raise RuntimeError("Destructive AI2 downgrade requires a separate reviewed data migration")
