"""PROD-OUTPUT-001 migrations on real PostgreSQL, in a disposable schema, never app tables.

f6a1b2h3 adds the final result; f6a1b2h4 relaxes the legacy shift; f6a1b2h5 removes the legacy
outputs. The fixture starts from today's metadata and walks h5 and h3 back to reach the
state before the final result existed.
"""
import importlib.util
import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.orm import Session

from app.core.db import Base, engine
from app.foundation.infrastructure.models import Organization, Permission, Role, RolePermission, User
from app.production.infrastructure.models import ProductionOrder, WorkCenter

pytestmark = pytest.mark.skipif(os.environ.get("RUN_POSTGRES_TESTS") != "1", reason="Opt-in isolated PostgreSQL tests")
VERSIONS = Path(__file__).parents[1] / "alembic/versions"


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, VERSIONS / filename)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


h2 = _load("output_confirmation", "2026_10_02_0900_f6a1b2h2_production_output_confirmation.py")
h3 = _load("result_entries", "2026_10_03_0900_f6a1b2h3_production_result_entries.py")
h4 = _load("output_shift_optional", "2026_10_04_0900_f6a1b2h4_legacy_output_shift_optional.py")
h5 = _load("remove_legacy_outputs", "2026_10_05_0900_f6a1b2h5_remove_legacy_production_outputs.py")


@pytest.fixture
def before_results():
    schema = "test_result_" + uuid4().hex
    with engine.begin() as c:
        c.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated = sa.create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(isolated)
        with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
            h5.downgrade()  # legacy outputs back (empty)
            h3.downgrade()  # and no final result yet
        with Session(isolated) as db:
            org = Organization(name="Migration", code="migration", timezone="UTC")
            db.add(org); db.flush()
            user = User(organization_id=org.id, full_name="Planner", email=f"{uuid4().hex}@example.invalid", password_hash="unused")
            center = WorkCenter(organization_id=org.id, code="WC", name="Line")
            db.add_all([user, center]); db.flush()
            order = ProductionOrder(organization_id=org.id, production_order_number="PO-1", work_center_id=center.id, product_type="film",
                                    planned_quantity=100, unit="kg", status="completed", planned_start_date=date.today(), planned_end_date=date.today(),
                                    created_by_user_id=user.id)
            db.add(order); db.flush()
            # A role holding the legacy permissions the new ones are granted from; one grant owner-scoped.
            role = Role(organization_id=org.id, name="Supervisor", code="supervisor")
            db.add(role); db.flush()
            for code, scope in (("production:production_outputs:read", "organization"), ("production:production_outputs:write", "own"),
                                ("production:orders:close", "organization")):
                permission = db.scalar(sa.select(Permission).where(Permission.organization_id == org.id, Permission.code == code))
                if permission is None:
                    _, resource, action = code.split(":")
                    permission = Permission(organization_id=org.id, code=code, name=code, description=code, module_name="production",
                                            resource_name=resource, action_name=action)
                    db.add(permission); db.flush()
                db.add(RolePermission(role_id=role.id, permission_id=permission.id, scope=scope))
            db.commit()
            ids = dict(org=org.id, user=user.id, order=order.id, center=center.id, role=role.id)
        yield isolated, ids
    finally:
        isolated.dispose()
        with engine.begin() as c:
            c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))


def _legacy_row(c, ids):
    output_id = uuid4()
    c.execute(sa.text("INSERT INTO production_outputs (id, organization_id, production_order_id, work_center_id, output_date, quantity_produced, unit, output_status, created_by_user_id, created_at, updated_at) "
                      "VALUES (:id, :org, :o, :wc, '2026-08-01', 99.5, 'kg', 'recorded', :u, now(), now())"),
              dict(id=output_id, org=ids["org"], o=ids["order"], wc=ids["center"], u=ids["user"]))
    return output_id


def _grants(c, role, resource):
    return dict(c.execute(sa.text("SELECT p.code, rp.scope FROM foundation_role_permissions rp JOIN foundation_permissions p ON p.id = rp.permission_id "
                                  "WHERE rp.role_id = :r AND p.resource_name = :res"), dict(r=role, res=resource)).all())


def _result_row(c, ids, loss=True):
    c.execute(sa.text("INSERT INTO production_result_entries (id, organization_id, production_order_id, disposition, quantity, unit, counts_as_loss, entry_type, created_by_user_id, created_at, updated_at) "
                      "VALUES (:id, :org, :o, 'scrap', 1, 'kg', :loss, 'original', :u, now(), now())"), dict(id=uuid4(), org=ids["org"], o=ids["order"], u=ids["user"], loss=loss))


def test_17_result_migration_upgrade_and_downgrade_round_trip(before_results):
    isolated, ids = before_results
    with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
        h3.upgrade()
        columns = {x["name"] for x in sa.inspect(c).get_columns("production_result_entries")}
        assert {"disposition", "counts_as_loss", "entry_type", "corrects_entry_id"} <= columns
        assert not {x for x in columns if "shift" in x or "work_center" in x or "run" in x or "status" in x}
        assert "ix_result_org_order" in {i["name"] for i in sa.inspect(c).get_indexes("production_result_entries")}
        assert _grants(c, ids["role"], "results") == {"production:results:read": "organization", "production:results:write": "own",
                                                      "production:results:correct": "organization"}
        with pytest.raises(sa.exc.IntegrityError):  # the loss rule holds at database level too
            with c.begin_nested():
                _result_row(c, ids, loss=False)
        h3.downgrade()
        assert "production_result_entries" not in sa.inspect(c).get_table_names()
        assert _grants(c, ids["role"], "results") == {}
        h3.upgrade()  # and forward again
        assert "production_result_entries" in sa.inspect(c).get_table_names()


def test_result_downgrade_refuses_to_erase_entries(before_results):
    isolated, ids = before_results
    with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
        h3.upgrade()
        _result_row(c, ids)
        with pytest.raises(RuntimeError, match="export"):
            h3.downgrade()
        assert c.scalar(sa.text("SELECT count(*) FROM production_result_entries")) == 1


def test_16_legacy_rows_survive_h2_to_h4_and_h5_refuses_to_drop_them(before_results):
    """Environments with pre-confirmation outputs (no shift) upgrade intact; removal never erases them silently."""
    isolated, ids = before_results
    with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
        h2.downgrade()  # the shape before f6a1b2h2: no shift, verification or correction columns
        legacy_id = _legacy_row(c, ids)
        h2.upgrade(); h3.upgrade(); h4.upgrade()
        row = c.execute(sa.text("SELECT quantity_produced, output_status, shift_definition_id FROM production_outputs WHERE id = :i"), dict(i=legacy_id)).one()
        assert (row[0], row[1], row[2]) == (Decimal("99.500"), "recorded", None)
        with pytest.raises(RuntimeError, match="1 production outputs"):
            h5.upgrade()
        assert c.scalar(sa.text("SELECT count(*) FROM production_outputs")) == 1


def test_h5_removes_the_legacy_outputs_and_quality_references(before_results):
    isolated, ids = before_results
    with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
        h3.upgrade(); h4.upgrade()
        h5.upgrade()
        tables = set(sa.inspect(c).get_table_names())
        assert "production_outputs" not in tables and "production_result_entries" in tables
        for table in ("quality_checks", "quality_defects", "quality_rejections"):
            assert "production_output_id" not in {x["name"] for x in sa.inspect(c).get_columns(table)}
        assert c.scalar(sa.text("SELECT count(*) FROM foundation_permissions WHERE code LIKE 'production:production_outputs:%'")) == 0
        assert _grants(c, ids["role"], "results")["production:results:read"] == "organization"  # the new grants stay
        h5.downgrade()
        assert "production_outputs" in set(sa.inspect(c).get_table_names())
        assert "production_output_id" in {x["name"] for x in sa.inspect(c).get_columns("quality_rejections")}
