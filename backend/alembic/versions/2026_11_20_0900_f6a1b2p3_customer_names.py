"""Bilingual customer names with a lossless rollback recovery table."""
import unicodedata

from alembic import op
import sqlalchemy as sa

revision = 'f6a1b2p3'
down_revision = 'f6a1b2p2'
branch_labels = None
depends_on = None

CHECK = 'ck_commercial_customers_name_required'
RECOVERY = 'commercial_customer_name_recovery'


def arabic(value):
    ranges = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x0870, 0x089F),
              (0x08A0, 0x08FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF),
              (0x10EC0, 0x10EFF), (0x1EE00, 0x1EEFF))
    return any(unicodedata.category(c).startswith('L') and
               any(lo <= ord(c) <= hi for lo, hi in ranges) for c in value)


def upgrade():
    bind = op.get_bind()
    op.add_column('commercial_customers', sa.Column('name_ar', sa.String(255), nullable=True))
    op.add_column('commercial_customers', sa.Column('name_en', sa.String(255), nullable=True))
    customers = sa.Table('commercial_customers', sa.MetaData(), autoload_with=bind)
    recovery = (sa.Table(RECOVERY, sa.MetaData(), autoload_with=bind)
                if sa.inspect(bind).has_table(RECOVERY) else None)
    # Keyset batches avoid buffering the customer table or changing original names.
    last = None
    while True:
        query = sa.select(customers.c.id, customers.c.name).order_by(customers.c.id).limit(500)
        if last is not None:
            query = query.where(customers.c.id > last)
        rows = bind.execute(query).all()
        if not rows:
            break
        saved = {}
        if recovery is not None:
            for saved_row in bind.execute(sa.select(recovery).where(
                    recovery.c.id.in_([r.id for r in rows])).order_by(recovery.c.saved_at.desc())):
                saved.setdefault((saved_row.id, saved_row.name), saved_row)
        for row in rows:
            old = saved.get((row.id, row.name))
            if old is not None:
                values = dict(name_ar=old.name_ar, name_en=old.name_en)
            else:
                values = dict(name_ar=row.name if arabic(row.name) else None,
                              name_en=None if arabic(row.name) else row.name)
            bind.execute(customers.update().where(customers.c.id == row.id).values(**values))
        last = rows[-1].id
    op.create_check_constraint(CHECK, 'commercial_customers',
        'coalesce(length(trim(name_ar)), 0) > 0 OR coalesce(length(trim(name_en)), 0) > 0')
    # Recovery rows remain private data if old-version edits prevented restoring them.
    # Never discard an alternative name just because the legacy name was edited.


def downgrade():
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(RECOVERY):
        op.create_table(RECOVERY,
                        sa.Column('snapshot_id', sa.Uuid(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
                        sa.Column('saved_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('clock_timestamp()')),
                        sa.Column('id', sa.Uuid(), nullable=False, index=True),
                        sa.Column('name', sa.String(255), nullable=False),
                        sa.Column('name_ar', sa.String(255)), sa.Column('name_en', sa.String(255)))
    recovery = sa.Table(RECOVERY, sa.MetaData(), autoload_with=bind)
    customers = sa.Table('commercial_customers', sa.MetaData(), autoload_with=bind)
    # Append snapshots: repeated rollback must not overwrite older alternative names.
    bind.execute(recovery.insert().from_select(['id', 'name', 'name_ar', 'name_en'],
        sa.select(customers.c.id, customers.c.name, customers.c.name_ar, customers.c.name_en)))
    op.drop_constraint(CHECK, 'commercial_customers', type_='check')
    op.drop_column('commercial_customers', 'name_en')
    op.drop_column('commercial_customers', 'name_ar')
