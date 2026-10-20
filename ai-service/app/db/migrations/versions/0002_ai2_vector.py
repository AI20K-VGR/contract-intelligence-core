from alembic import op
from sqlalchemy import text

revision = "0002_ai2_vector"
down_revision = "0001_ai2_initial"
branch_labels = None
depends_on = None


def upgrade():
    cx = op.get_bind()
    available = cx.execute(text("SELECT 1 FROM pg_available_extensions WHERE name='vector'")).scalar()
    if not available:
        return
    installed = cx.execute(text("SELECT 1 FROM pg_extension WHERE extname='vector'")).scalar()
    if not installed:
        superuser = cx.execute(text("SELECT rolsuper FROM pg_roles WHERE rolname=current_user")).scalar()
        if not superuser:
            return
        cx.execute(text("CREATE EXTENSION vector"))
    cx.execute(text("ALTER TABLE ai2.vector_segments ADD COLUMN IF NOT EXISTS embedding vector"))


def downgrade():
    raise RuntimeError("Destructive AI2 downgrade requires a separate reviewed data migration")
