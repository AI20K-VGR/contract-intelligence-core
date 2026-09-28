"""v12__review_item_target_snapshot — the column 2f6052c mapped without a migration.

``ReviewItemORM.target_snapshot`` (JSON text) shipped with the clause-review
wiring, but no revision created it, so every query that loads a review item
failed with ``UndefinedColumnError`` (e.g. ``GET /dossiers/{id}/conflicts``).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v12__review_item_target_snapshot"
down_revision: str | None = "v11__ai2_result_projection"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns() -> set[str] | None:
    inspector = sa.inspect(op.get_bind())
    if "review_item" not in inspector.get_table_names():
        return None
    return {column["name"] for column in inspector.get_columns("review_item")}


def upgrade() -> None:
    columns = _columns()
    if columns is not None and "target_snapshot" not in columns:
        op.add_column("review_item", sa.Column("target_snapshot", sa.Text(), nullable=True))


def downgrade() -> None:
    columns = _columns()
    if columns is not None and "target_snapshot" in columns:
        op.drop_column("review_item", "target_snapshot")
