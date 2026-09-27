"""organization lifecycle state machine

Revision ID: f6a1b2e3
Revises: f6a1b2e2
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f6a1b2e3"
down_revision: str | None = "f6a1b2e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for value in ("provisioning", "suspended", "archived"):
        op.execute(f"ALTER TYPE organization_status ADD VALUE IF NOT EXISTS '{value}'")
    op.add_column("foundation_organizations", sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("foundation_organizations", sa.Column("status_changed_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("foundation_organizations", sa.Column("status_change_reason", sa.String(500), nullable=True))
    op.create_foreign_key("fk_foundation_org_status_changed_by", "foundation_organizations", "system_platform_accounts", ["status_changed_by"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_foundation_org_status_changed_by", "foundation_organizations", type_="foreignkey")
    op.drop_column("foundation_organizations", "status_change_reason")
    op.drop_column("foundation_organizations", "status_changed_by")
    op.drop_column("foundation_organizations", "status_changed_at")
    # PostgreSQL enum values are intentionally retained; removing them safely requires recreating the type.
