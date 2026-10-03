"""Quotation document (QUOTE-DOC-001): terms settings, signature, bank accounts, bilingual lines.

- commercial_quote_settings / commercial_quote_terms: the organization's signature title and its
  bilingual terms and conditions, printed on every quotation document.
- foundation_bank_accounts: company bank accounts printed in the quotation footer (several allowed).
- commercial_quotes: attention, subject, tax_rate (VAT % applied by the server).
- commercial_quote_items: description_ar / description_en (the printed line).
- Permissions commercial:quote_settings:{read,update}, granted to the organization administrator and
  commercial manager system roles (they hold commercial:* / ALL). Added grants are recorded so the
  downgrade removes exactly those. No existing quote or item value changes.
"""
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "f6a1b2i3"
down_revision = "f6a1b2i2"
branch_labels = None
depends_on = None

CODES = {"commercial:quote_settings:read": ("read", "Read quotation settings"),
         "commercial:quote_settings:update": ("update", "Update quotation settings")}
ROLES = ("organization_admin", "commercial_manager")
BACKUP = "quote_settings_i3_added"


def upgrade():
    op.create_table(
        "commercial_quote_settings",
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), primary_key=True),
        sa.Column("signature_title_ar", sa.String(255)),
        sa.Column("signature_title_en", sa.String(255)),
        sa.Column("show_preparer_name", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_by_user_id", sa.Uuid(), sa.ForeignKey("foundation_users.id", ondelete="SET NULL")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "commercial_quote_terms",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("title_ar", sa.String(120), nullable=False),
        sa.Column("title_en", sa.String(120)),
        sa.Column("body_ar", sa.Text(), nullable=False),
        sa.Column("body_en", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_commercial_quote_terms_org_order", "commercial_quote_terms", ["organization_id", "sort_order"])
    op.create_table(
        "foundation_bank_accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bank_name_ar", sa.String(255), nullable=False),
        sa.Column("bank_name_en", sa.String(255)),
        sa.Column("account_name", sa.String(255)),
        sa.Column("account_number", sa.String(64)),
        sa.Column("iban", sa.String(34), nullable=False),
        sa.Column("swift_code", sa.String(11)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_foundation_bank_accounts_organization_id", "foundation_bank_accounts", ["organization_id"])
    op.add_column("commercial_quotes", sa.Column("tax_rate", sa.Numeric(5, 2)))
    op.add_column("commercial_quotes", sa.Column("attention", sa.String(255)))
    op.add_column("commercial_quotes", sa.Column("subject", sa.String(255)))
    op.add_column("commercial_quote_items", sa.Column("description_ar", sa.Text()))
    op.add_column("commercial_quote_items", sa.Column("description_en", sa.Text()))

    bind = op.get_bind()
    op.create_table(BACKUP, sa.Column("id", sa.Uuid(), primary_key=True))
    for org in bind.scalars(sa.text("SELECT id FROM foundation_organizations")).all():
        for code, (action, name) in CODES.items():
            bind.execute(sa.text(
                "INSERT INTO foundation_permissions (id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) "
                "VALUES (:id,:org,:code,:name,:description,'commercial','quote_settings',:action,now(),now()) ON CONFLICT (organization_id,code) DO NOTHING"),
                dict(id=uuid4(), org=org, code=code, name=name, description=f"Allows the account to {name.lower()}.", action=action))
            permission = bind.scalar(sa.text("SELECT id FROM foundation_permissions WHERE organization_id=:org AND code=:code"), dict(org=org, code=code))
            for role in bind.scalars(sa.text("SELECT id FROM foundation_roles WHERE organization_id=:org AND is_system AND code IN :roles")
                                     .bindparams(sa.bindparam("roles", expanding=True)), dict(org=org, roles=list(ROLES))):
                added = bind.scalar(sa.text("INSERT INTO foundation_role_permissions (id,role_id,permission_id,scope) VALUES (:id,:role,:permission,'organization') "
                                            "ON CONFLICT (role_id,permission_id) DO NOTHING RETURNING id"), dict(id=uuid4(), role=role, permission=permission))
                if added:
                    bind.execute(sa.text(f"INSERT INTO {BACKUP} (id) VALUES (:id)"), dict(id=added))


def downgrade():
    bind = op.get_bind()
    bind.execute(sa.text(f"DELETE FROM foundation_role_permissions WHERE id IN (SELECT id FROM {BACKUP})"))
    op.drop_table(BACKUP)
    bind.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id IN "
                         "(SELECT id FROM foundation_permissions WHERE code LIKE 'commercial:quote_settings:%')"))
    bind.execute(sa.text("DELETE FROM foundation_permissions WHERE code LIKE 'commercial:quote_settings:%'"))
    op.drop_column("commercial_quote_items", "description_en")
    op.drop_column("commercial_quote_items", "description_ar")
    op.drop_column("commercial_quotes", "subject")
    op.drop_column("commercial_quotes", "attention")
    op.drop_column("commercial_quotes", "tax_rate")
    op.drop_index("ix_foundation_bank_accounts_organization_id", table_name="foundation_bank_accounts")
    op.drop_table("foundation_bank_accounts")
    op.drop_index("ix_commercial_quote_terms_org_order", table_name="commercial_quote_terms")
    op.drop_table("commercial_quote_terms")
    op.drop_table("commercial_quote_settings")
