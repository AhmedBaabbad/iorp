"""Simpler shipment lines (SHIP-003): description, width and thickness (mm), quantity and unit, one full weight.

- width_mm / thickness_mm come from the line's specification (its width_mm / thickness_mm values, when numeric).
- weight is the line's gross weight, else its net weight (in the same weight unit).
- specification_json, package_count, package_type, net_weight, gross_weight, batch_no and notes are dropped.
"""
import sqlalchemy as sa
from alembic import op

revision = "f6a1b2j3"
down_revision = "f6a1b2j2"
branch_labels = None
depends_on = None

NUMBER = "'^[0-9]+(\\.[0-9]+)?$'"


def upgrade():
    op.add_column("shipping_shipment_lines", sa.Column("width_mm", sa.Numeric(10, 3)))
    op.add_column("shipping_shipment_lines", sa.Column("thickness_mm", sa.Numeric(10, 3)))
    op.add_column("shipping_shipment_lines", sa.Column("weight", sa.Numeric(14, 3)))
    op.execute(f"""
        UPDATE shipping_shipment_lines SET
          width_mm = CASE WHEN (specification_json->>'width_mm') ~ {NUMBER} THEN (specification_json->>'width_mm')::numeric END,
          thickness_mm = CASE WHEN (specification_json->>'thickness_mm') ~ {NUMBER} THEN (specification_json->>'thickness_mm')::numeric END,
          weight = COALESCE(gross_weight, net_weight)""")
    for column in ("specification_json", "package_count", "package_type", "net_weight", "gross_weight", "batch_no", "notes"):
        op.drop_column("shipping_shipment_lines", column)


def downgrade():
    op.add_column("shipping_shipment_lines", sa.Column("specification_json", sa.JSON()))
    op.add_column("shipping_shipment_lines", sa.Column("package_count", sa.Integer()))
    op.add_column("shipping_shipment_lines", sa.Column("package_type", sa.String(40)))
    op.add_column("shipping_shipment_lines", sa.Column("net_weight", sa.Numeric(14, 3)))
    op.add_column("shipping_shipment_lines", sa.Column("gross_weight", sa.Numeric(14, 3)))
    op.add_column("shipping_shipment_lines", sa.Column("batch_no", sa.String(80)))
    op.add_column("shipping_shipment_lines", sa.Column("notes", sa.String(500)))
    op.execute("""
        UPDATE shipping_shipment_lines SET gross_weight = weight,
          specification_json = NULLIF(jsonb_strip_nulls(jsonb_build_object('width_mm', width_mm, 'thickness_mm', thickness_mm)), '{}'::jsonb)::json""")
    for column in ("weight", "thickness_mm", "width_mm"):
        op.drop_column("shipping_shipment_lines", column)
