"""Let ocr_line.confidence be unknown.

Revision ID: v17__ocr_line_conf_nullable
Revises: v16__processed_event
Create Date: 2026-09-29

The UI now shows OCR confidence per bbox. AI1 scores each line itself; a line
without a score is stored as NULL, i.e. unknown rather than 0.

Rows already written keep their value: ``ocr_line`` is append-only (a trigger
rejects UPDATE/DELETE). The ``1.0`` placeholder the old AI1 bridge wrote for
every line is read back as unknown instead (see ``stored_line_confidence``).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v17__ocr_line_conf_nullable"
down_revision: str | None = "v16__processed_event"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if "ocr_line" not in sa.inspect(conn).get_table_names():
        return
    with op.batch_alter_table("ocr_line") as batch:
        batch.alter_column(
            "confidence", existing_type=sa.String(), nullable=True, server_default=None
        )


def downgrade() -> None:
    # NOT NULL cannot come back once NULL rows exist, and the table is
    # append-only, so they cannot be rewritten. Nothing to undo safely.
    pass
