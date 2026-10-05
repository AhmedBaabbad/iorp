"""Shipment lines like quotation lines (SHIP-002).

- The specification becomes property/value JSON (specification_json), as on quotation lines; a free-text specification
  already written is kept as {"specification": "<text>"}.
- Weights carry their unit: net_weight_kg / gross_weight_kg become net_weight / gross_weight with weight_unit = 'kg'
  (their existing values stay in kilograms).
Units come from the shared catalogue (app/core/units.py); existing rows are not changed.
"""
import sqlalchemy as sa
from alembic import op

revision = "f6a1b2j2"
down_revision = "f6a1b2j1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("shipping_shipment_lines", sa.Column("specification_json", sa.JSON()))
    op.execute("UPDATE shipping_shipment_lines SET specification_json = json_build_object('specification', specification) "
               "WHERE specification IS NOT NULL AND specification <> ''")
    op.drop_column("shipping_shipment_lines", "specification")
    op.alter_column("shipping_shipment_lines", "net_weight_kg", new_column_name="net_weight")
    op.alter_column("shipping_shipment_lines", "gross_weight_kg", new_column_name="gross_weight")
    op.add_column("shipping_shipment_lines", sa.Column("weight_unit", sa.String(8), nullable=False, server_default="kg"))
    op.create_check_constraint("ck_shipping_lines_weight_unit", "shipping_shipment_lines", "weight_unit IN ('g', 'kg', 'ton', 'lb', 'oz')")


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM shipping_shipment_lines WHERE weight_unit <> 'kg'")):
        raise RuntimeError("Lines with weights in other units exist; they cannot be stored as kilograms without converting them.")
    op.drop_constraint("ck_shipping_lines_weight_unit", "shipping_shipment_lines", type_="check")
    op.drop_column("shipping_shipment_lines", "weight_unit")
    op.alter_column("shipping_shipment_lines", "gross_weight", new_column_name="gross_weight_kg")
    op.alter_column("shipping_shipment_lines", "net_weight", new_column_name="net_weight_kg")
    op.add_column("shipping_shipment_lines", sa.Column("specification", sa.String(500)))
    op.execute("UPDATE shipping_shipment_lines SET specification = left(specification_json::text, 500) WHERE specification_json IS NOT NULL")
    op.drop_column("shipping_shipment_lines", "specification_json")
