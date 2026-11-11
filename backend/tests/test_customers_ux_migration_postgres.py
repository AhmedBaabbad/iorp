"""Replay customer migration in a disposable schema; never touch public tables."""
import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.core.db import Base, engine
from app.main import app  # noqa: F401 — register all model tables

pytestmark = pytest.mark.skipif(os.environ.get("RUN_POSTGRES_TESTS") != "1", reason="Isolated PostgreSQL opt-in")


def test_existing_organizations_contacts_upgrade_downgrade_and_rerun():
    path = Path(__file__).parents[1] / "alembic/versions/2026_11_17_0900_f6a1b2p0_customers_ux.py"
    spec = importlib.util.spec_from_file_location("customers_ux_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    schema = "test_customers_ux_" + uuid4().hex
    with engine.begin() as c:
        c.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated = sa.create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(isolated)
        with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
            migration.downgrade()
            org, ar_org, user = uuid4(), uuid4(), uuid4()
            organizations = Base.metadata.tables["foundation_organizations"]
            for identifier, language in ((org, "en"), (ar_org, "ar")):
                c.execute(organizations.insert().values(id=identifier, name="Synthetic", code=str(identifier),
                    status="active", timezone="UTC", default_locale=language))
            c.execute(Base.metadata.tables["foundation_users"].insert().values(id=user, organization_id=org,
                email="synthetic@example.test", full_name="Creator", password_hash="unused", status="active", is_organization_root=False))
            customers = sa.Table("commercial_customers", sa.MetaData(), autoload_with=c)
            contacts = Base.metadata.tables["commercial_customer_contacts"]
            ids = [uuid4() for _ in range(6)]
            for i, customer in enumerate(ids):
                c.execute(customers.insert().values(id=customer, organization_id=ar_org if i == 5 else org,
                    customer_code=f"C{i}", name="Synthetic", phone="9" * 50 if i == 4 else f"555{i}",
                    email=f"legacy{i}@example.test", status="active", relationship_stage="lead", priority_level="medium",
                    created_by_user_id=None if i in (4, 5) else user, country="sa", estimated_consumption=99,
                    created_at=sa.func.now(), updated_at=sa.func.now()))
            # Phone match and case-insensitive email match must each prevent duplication.
            for i in (0, 1, 2):
                c.execute(contacts.insert().values(id=uuid4(), organization_id=org, customer_id=ids[i], name="Existing",
                    phone="5550" if i == 0 else None, email="LEGACY1@EXAMPLE.TEST" if i == 1 else None,
                    active=True, is_default=i == 2, version=1, created_by=user, updated_by=user))
            lists = Base.metadata.tables["masterdata_list_items"]
            custom = uuid4()
            c.execute(lists.insert().values(id=custom, organization_id=org, list="country", key="sa",
                name_ar="مخصص", name_en="Customized", active=False, sort_order=999))
            migration.upgrade()
            assert "estimated_consumption" not in {x["name"] for x in sa.inspect(c).get_columns("commercial_customers")}
            # Six customers: two matching records, four newly migrated contacts.
            assert c.scalar(sa.select(sa.func.count()).select_from(contacts)) == 7
            assert migration.migrate_contacts(c) == 0
            new = c.execute(sa.select(contacts).where(contacts.c.customer_id == ids[2], contacts.c.name != "Existing")).mappings().one()
            assert new["name"] == "Primary contact" and not new["is_default"] and new["created_by"] == user
            arabic = c.execute(sa.select(contacts).where(contacts.c.customer_id == ids[5])).mappings().one()
            assert arabic["name"] == "جهة الاتصال الرئيسية" and arabic["created_by"] is None and arabic["is_default"]
            assert c.scalar(sa.select(contacts.c.phone).where(contacts.c.customer_id == ids[4])) == "9" * 50
            item = c.execute(sa.select(lists).where(lists.c.id == custom)).mappings().one()
            assert item["name_en"] == "Customized" and not item["active"] and item["sort_order"] == 999
            for organization in (org, ar_org):
                for kind, count in (("country", 249), ("city", 357)):
                    assert c.scalar(sa.select(sa.func.count()).select_from(lists).where(lists.c.organization_id == organization, lists.c.list == kind)) == count
            # An operator may edit a migrated contact; re-upgrade must not recreate it.
            c.execute(contacts.update().where(contacts.c.customer_id == ids[3]).values(phone="edited", email=None))
            migration.downgrade()
            assert c.scalar(sa.text("SELECT count(*) FROM commercial_customers WHERE estimated_consumption IS NOT NULL")) == 0
            assert c.scalar(sa.text("SELECT phone FROM commercial_customers WHERE id=:id"), {"id": ids[3]}) == "5553"
            migration.upgrade()
            assert c.scalar(sa.select(sa.func.count()).select_from(contacts)) == 7
            assert migration.migrate_contacts(c) == 0
    finally:
        isolated.dispose()
        with engine.begin() as c:
            c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
