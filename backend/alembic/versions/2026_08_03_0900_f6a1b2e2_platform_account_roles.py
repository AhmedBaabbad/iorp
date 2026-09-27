"""add formal platform account roles

Revision ID: f6a1b2e2
Revises: f6a1b2e1
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "f6a1b2e2"
down_revision: str | None = "f6a1b2e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    role = sa.Enum("root", "admin", name="platform_account_role")
    role.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "system_platform_accounts",
        sa.Column("role", role, nullable=True, server_default="admin"),
    )
    op.execute(
        "UPDATE system_platform_accounts "
        "SET role = (CASE WHEN is_root THEN 'root' ELSE 'admin' END)::platform_account_role"
    )
    op.alter_column("system_platform_accounts", "role", nullable=False, server_default=None)


def downgrade() -> None:
    op.drop_column("system_platform_accounts", "role")
    sa.Enum(name="platform_account_role").drop(op.get_bind(), checkfirst=True)
