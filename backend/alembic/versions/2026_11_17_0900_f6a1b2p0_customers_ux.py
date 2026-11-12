"""Customer geography, optional atomic contact and legacy contact migration.

Downgrade retains seeded lists and migrated contacts: these are compatible with
the previous schema and may have been edited or referenced after migration.
"""
from uuid import UUID, uuid5

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

revision = "f6a1b2p0"
down_revision = "f6a1b2o9"
branch_labels = None
depends_on = None


def migrate_contacts(connection):
    """Idempotent, tenant-scoped; an edited migrated contact is not recreated."""
    tables = sa.MetaData()
    customers = sa.Table("commercial_customers", tables, autoload_with=connection)
    contacts = sa.Table("commercial_customer_contacts", tables, autoload_with=connection)
    organizations = sa.Table("foundation_organizations", tables, autoload_with=connection)
    locales = dict(connection.execute(sa.select(organizations.c.id, organizations.c.default_locale)).all())
    count = 0
    query = sa.select(customers).where(sa.or_(customers.c.phone.is_not(None), customers.c.email.is_not(None))).with_for_update()
    for row in connection.execute(query).mappings():
        phone = (row["phone"] or "").strip() or None
        email = (row["email"] or "").strip() or None
        if not phone and not email:
            continue
        contact_id = uuid5(UUID("fe48d2ca-5304-4fb7-91ef-bdcfb9654ff2"), f'{row["organization_id"]}:{row["id"]}')
        existing = list(connection.execute(sa.select(contacts).where(
            contacts.c.organization_id == row["organization_id"], contacts.c.customer_id == row["id"])).mappings())
        if any(c["id"] == contact_id or (phone and (c["phone"] or "").strip() == phone)
               or (email and (c["email"] or "").strip().casefold() == email.casefold()) for c in existing):
            continue
        connection.execute(contacts.insert().values(
            id=contact_id, organization_id=row["organization_id"], customer_id=row["id"],
            name="Primary contact" if locales.get(row["organization_id"]) == "en" else "جهة الاتصال الرئيسية",
            phone=phone, email=email, role=None, active=True,
            is_default=not any(c["is_default"] for c in existing), version=1,
            created_by=row["created_by_user_id"], updated_by=row["created_by_user_id"],
            created_at=sa.func.now(), updated_at=sa.func.now()))
        count += 1
    return count


def upgrade():
    connection = op.get_bind()
    for table in ("commercial_customers", "procurement_suppliers", "commercial_customer_sites"):
        op.add_column(table, sa.Column("city_other", sa.String(120), nullable=True))
    op.add_column("commercial_customer_sites", sa.Column("country", sa.String(120), nullable=True))
    op.add_column("shipping_shipments", sa.Column("delivery_country", sa.String(120), nullable=True))
    # Preserve all legacy phone values and customers whose creator is unknown.
    op.alter_column("commercial_customer_contacts", "phone", type_=sa.String(50), existing_type=sa.String(30))
    for column in ("created_by", "updated_by"):
        op.alter_column("commercial_customer_contacts", column, nullable=True)
    from app.masterdata.application.list_service import seed_standard_lists
    with Session(bind=connection) as session:
        for organization_id in connection.execute(sa.text("SELECT id FROM foundation_organizations")).scalars():
            seed_standard_lists(session, organization_id)
        session.flush()
    connection.execute(sa.text("""UPDATE commercial_customer_sites s SET country = COALESCE(
        (SELECT parent_key FROM masterdata_list_items m WHERE m.organization_id=s.organization_id
          AND m.list='city' AND m.key=s.city),
        (SELECT c.country FROM commercial_customers c WHERE c.id=s.customer_id AND c.organization_id=s.organization_id))"""))
    migrate_contacts(connection)
    op.drop_column("commercial_customers", "estimated_consumption")


def downgrade():
    op.add_column("commercial_customers", sa.Column("estimated_consumption", sa.Numeric(14, 2), nullable=True))
    op.drop_column("shipping_shipments", "delivery_country")
    op.drop_column("commercial_customer_sites", "country")
    for table in ("commercial_customer_sites", "procurement_suppliers", "commercial_customers"):
        op.drop_column(table, "city_other")
    # Keep the lossless, backward-compatible phone/creator widening and migrated
    # contacts/catalogs. Never delete organization data during a rollback.
