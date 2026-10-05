"""Lot values entered by the inspector when the order line lacks them (QUAL-SPEC-002). No existing data changes."""
import sqlalchemy as sa
from alembic import op

revision = "f6a1b2j0"
down_revision = "f6a1b2i9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("quality_checks", sa.Column("lot_values", sa.JSON()))


def downgrade():
    op.drop_column("quality_checks", "lot_values")
