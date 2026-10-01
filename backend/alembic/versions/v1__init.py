"""V1 __init_schema__ — sinh từ DOC-04b-postgres-schema.sql.

Revision ID: v1__init
Revises:
Create Date: 2026-09-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "v1__init"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all 23 tables from DOC-04b-postgres-schema.sql v1.0.

    Sprint 2: chạy ``alembic revision --autogenerate`` sau khi đã define
    SQLAlchemy models đầy đủ. File này là placeholder để alembic chạy được.
    """
    # TODO Sprint 2: autogenerate from SQLAlchemy Base.metadata
    pass


def downgrade() -> None:
    """Drop all 23 tables."""
    pass
