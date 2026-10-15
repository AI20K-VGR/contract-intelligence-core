"""merge AI2 and manifest migration heads

Revision ID: f6b54410fb6d
Revises: v21__manifest_document_number, v23__service_logs_and_purge_fix
Create Date: 2026-10-14 05:34:27.538770

"""
# revision identifiers, used by Alembic.
revision: str = "f6b54410fb6d"
down_revision: tuple[str, str] = (
    "v21__manifest_document_number",
    "v23__service_logs_and_purge_fix",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
