"""SALES-DISC-001: a quotation's discount is a percentage of each line, taken before VAT.

- commercial_quote_items gains discount_percent (0-100) and discount_amount; the quotation's discount_amount becomes
  the sum of its lines' amounts.
- A quotation saved with a fixed discount amount gets the equivalent percentage on every line (amount / subtotal),
  and its discount, VAT (when its rate is known) and total are recomputed from the lines; each change is printed.
- commercial_order_items.agreed_unit_price keeps four places, so a sales order made from a discounted quotation agrees
  the net price exactly (12.35 less 7 % = 11.4855).
"""
from decimal import ROUND_HALF_UP, Decimal

from alembic import op
import sqlalchemy as sa

revision = "f6a1b2n4"
down_revision = "f6a1b2n3"
branch_labels = None
depends_on = None

HALALA = Decimal("0.01")


def _money(value):
    return Decimal(value).quantize(HALALA, rounding=ROUND_HALF_UP)


def upgrade():
    bind = op.get_bind()
    with op.batch_alter_table("commercial_quote_items") as batch:
        batch.add_column(sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False, server_default="0"))
        batch.create_check_constraint("ck_quote_item_discount_percent", "discount_percent >= 0 AND discount_percent <= 100")
    with op.batch_alter_table("commercial_order_items") as batch:
        batch.alter_column("agreed_unit_price", existing_type=sa.Numeric(14, 2), type_=sa.Numeric(14, 4), existing_nullable=True)

    quotes = bind.execute(sa.text("SELECT id, quote_number, subtotal_amount, discount_amount, tax_rate, tax_amount, total_amount "
                                  "FROM commercial_quotes WHERE discount_amount > 0 AND subtotal_amount > 0")).all()
    for qid, number, subtotal, discount, rate, tax, total in quotes:
        percent = (Decimal(discount) * 100 / Decimal(subtotal)).quantize(HALALA, rounding=ROUND_HALF_UP)
        new_discount = Decimal("0")
        for item_id, line_total in bind.execute(sa.text("SELECT id, line_total FROM commercial_quote_items WHERE quote_id = :q"), dict(q=qid)).all():
            amount = _money(Decimal(line_total) * percent / 100)
            new_discount += amount
            bind.execute(sa.text("UPDATE commercial_quote_items SET discount_percent = :p, discount_amount = :a WHERE id = :i"),
                         dict(p=percent, a=amount, i=item_id))
        new_tax = _money((Decimal(subtotal) - new_discount) * Decimal(rate) / 100) if rate is not None else Decimal(tax)
        new_total = Decimal(subtotal) - new_discount + new_tax
        bind.execute(sa.text("UPDATE commercial_quotes SET discount_amount = :d, tax_amount = :t, total_amount = :tt WHERE id = :q"),
                     dict(d=new_discount, t=new_tax, tt=new_total, q=qid))
        print(f"{number}: discount {discount} -> {percent}% on every line = {new_discount}; total {total} -> {new_total}")
    print(f"commercial_quotes: {len(quotes)} fixed discount(s) turned into a percentage")


def downgrade():
    # The quotation keeps its discount amount (the sum of its lines); the lines lose their percentages.
    with op.batch_alter_table("commercial_order_items") as batch:
        batch.alter_column("agreed_unit_price", existing_type=sa.Numeric(14, 4), type_=sa.Numeric(14, 2), existing_nullable=True)
    with op.batch_alter_table("commercial_quote_items") as batch:
        batch.drop_constraint("ck_quote_item_discount_percent", type_="check")
        batch.drop_column("discount_amount")
        batch.drop_column("discount_percent")
