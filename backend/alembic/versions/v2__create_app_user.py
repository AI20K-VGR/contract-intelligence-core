"""v2__create_app_user_table

Revision ID: v2__create_app_user
Revises: v1__init
Create Date: 2026-09-18

Thêm bảng app_user và các indexes cần thiết cho Auth/RBAC module (DOC-05b Sprint 1).

Sprint 1:
    - Self-issued JWT (HS256) với claims: sub, email, display_name, role, tenant_id
    - Password hashing: Argon2id (passlib)
    - Refresh token revocation: token_version counter trong app_user

Sprint 2 (Keycloak):
    - Chỉ cần thay đổi settings: auth_mode = "keycloak"
    - Không cần thay đổi schema
    - Keycloak JWT chứa: sub (user_id), realm_access.roles, tenant_id custom claim
    - user_id (sub) vẫn dùng prefix "usr_" để tương thích với existing data

DBA notes:
    - uq_app_user_tenant_email đảm bảo email unique trong mỗi tenant (multi-tenancy isolation)
    - is_active = false khi admin disable user (login bị từ chối nhưng audit trail vẫn giữ)
    - token_version = 0 khi chưa có refresh token; tăng mỗi lần cấp refresh mới (revoke cũ)
    - password_hash dùng argon2 — không có plaintext trong DB
    - Cân nhắc: nếu cần tạo index trên (tenant_id, lower(email)) thay vì (tenant_id, email)
      vì email comparison là case-insensitive trong business logic.
      Tuy nhiên PostgreSQL COLLATE "C" cho TEXT đã là case-sensitive nên index thường OK.
      Nếu business cần case-insensitive lookup → dùng functional index trên lower(email).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "v2__create_app_user"
down_revision: Union[str, None] = "v1__init"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tạo bảng app_user
    op.create_table(
        "app_user",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # RBAC constraint — matching schema SQL trong DOC-04b
        sa.CheckConstraint(
            "role IN ('OPERATOR', 'REVIEWER', 'ADMINISTRATOR')",
            name="ck_app_user_role",
        ),
    )

    # Index trên tenant_id (cho filter query)
    op.create_index("ix_app_user_tenant", "app_user", ["tenant_id"])

    # Unique constraint: email unique trong mỗi tenant
    op.create_index(
        "ix_app_user_tenant_email",
        "app_user",
        ["tenant_id", "email"],
        unique=True,
    )

    # Index trên is_active (cho login query)
    op.create_index("ix_app_user_is_active", "app_user", ["is_active"])


def downgrade() -> None:
    op.drop_table("app_user")
