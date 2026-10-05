"""Non-conformance reports redesigned (QUAL-NCR-002).

- non_conformance_reports.status: the native enum becomes text with a check — open, investigation, action, verification,
  closed, cancelled (draft → open, under_review → investigation); new columns for severity, sources (production order,
  return, customer, supplier), owner and due date, containment, root cause, verification, the action with the supplier,
  costs and claim.
- non_conformance_items: quantity to three decimals, disposition and its notes.
- quality_ncr_actions (corrective actions) and quality_ncr_attachments.
- The NCR numbers continue from the quality counter (kind NCR), seeded from the numbers already issued.
- Permissions quality:ncr_reports:{verify,cancel} and quality:ncr_actions:{read,complete}, and the departments that own
  causes may read reports (warehouse also create), granted as the system roles define them. Grants added here are recorded
  so the downgrade removes exactly them.
"""
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "f6a1b2j6"
down_revision = "f6a1b2j5"
branch_labels = None
depends_on = None

BACKUP = "quality_j6_added_grants"
NAMES = {
    "quality:ncr_reports:verify": "Verify Corrective Actions and Close NCRs", "quality:ncr_reports:cancel": "Cancel Non-Conformance Reports",
    "quality:ncr_actions:read": "Read Corrective Actions", "quality:ncr_actions:complete": "Complete Corrective Actions",
}
NEW = tuple(NAMES)
OWNER = ("quality:ncr_reports:read", "quality:ncr_actions:read", "quality:ncr_actions:complete")
ROLES = {
    "organization_admin": NEW, "quality_manager": NEW, "factory_manager": NEW,
    "safety_manager": ("quality:ncr_actions:read", "quality:ncr_actions:complete"),
    "production_manager": OWNER, "maintenance_manager": OWNER, "procurement_manager": OWNER,
    "warehouse_manager": (*OWNER, "quality:ncr_reports:create"), "viewer": ("quality:ncr_actions:read",),
}
STATUSES = "('open', 'investigation', 'action', 'verification', 'closed', 'cancelled')"


def upgrade():
    bind = op.get_bind()
    uuid, dt, money = sa.Uuid(), sa.DateTime(timezone=True), sa.Numeric(14, 2)
    user = lambda name, nullable=True: sa.Column(name, uuid, sa.ForeignKey("foundation_users.id"), nullable=nullable)  # noqa: E731

    op.execute("ALTER TABLE non_conformance_reports ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE non_conformance_reports ALTER COLUMN status TYPE varchar(16) USING (CASE status::text "
               "WHEN 'draft' THEN 'open' WHEN 'under_review' THEN 'investigation' ELSE status::text END)")
    op.execute("ALTER TABLE non_conformance_reports ALTER COLUMN status SET DEFAULT 'open'")
    op.execute("DROP TYPE IF EXISTS quality_ncr_status")
    op.create_check_constraint("ck_non_conformance_reports_status", "non_conformance_reports", f"status IN {STATUSES}")
    add = lambda column: op.add_column("non_conformance_reports", column)  # noqa: E731
    add(sa.Column("severity", sa.String(12), nullable=False, server_default="major"))
    for name in ("production_order_id", "return_id", "customer_id", "supplier_id"):
        add(sa.Column(name, uuid))
        op.create_index(f"ix_non_conformance_reports_{name}", "non_conformance_reports", [name])
    add(sa.Column("customer_name", sa.String(255)))
    add(sa.Column("supplier_name", sa.String(255)))
    add(sa.Column("supplier_reference", sa.String(120)))
    add(user("owner_user_id"))
    add(sa.Column("due_date", sa.Date()))
    add(sa.Column("containment", sa.Text()))
    add(sa.Column("contained_at", dt))
    add(user("contained_by_user_id"))
    add(sa.Column("root_cause_category", sa.String(16)))
    add(sa.Column("root_cause_method", sa.String(16)))
    add(sa.Column("root_cause", sa.Text()))
    add(sa.Column("action_required", sa.Boolean()))
    add(sa.Column("no_action_justification", sa.Text()))
    add(sa.Column("investigated_at", dt))
    add(user("investigated_by_user_id"))
    add(sa.Column("verification_attempts", sa.Integer(), nullable=False, server_default="0"))
    add(sa.Column("verification_notes", sa.Text()))
    add(sa.Column("verified_at", dt))
    add(user("verified_by_user_id"))
    add(sa.Column("closed_at", dt))
    add(sa.Column("cancel_reason", sa.Text()))
    add(sa.Column("supplier_action", sa.String(16), nullable=False, server_default="none"))
    add(sa.Column("supplier_response", sa.Text()))
    add(sa.Column("supplier_responded_at", sa.Date()))
    for name in ("cost_material", "cost_labor", "cost_scrap", "cost_transport", "cost_other", "claim_amount"):
        add(sa.Column(name, money))
    add(sa.Column("claim_status", sa.String(12), nullable=False, server_default="none"))
    op.create_index("ix_non_conformance_reports_org_status", "non_conformance_reports", ["organization_id", "status"])

    op.alter_column("non_conformance_items", "quantity_affected", type_=sa.Numeric(14, 3), existing_type=sa.Numeric(14, 2))
    op.add_column("non_conformance_items", sa.Column("disposition", sa.String(24)))
    op.add_column("non_conformance_items", sa.Column("disposition_notes", sa.Text()))

    org = lambda: sa.Column("organization_id", uuid, sa.ForeignKey("foundation_organizations.id"), nullable=False)  # noqa: E731
    report = lambda: sa.Column("ncr_id", uuid, sa.ForeignKey("non_conformance_reports.id"), nullable=False)  # noqa: E731
    op.create_table("quality_ncr_actions", sa.Column("id", uuid, primary_key=True), org(), report(),
                    sa.Column("line_no", sa.Integer(), nullable=False), sa.Column("kind", sa.String(12), nullable=False),
                    sa.Column("description", sa.Text(), nullable=False), user("owner_user_id"), sa.Column("owner_name", sa.String(200)),
                    sa.Column("due_date", sa.Date()), sa.Column("status", sa.String(12), nullable=False, server_default="open"),
                    sa.Column("evidence", sa.Text()), sa.Column("completed_at", dt), user("completed_by_user_id"),
                    sa.Column("cancel_reason", sa.Text()), user("created_by_user_id", False),
                    sa.Column("created_at", dt, nullable=False), sa.Column("updated_at", dt, nullable=False),
                    sa.UniqueConstraint("ncr_id", "line_no", name="uq_quality_ncr_actions_line"),
                    sa.CheckConstraint("kind IN ('correction', 'corrective', 'preventive')", name="ck_quality_ncr_actions_kind"),
                    sa.CheckConstraint("status IN ('open', 'done', 'cancelled')", name="ck_quality_ncr_actions_status"))
    op.create_index("ix_quality_ncr_actions_ncr_id", "quality_ncr_actions", ["ncr_id"])
    op.create_index("ix_quality_ncr_actions_owner_user_id", "quality_ncr_actions", ["owner_user_id"])
    op.create_index("ix_quality_ncr_actions_org_status", "quality_ncr_actions", ["organization_id", "status"])
    op.create_table("quality_ncr_attachments", sa.Column("id", uuid, primary_key=True), org(), report(),
                    sa.Column("file_name", sa.String(255), nullable=False), sa.Column("content_type", sa.String(80), nullable=False),
                    sa.Column("size_bytes", sa.Integer(), nullable=False), sa.Column("storage_path", sa.String(500), nullable=False),
                    user("uploaded_by_user_id", False), sa.Column("uploaded_at", dt, nullable=False))
    op.create_index("ix_quality_ncr_attachments_ncr_id", "quality_ncr_attachments", ["ncr_id"])

    # Numbers continue from what was issued: NCR-YYYY-NNNN -> the counter of that organization and year.
    op.execute("""
        INSERT INTO quality_code_counters (organization_id, kind, year, value)
        SELECT organization_id, 'NCR', CAST(split_part(report_number, '-', 2) AS integer), MAX(CAST(split_part(report_number, '-', 3) AS integer))
        FROM non_conformance_reports WHERE report_number ~ '^NCR-[0-9]{4}-[0-9]+$'
        GROUP BY organization_id, split_part(report_number, '-', 2)
        ON CONFLICT (organization_id, kind, year) DO UPDATE SET value = GREATEST(quality_code_counters.value, EXCLUDED.value)""")

    op.create_table(BACKUP, sa.Column("id", uuid, primary_key=True), sa.Column("role_id", uuid, nullable=False),
                    sa.Column("permission_id", uuid, nullable=False))
    backup = sa.table(BACKUP, sa.column("id"), sa.column("role_id"), sa.column("permission_id"))
    bind.execute(sa.text("UPDATE foundation_permissions SET name=:name, description=:description WHERE code='quality:ncr_reports:update'"),
                 dict(name="Work Non-Conformance Reports (containment, root cause, actions)",
                      description="Work Non-Conformance Reports (containment, root cause, actions)"))
    for organization in bind.scalars(sa.text("SELECT id FROM foundation_organizations")).all():
        for code, name in NAMES.items():
            _module, resource, action = code.split(":")
            bind.execute(sa.text("INSERT INTO foundation_permissions (id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) "
                                 "VALUES (:id,:org,:code,:name,:description,'quality',:resource,:action,now(),now()) ON CONFLICT (organization_id,code) DO NOTHING"),
                         dict(id=uuid4(), org=organization, code=code, name=name, description=name, resource=resource, action=action))
        ids = dict(bind.execute(sa.text("SELECT code, id FROM foundation_permissions WHERE organization_id=:org AND module_name='quality'"),
                                dict(org=organization)).all())
        roles = dict(bind.execute(sa.text("SELECT code, id FROM foundation_roles WHERE organization_id=:org AND is_system"), dict(org=organization)).all())
        for role, codes in ROLES.items():
            if role not in roles:
                continue
            for code in codes:
                if code not in ids:
                    continue
                added = bind.scalar(sa.text("INSERT INTO foundation_role_permissions (id,role_id,permission_id,scope) VALUES (:id,:role,:p,'organization') "
                                            "ON CONFLICT (role_id,permission_id) DO NOTHING RETURNING id"), dict(id=uuid4(), role=roles[role], p=ids[code]))
                if added:
                    bind.execute(backup.insert().values(id=added, role_id=roles[role], permission_id=ids[code]))


def downgrade():
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT count(*) FROM quality_ncr_actions")) or bind.scalar(sa.text("SELECT count(*) FROM quality_ncr_attachments")) or \
            bind.scalar(sa.text("SELECT count(*) FROM non_conformance_reports WHERE status IN ('action', 'verification', 'cancelled')")):
        raise RuntimeError("Reports with corrective actions, files or later stages exist; they are records and are not dropped by a downgrade.")
    bind.execute(sa.text(f"DELETE FROM foundation_role_permissions WHERE id IN (SELECT id FROM {BACKUP})"))
    op.drop_table(BACKUP)
    codes = sa.bindparam("codes", expanding=True)
    bind.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id IN (SELECT id FROM foundation_permissions WHERE code IN :codes)").bindparams(codes),
                 dict(codes=list(NEW)))
    bind.execute(sa.text("DELETE FROM foundation_permissions WHERE code IN :codes").bindparams(codes), dict(codes=list(NEW)))
    bind.execute(sa.text("UPDATE foundation_permissions SET name='Update ncr reports', description='Update ncr reports' WHERE code='quality:ncr_reports:update'"))
    op.execute("DELETE FROM quality_code_counters WHERE kind = 'NCR'")
    op.drop_table("quality_ncr_attachments")
    op.drop_table("quality_ncr_actions")
    op.drop_column("non_conformance_items", "disposition_notes")
    op.drop_column("non_conformance_items", "disposition")
    op.alter_column("non_conformance_items", "quantity_affected", type_=sa.Numeric(14, 2), existing_type=sa.Numeric(14, 3))
    op.drop_index("ix_non_conformance_reports_org_status", "non_conformance_reports")
    for name in ("production_order_id", "return_id", "customer_id", "supplier_id"):
        op.drop_index(f"ix_non_conformance_reports_{name}", "non_conformance_reports")
    for name in ("severity", "production_order_id", "return_id", "customer_id", "supplier_id", "customer_name", "supplier_name", "supplier_reference",
                 "owner_user_id", "due_date", "containment", "contained_at", "contained_by_user_id", "root_cause_category", "root_cause_method",
                 "root_cause", "action_required", "no_action_justification", "investigated_at", "investigated_by_user_id", "verification_attempts",
                 "verification_notes", "verified_at", "verified_by_user_id", "closed_at", "cancel_reason", "supplier_action", "supplier_response",
                 "supplier_responded_at", "cost_material", "cost_labor", "cost_scrap", "cost_transport", "cost_other", "claim_amount", "claim_status"):
        op.drop_column("non_conformance_reports", name)
    op.drop_constraint("ck_non_conformance_reports_status", "non_conformance_reports", type_="check")
    op.execute("CREATE TYPE quality_ncr_status AS ENUM ('draft', 'open', 'under_review', 'closed')")
    op.execute("ALTER TABLE non_conformance_reports ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE non_conformance_reports ALTER COLUMN status TYPE quality_ncr_status USING (CASE status "
               "WHEN 'investigation' THEN 'under_review' ELSE status END)::quality_ncr_status")
    op.execute("ALTER TABLE non_conformance_reports ALTER COLUMN status SET DEFAULT 'draft'")
