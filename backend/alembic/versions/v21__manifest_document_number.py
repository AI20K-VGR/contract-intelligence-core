"""v21__manifest_document_number — explicit contract/annex identities for AI2.

Shares the "v21" prefix with v21__tenant_lexicon (both branched from v20__ai2_schema
on different PRs). Revision ids are the full strings, so they do not collide; a merge
revision joins the two heads. Read the chain with `alembic history`, not the prefix.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v21__manifest_document_number"
down_revision: str | None = "v20__ai2_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "manifest_item" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("manifest_item")}
    if "document_number" not in columns:
        op.add_column(
            "manifest_item",
            sa.Column("document_number", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "manifest_item" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("manifest_item")}
    if "document_number" in columns:
        op.drop_column("manifest_item", "document_number")
