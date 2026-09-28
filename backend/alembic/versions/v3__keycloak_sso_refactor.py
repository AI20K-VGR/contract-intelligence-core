"""v3__keycloak_sso_refactor

Revision ID: v3__keycloak_sso_refactor
Revises: v2__create_app_user
Create Date: 2026-09-20

Refactor schema cho Keycloak SSO:
    - DROP COLUMN password_hash  (Keycloak quản lý password)
    - DROP COLUMN last_login_at  (Keycloak track riêng qua login events)
    - DROP COLUMN token_version  (Keycloak quản lý refresh token revocation)
    - ADD COLUMN keycloak_sub TEXT NOT NULL UNIQUE
        - Original `sub` claim từ Keycloak JWT — dùng cho idempotent upsert

Backward compatibility note:
    - DROP COLUMN là irreversible trong PostgreSQL (data mất vĩnh viễn).
    - Trước khi chạy migration, đảm bảo đã:
        1. Migrate users sang Keycloak realm (idempotent script ở scripts/)
        2. Cập nhật tất cả env từ AUTH_MODE=local sang AUTH_MODE=keycloak
        3. Verify /auth/me hoạt động đúng với Keycloak token
    - Nếu cần rollback, dùng PITR hoặc restore từ backup.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v3__keycloak_sso_refactor"
down_revision: Union[str, None] = "v2__create_app_user"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Thêm cột keycloak_sub (nullable trước để backfill nếu cần)
    op.add_column(
        "app_user",
        sa.Column("keycloak_sub", sa.Text(), nullable=True),
    )

    # 2. Backfill keycloak_sub từ id (assume id đã có prefix "usr_...")
    #    - Nếu id = "usr_xxx" → keycloak_sub = "xxx"
    #    - Nếu id không có prefix → keycloak_sub = id
    op.execute(
        """
        UPDATE app_user
        SET keycloak_sub = CASE
            WHEN id LIKE 'usr\\_%' ESCAPE '\\' THEN substring(id FROM 5)
            ELSE id
        END
        WHERE keycloak_sub IS NULL
        """
    )

    # 3. Set NOT NULL sau khi backfill
    op.alter_column("app_user", "keycloak_sub", nullable=False)

    # 4. Tạo UNIQUE index cho keycloak_sub
    op.create_index(
        "ix_app_user_keycloak_sub",
        "app_user",
        ["keycloak_sub"],
        unique=True,
    )

    # 5. DROP các cột không còn dùng
    op.drop_column("app_user", "password_hash")
    op.drop_column("app_user", "last_login_at")
    op.drop_column("app_user", "token_version")


def downgrade() -> None:
    # Re-add các cột (sẽ NULL hoặc default)
    op.add_column(
        "app_user",
        sa.Column("password_hash", sa.Text(), nullable=True),
    )
    op.add_column(
        "app_user",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "app_user",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )

    # Drop keycloak_sub
    op.drop_index("ix_app_user_keycloak_sub", table_name="app_user")
    op.drop_column("app_user", "keycloak_sub")

    # Set password_hash NOT NULL sau khi backfill (nếu cần)
    # Note: downgrade này giả định password_hash được restore từ data backup
    op.alter_column("app_user", "password_hash", nullable=False)
