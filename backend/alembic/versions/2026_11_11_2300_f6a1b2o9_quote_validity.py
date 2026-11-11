"""UX-BATCH-A: organization quotation validity policy."""
from alembic import op
import sqlalchemy as sa

revision = "f6a1b2o9"
down_revision = "f6a1b2o8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("commercial_quote_settings", sa.Column("quote_validity_days", sa.Integer(), nullable=False, server_default="10"))
    op.create_check_constraint("ck_quote_validity_days_range", "commercial_quote_settings", "quote_validity_days BETWEEN 1 AND 365")


def downgrade():
    op.drop_constraint("ck_quote_validity_days_range", "commercial_quote_settings", type_="check")
    op.drop_column("commercial_quote_settings", "quote_validity_days")
