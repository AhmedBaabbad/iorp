"""Corrective-action follow-up (QUAL-CAPA-001).

- non_conformance_reports: the later review of a closed report's effectiveness (due date, result, notes, who and when).
- The report permission reports:quality:corrective_actions, granted to the system roles that run quality reports. Grants
  added here are recorded so the downgrade removes exactly them.
"""
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "f6a1b2j9"
down_revision = "f6a1b2j8"
branch_labels = None
depends_on = None

CODE, NAME = "reports:quality:corrective_actions", "Corrective actions follow-up"
ROLES = ("organization_admin", "factory_manager", "quality_manager", "viewer")
BACKUP = "quality_j9_added_grants"


def upgrade():
    bind = op.get_bind()
    add = lambda column: op.add_column("non_conformance_reports", column)  # noqa: E731
    add(sa.Column("effectiveness_due_date", sa.Date()))
    add(sa.Column("effectiveness_result", sa.String(16)))
    add(sa.Column("effectiveness_notes", sa.Text()))
    add(sa.Column("effectiveness_reviewed_at", sa.DateTime(timezone=True)))
    add(sa.Column("effectiveness_reviewed_by_user_id", sa.Uuid(), sa.ForeignKey("foundation_users.id")))
    op.create_index("ix_non_conformance_reports_effectiveness_due_date", "non_conformance_reports", ["effectiveness_due_date"])
    op.create_check_constraint("ck_non_conformance_reports_effectiveness_result", "non_conformance_reports",
                               "effectiveness_result IS NULL OR effectiveness_result IN ('effective', 'not_effective')")

    op.create_table(BACKUP, sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("role_id", sa.Uuid(), nullable=False),
                    sa.Column("permission_id", sa.Uuid(), nullable=False))
    for org in bind.scalars(sa.text("SELECT id FROM foundation_organizations")).all():
        bind.execute(sa.text("INSERT INTO foundation_permissions(id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) "
                             "VALUES (:id,:org,:code,:name,:description,'reports','quality','corrective_actions',now(),now()) ON CONFLICT (organization_id,code) DO NOTHING"),
                     dict(id=uuid4(), org=org, code=CODE, name=NAME, description="Generate quality report: " + NAME))
        pid = bind.scalar(sa.text("SELECT id FROM foundation_permissions WHERE organization_id=:org AND code=:code"), dict(org=org, code=CODE))
        roles = bind.scalars(sa.text("SELECT id FROM foundation_roles WHERE organization_id=:org AND is_system AND code IN :roles")
                             .bindparams(sa.bindparam("roles", expanding=True)), dict(org=org, roles=list(ROLES))).all()
        for rid in roles:
            added = bind.scalar(sa.text("INSERT INTO foundation_role_permissions(id,role_id,permission_id,scope) VALUES (:id,:role,:permission,'organization') "
                                        "ON CONFLICT (role_id,permission_id) DO NOTHING RETURNING id"), dict(id=uuid4(), role=rid, permission=pid))
            if added:
                bind.execute(sa.text(f"INSERT INTO {BACKUP}(id,role_id,permission_id) VALUES (:id,:role,:permission)"), dict(id=added, role=rid, permission=pid))


def downgrade():
    bind = op.get_bind()
    bind.execute(sa.text(f"DELETE FROM foundation_role_permissions WHERE id IN (SELECT id FROM {BACKUP})"))
    op.drop_table(BACKUP)
    bind.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id IN (SELECT id FROM foundation_permissions WHERE code=:code)"), dict(code=CODE))
    bind.execute(sa.text("DELETE FROM foundation_permissions WHERE code=:code"), dict(code=CODE))
    op.drop_constraint("ck_non_conformance_reports_effectiveness_result", "non_conformance_reports", type_="check")
    op.drop_index("ix_non_conformance_reports_effectiveness_due_date", table_name="non_conformance_reports")
    for name in ("effectiveness_reviewed_by_user_id", "effectiveness_reviewed_at", "effectiveness_notes", "effectiveness_result", "effectiveness_due_date"):
        op.drop_column("non_conformance_reports", name)
