"""PROJECT-FIX-002: production order numbers from a counter (PO-YYYY-NNNNNN), no longer from count()+1.

Manual and planning orders took their numbers by counting the existing orders (two formats: PO-YYYYNNNN and
PO-YYYY-NNNNNN), which could repeat after a deletion and ignored the year. production_order_counters keeps one
sequence per organization and year. Each counter starts after the highest number already issued that year in either
format, so no new order takes an old number. Existing numbers are not changed.
"""
import re
from collections import defaultdict

from alembic import op
import sqlalchemy as sa

revision = "f6a1b2n5"
down_revision = "f6a1b2n4"
branch_labels = None
depends_on = None

ISSUED = (re.compile(r"^PO-(\d{4})-(\d+)$"), re.compile(r"^PO-(\d{4})(\d{4,})$"))


def _highest(rows):
    """{(organization, year): highest sequence already issued}, from both formats; other numbers are left alone."""
    highest = defaultdict(int)
    for organization_id, number in rows:
        for pattern in ISSUED:
            m = pattern.match(number or "")
            if m:
                key = (organization_id, int(m[1]))
                highest[key] = max(highest[key], int(m[2]))
                break
    return highest


def upgrade():
    op.create_table(
        "production_order_counters",
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), primary_key=True),
        sa.Column("year", sa.Integer(), primary_key=True),
        sa.Column("last_value", sa.Integer(), nullable=False),
    )
    bind = op.get_bind()
    highest = _highest(bind.execute(sa.text("SELECT organization_id, production_order_number FROM production_orders")).all())
    for (organization_id, year), value in highest.items():
        bind.execute(sa.text("INSERT INTO production_order_counters (organization_id, year, last_value) VALUES (:o, :y, :v)"),
                     dict(o=organization_id, y=year, v=value))
        print(f"production_order_counters: {organization_id} {year} continues after {value}")


def downgrade():
    op.drop_table("production_order_counters")
