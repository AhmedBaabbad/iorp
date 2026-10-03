"""Shared organization branding, stored assets and report export audit.

Existing logo files remain at their current keys; no production data is changed.
"""
from uuid import uuid4
import sqlalchemy as sa
from alembic import op

revision='f6a1b2h8'
down_revision='f6a1b2h7'
branch_labels=None
depends_on=None

FIELDS={'legal_name_ar':255,'legal_name_en':255,'trade_name_ar':255,'trade_name_en':255,
        'commercial_registration_no':100,'vat_number':100,'address_ar':500,'address_en':500,
        'city':100,'country':100,'postal_code':30,'phone':60,'email':255,'website':255,'primary_color':7}

def upgrade():
    op.create_table('foundation_stored_assets',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('foundation_organizations.id'),nullable=False),sa.Column('storage_key',sa.String(500),nullable=False),sa.Column('media_type',sa.String(50),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_index('ix_foundation_stored_assets_organization_id','foundation_stored_assets',['organization_id'])
    op.create_table('foundation_organization_branding',sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('foundation_organizations.id'),primary_key=True),
        *[sa.Column(k,sa.String(n)) for k,n in FIELDS.items()],sa.Column('report_footer_note_ar',sa.Text()),sa.Column('report_footer_note_en',sa.Text()),
        sa.Column('logo_asset_id',sa.Uuid(),sa.ForeignKey('foundation_stored_assets.id')),sa.Column('secondary_logo_asset_id',sa.Uuid(),sa.ForeignKey('foundation_stored_assets.id')),
        sa.Column('updated_by_user_id',sa.Uuid(),sa.ForeignKey('foundation_users.id',ondelete='SET NULL')),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_table('report_counters',sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('foundation_organizations.id'),primary_key=True),sa.Column('module',sa.String(40),primary_key=True),sa.Column('year',sa.Integer(),primary_key=True),sa.Column('value',sa.Integer(),nullable=False))
    op.create_table('report_exports',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('foundation_organizations.id'),nullable=False),sa.Column('report_key',sa.String(120),nullable=False),sa.Column('reference_no',sa.String(100),nullable=False),sa.Column('params_json',sa.JSON(),nullable=False),sa.Column('format',sa.String(10),nullable=False),sa.Column('generated_by_user_id',sa.Uuid(),sa.ForeignKey('foundation_users.id',ondelete='SET NULL')),sa.Column('generated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('page_count',sa.Integer()),sa.Column('duration_ms',sa.Integer()),sa.Column('status',sa.String(20),nullable=False),sa.Column('error_message',sa.String(200)),sa.UniqueConstraint('organization_id','reference_no',name='uq_report_reference'))
    op.create_index('ix_report_exports_organization_id','report_exports',['organization_id'])
    op.create_index('ix_report_exports_generated_at','report_exports',['generated_at'])
    bind=op.get_bind()
    for org,path in bind.execute(sa.text('SELECT id,logo_path FROM foundation_organizations WHERE logo_path IS NOT NULL')):
        asset=uuid4(); media={'jpg':'image/jpeg','jpeg':'image/jpeg','webp':'image/webp'}.get(path.rsplit('.',1)[-1].lower(),'image/png')
        bind.execute(sa.text('INSERT INTO foundation_stored_assets(id,organization_id,storage_key,media_type) VALUES (:id,:org,:key,:media)'),dict(id=asset,org=org,key=path,media=media))
        bind.execute(sa.text('INSERT INTO foundation_organization_branding(organization_id,logo_asset_id) VALUES (:org,:asset)'),dict(org=org,asset=asset))
    # Grants are based on existing permissions, never role names.
    mappings={'organization:branding:read':'foundation:organization:read','organization:branding:update':'foundation:organization:branding',
              'reports:production:order_full':'production:production_orders:read','reports:production:orders_summary':'production:production_orders:read',
              'reports:production:results_analysis':'production:results:read','reports:production:shift_workforce':'workforce:members:read',
              'reports:exports:read':'foundation:audit:read'}
    for org in bind.scalars(sa.text('SELECT id FROM foundation_organizations')):
        for code,source in mappings.items():
            pid=uuid4(); module,resource,action=code.split(':')
            bind.execute(sa.text('INSERT INTO foundation_permissions(id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) VALUES (:id,:org,:code,:name,:description,:module,:resource,:action,now(),now()) ON CONFLICT (organization_id,code) DO NOTHING'),dict(id=pid,org=org,code=code,name=code,description=code,module=module,resource=resource,action=action))
            pid=bind.scalar(sa.text('SELECT id FROM foundation_permissions WHERE organization_id=:org AND code=:code'),dict(org=org,code=code))
            for role,scope in bind.execute(sa.text('SELECT rp.role_id,rp.scope FROM foundation_role_permissions rp JOIN foundation_permissions p ON p.id=rp.permission_id WHERE p.organization_id=:org AND p.code=:source'),dict(org=org,source=source)):
                bind.execute(sa.text('INSERT INTO foundation_role_permissions(id,role_id,permission_id,scope) VALUES (:id,:role,:permission,:scope) ON CONFLICT (role_id,permission_id) DO NOTHING'),dict(id=uuid4(),role=role,permission=pid,scope=scope))

def downgrade():
    bind=op.get_bind()
    if bind.scalar(sa.text('SELECT count(*) FROM report_exports')) or bind.scalar(sa.text('SELECT count(*) FROM foundation_organization_branding WHERE updated_by_user_id IS NOT NULL')):
        raise RuntimeError('Export audit or edited branding exists; preserve it before downgrade')
    for table in ('report_exports','report_counters','foundation_organization_branding','foundation_stored_assets'):
        op.drop_table(table)
    # Existing organization.logo_path and stored files are preserved. Permission grants are harmless without routes.
