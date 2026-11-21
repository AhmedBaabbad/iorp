"""Normalize saved phone numbers; invalid legacy values are retained, never logged."""
import logging
import re
from alembic import op
import sqlalchemy as sa

revision = 'f6a1b2p6'
down_revision = 'f6a1b2p5'
branch_labels = depends_on = None
log = logging.getLogger('alembic.runtime.migration')

# Frozen normalization rules from app/core/phones.py, independent of future application changes.
def normalize(value):
    if value is None or not value.strip():return None
    digits = {**{0x0660+i:str(i) for i in range(10)}, **{0x06F0+i:str(i) for i in range(10)}}
    text = re.sub(r'[\s\-().]', '', value.strip().translate(digits))
    if text.startswith('00'):text = '+' + text[2:]
    if re.fullmatch(r'0\d{8,9}', text):text = '+966' + text[1:]
    if not re.fullmatch(r'\+\d{8,15}', text):raise ValueError('PHONE_INVALID')
    return text

FIELDS = [
    ('commercial_customers','phone',50), ('commercial_customer_contacts','phone',50),
    ('workforce_members','phone',50), ('shipping_drivers','phone',30),
    ('shipping_carriers','phone',30), ('procurement_suppliers','phone',20),
    ('procurement_supplier_contacts','phone',30), ('foundation_users','phone',50),
    ('foundation_organization_branding','phone',60),
    ('shipping_shipments','driver_phone',20), ('shipping_shipments','consignee_phone',20),
]

def upgrade():
    bind = op.get_bind()
    for table_name, column, old_length in FIELDS:
        key = 'organization_id' if table_name == 'foundation_organization_branding' else 'id'
        table = sa.table(table_name, sa.column(key,sa.Uuid()), sa.column(column,sa.String()))
        oversized = False
        for record_id, value in bind.execute(sa.select(table.c[key],table.c[column])).all():
            try:
                converted = normalize(value)
            except ValueError:
                log.warning('Phone normalization skipped: table=%s column=%s id=%s',table_name,column,record_id)
                converted = value
            if converted is not None and len(converted)>30:oversized = True
            if converted != value:
                bind.execute(table.update().where(table.c[key]==record_id).values({column:converted}))
        # Do not truncate an unconvertible legacy value to narrow a column. New writes are limited to 30.
        if old_length != 30 and not oversized:
            op.alter_column(table_name,column,type_=sa.String(30),existing_type=sa.String(old_length),existing_nullable=True)

def downgrade():
    # Normalized phone values and invalid retained values are not restored to their old representation.
    # Keep the widened 30-character storage too: narrowing could truncate retained legacy values.
    pass
