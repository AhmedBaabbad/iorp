"""Quality report center permissions (QUAL-REPORT-001). No business data changes.

Adds reports:quality:{check_full,checks_summary,rejections_analysis,defects_analysis} to every organization and grants
them to the system roles that run quality reports. Grants added here are recorded so the downgrade removes only those.
"""
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = 'f6a1b2i7'
down_revision = 'f6a1b2i6'
branch_labels = None
depends_on = None

KEYS = {
    'check_full': ('Quality check report', 'تقرير فحص الجودة'),
    'checks_summary': ('Quality checks summary', 'ملخص فحوصات الجودة'),
    'rejections_analysis': ('Rejections and dispositions analysis', 'تحليل الرفض والقرارات'),
    'defects_analysis': ('Defects analysis', 'تحليل العيوب'),
}
ROLES = ('organization_admin', 'factory_manager', 'quality_manager', 'viewer')
BACKUP = 'quality_report_i7_added_grants'


def upgrade():
    bind = op.get_bind()
    op.create_table(BACKUP, sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('role_id', sa.Uuid(), nullable=False),
                    sa.Column('permission_id', sa.Uuid(), nullable=False))
    for org in bind.scalars(sa.text('SELECT id FROM foundation_organizations')).all():
        roles = bind.scalars(sa.text('SELECT id FROM foundation_roles WHERE organization_id=:org AND is_system AND code IN :roles')
                             .bindparams(sa.bindparam('roles', expanding=True)), dict(org=org, roles=list(ROLES))).all()
        for key, (en, _ar) in KEYS.items():
            code = 'reports:quality:' + key
            bind.execute(sa.text("INSERT INTO foundation_permissions(id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) "
                                 "VALUES (:id,:org,:code,:name,:description,'reports','quality',:action,now(),now()) ON CONFLICT (organization_id,code) DO NOTHING"),
                         dict(id=uuid4(), org=org, code=code, name=en, description='Generate quality report: ' + en, action=key))
            pid = bind.scalar(sa.text('SELECT id FROM foundation_permissions WHERE organization_id=:org AND code=:code'), dict(org=org, code=code))
            for rid in roles:
                added = bind.scalar(sa.text("INSERT INTO foundation_role_permissions(id,role_id,permission_id,scope) VALUES (:id,:role,:permission,'organization') "
                                            "ON CONFLICT (role_id,permission_id) DO NOTHING RETURNING id"), dict(id=uuid4(), role=rid, permission=pid))
                if added:
                    bind.execute(sa.text(f'INSERT INTO {BACKUP}(id,role_id,permission_id) VALUES (:id,:role,:permission)'), dict(id=added, role=rid, permission=pid))


def downgrade():
    bind = op.get_bind()
    bind.execute(sa.text(f'DELETE FROM foundation_role_permissions WHERE id IN (SELECT id FROM {BACKUP})'))
    op.drop_table(BACKUP)
    # Grants an administrator added later are removed with their permission rows.
    bind.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id IN (SELECT id FROM foundation_permissions WHERE code LIKE 'reports:quality:%')"))
    bind.execute(sa.text("DELETE FROM foundation_permissions WHERE code LIKE 'reports:quality:%'"))
