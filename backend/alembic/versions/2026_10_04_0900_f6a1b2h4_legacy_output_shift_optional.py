"""Legacy production outputs: the shift is optional.

Databases that already ran f6a1b2h2 have shift_definition_id NOT NULL. Legacy rows recorded
before shifts were tracked have no shift, and the table is read-only since PROD-OUTPUT-001,
so the column becomes nullable. A no-op where f6a1b2h2 already created it nullable.

Revision ID: f6a1b2h4
Revises: f6a1b2h3
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a1b2h4"
down_revision = "f6a1b2h3"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("production_outputs", "shift_definition_id", existing_type=sa.Uuid(), nullable=True)


def downgrade():
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT count(*) FROM production_outputs WHERE shift_definition_id IS NULL")):
        raise RuntimeError("Legacy outputs without a shift exist; they cannot be made to require one")
    op.alter_column("production_outputs", "shift_definition_id", existing_type=sa.Uuid(), nullable=False)
