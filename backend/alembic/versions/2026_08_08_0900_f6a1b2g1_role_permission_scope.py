"""Add scope column to role_permission junction table (own/team/organization)."""
from alembic import op
import sqlalchemy as sa

revision = "f6a1b2g1"
down_revision = "f6a1b2g0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "foundation_role_permissions",
        sa.Column("scope", sa.String(length=20), nullable=False, server_default="organization"),
    )
    op.create_check_constraint(
        "ck_foundation_role_permissions_scope",
        "foundation_role_permissions",
        "scope IN ('own', 'team', 'organization')",
    )


def downgrade():
    op.drop_constraint("ck_foundation_role_permissions_scope", "foundation_role_permissions", type_="check")
    op.drop_column("foundation_role_permissions", "scope")
