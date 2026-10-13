"""v24__merge_manifest_number — join the two branches that leave v20__ai2_schema.

``v21__tenant_lexicon`` .. ``v23__service_logs_and_purge_fix`` and
``v21__manifest_document_number`` were written on separate branches. No schema
change here: the revision only gives the history a single head again.

The revision id must fit ``alembic_version.version_num``, a varchar(32).
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "v24__merge_manifest_number"
down_revision: tuple[str, str] = (
    "v23__service_logs_and_purge_fix",
    "v21__manifest_document_number",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
