"""Real PostgreSQL migration round-trip in a disposable schema, never app tables."""
import importlib.util
import os
from datetime import date, time
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.orm import Session

from app.core.db import Base, engine
from app.foundation.infrastructure.models import Organization, Permission, Role, RolePermission, User
from app.production.infrastructure.models import ProductionOrder, ShiftDefinition, WorkCenter
from app.workforce.infrastructure.models import WorkforceMember

pytestmark = pytest.mark.skipif(os.environ.get("RUN_POSTGRES_TESTS") != "1", reason="Opt-in isolated PostgreSQL tests")


@pytest.fixture
def legacy_database():
    schema = "test_execution_" + uuid4().hex
    with engine.begin() as c:
        c.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated = sa.create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(isolated)
        with Session(isolated) as db:
            org = Organization(name="Migration", code="migration", timezone="UTC")
            db.add(org); db.flush()
            center = WorkCenter(organization_id=org.id, code="WC", name="Line")
            shift = ShiftDefinition(organization_id=org.id, code="S", name="Morning", start_time=time(7), end_time=time(15), duration_hours=8, crosses_midnight=False)
            db.add_all([center, shift]); db.flush()
            # A pre-existing role holding the legacy shift grants, one of them owner-scoped.
            role = Role(organization_id=org.id, name="Supervisor", code="supervisor")
            db.add(role); db.flush()
            for action, scope in (("read", "organization"), ("write", "own")):
                permission = Permission(organization_id=org.id, code=f"production:shift_definitions:{action}", name=action, description=action, module_name="production", resource_name="shift_definitions", action_name=action)
                db.add(permission); db.flush()
                db.add(RolePermission(role_id=role.id, permission_id=permission.id, scope=scope))
            db.commit()
            org_id, center_id, shift_id = org.id, center.id, shift.id
        with isolated.begin() as c:
            # Waste (f6a1b2h6) and downtime (f6a1b2h7) point at runs; both are after this migration's history.
            for table in ("production_waste_records", "production_downtime_events"):
                c.execute(sa.text(f"ALTER TABLE {table} DROP COLUMN production_run_id"))
            for table in ("production_run_members", "production_runs", "production_shift_roster_members", "production_shift_rosters"):
                c.execute(sa.text(f"DROP TABLE {table}"))
            c.execute(sa.text("ALTER TABLE production_shift_definitions ADD COLUMN work_center_id uuid REFERENCES production_work_centers(id)"))
            c.execute(sa.text("UPDATE production_shift_definitions SET work_center_id=:id"), {"id": center_id})
            c.execute(sa.text("ALTER TABLE production_shift_definitions ALTER COLUMN work_center_id SET NOT NULL"))
            c.execute(sa.text("CREATE INDEX ix_production_shift_definitions_work_center_id ON production_shift_definitions(work_center_id)"))
        spec = importlib.util.spec_from_file_location("execution_migration", Path(__file__).parents[1] / "alembic/versions/2026_09_26_0900_f6a1b2g6_execution_foundation.py")
        migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
        yield isolated, migration, org_id, center_id, shift_id
    finally:
        isolated.dispose()
        with engine.begin() as c:
            c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))


def test_upgrade_archives_exact_link_and_roundtrip(legacy_database):
    isolated, migration, org_id, center_id, shift_id = legacy_database
    with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
        migration.upgrade()
        assert c.execute(sa.text("SELECT organization_id, work_center_id, shift_definition_id FROM production_legacy_shift_centers")).one() == (org_id, center_id, shift_id)
        assert "work_center_id" not in {x["name"] for x in sa.inspect(c).get_columns("production_shift_definitions")}
        assert c.scalar(sa.text("SELECT count(*) FROM production_shift_roster_members")) == 0
        assert c.scalar(sa.text("SELECT count(*) FROM foundation_permissions WHERE module_name='production' AND resource_name <> 'shift_definitions'")) == 13
        migration.downgrade()
        assert c.scalar(sa.text("SELECT work_center_id FROM production_shift_definitions WHERE id=:id"), {"id": shift_id}) == center_id


def test_downgrade_refuses_to_erase_roster_history(legacy_database):
    isolated, migration, org_id, _, shift_id = legacy_database
    with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
        migration.upgrade()
        c.execute(sa.text("INSERT INTO production_shift_rosters (id, organization_id, shift_definition_id, effective_from, status) VALUES (:id,:org,:shift,:day,'active')"), dict(id=uuid4(), org=org_id, shift=shift_id, day=date(2026, 1, 1)))
        with pytest.raises(RuntimeError, match="history"):
            migration.downgrade()
        assert c.scalar(sa.text("SELECT count(*) FROM production_shift_rosters")) == 1


def test_downgrade_refuses_unmapped_independent_shift(legacy_database):
    isolated, migration, org_id, _, _ = legacy_database
    with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
        migration.upgrade()
        c.execute(sa.text("INSERT INTO production_shift_definitions (id,organization_id,code,name,shift_type,start_time,end_time,duration_hours,crosses_midnight,status,created_at,updated_at) VALUES (:id,:org,'NEW','New','custom','07:00','15:00',8,false,'active',now(),now())"), dict(id=uuid4(), org=org_id))
        with pytest.raises(RuntimeError, match="mapping"):
            migration.downgrade()


def granted(c, org_id):
    return dict(c.execute(sa.text("SELECT p.code, rp.scope FROM foundation_role_permissions rp JOIN foundation_permissions p ON p.id=rp.permission_id WHERE p.organization_id=:org"), {"org": org_id}).all())


def load_hardening():
    spec = importlib.util.spec_from_file_location("execution_hardening", Path(__file__).parents[1] / "alembic/versions/2026_09_27_0900_f6a1b2g7_execution_hardening.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_legacy_grants_map_to_new_codes(legacy_database):
    isolated, migration, org_id, _, _ = legacy_database
    hardening = load_hardening()
    with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
        migration.upgrade()
        grants = granted(c, org_id)
        # read -> read; write -> create + update; scope is carried over unchanged.
        assert grants["production:shifts:read"] == "organization"
        assert grants["production:shifts:create"] == grants["production:shifts:update"] == "own"
        assert not any(code.startswith(("production:runs:", "production:shift_rosters:")) for code in grants)
        role_id = c.scalar(sa.text("SELECT id FROM foundation_roles WHERE code='supervisor'"))
        runs_update = c.scalar(sa.text("SELECT id FROM foundation_permissions WHERE organization_id=:org AND code='production:runs:update'"), {"org": org_id})
        c.execute(sa.text("INSERT INTO foundation_role_permissions (id, role_id, permission_id, scope) VALUES (:id, :role, :permission, 'organization')"), dict(id=uuid4(), role=role_id, permission=runs_update))
        hardening.upgrade()
        grants = granted(c, org_id)
        assert grants["production:shifts:delete"] == "own"
        assert grants["production:runs:pause"] == grants["production:runs:cancel"] == "organization"


def test_repeated_participation_index_and_guarded_downgrade(legacy_database):
    isolated, migration, org_id, center_id, _ = legacy_database
    hardening = load_hardening()
    with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
        migration.upgrade()
        hardening.upgrade()
        with Session(bind=c) as db:
            user = User(organization_id=org_id, email="u@example.com", full_name="U", password_hash="x")
            worker = WorkforceMember(organization_id=org_id, employee_code="W1", full_name="W", worker_type="operator", employment_type="employee")
            db.add_all([user, worker]); db.flush()
            order = ProductionOrder(organization_id=org_id, production_order_number="PO", work_center_id=center_id, product_type="film", planned_quantity=1, unit="kg", planned_start_date=date(2026, 1, 1), planned_end_date=date(2026, 1, 1), created_by_user_id=user.id)
            db.add(order); db.flush()
            user_id, worker_id, order_id, run_id = user.id, worker.id, order.id, uuid4()
        c.execute(sa.text("INSERT INTO production_runs (id, organization_id, production_order_id, work_center_id, run_date, status, created_by_user_id) VALUES (:id, :org, :order, :wc, :day, 'in_progress', :user)"), dict(id=run_id, org=org_id, order=order_id, wc=center_id, day=date(2026, 1, 1), user=user_id))
        member = sa.text("INSERT INTO production_run_members (id, organization_id, production_run_id, workforce_member_id, role_code, is_lead, started_at, ended_at) VALUES (:id, :org, :run, :worker, 'operator', false, :start, :end)")
        c.execute(member, dict(id=uuid4(), org=org_id, run=run_id, worker=worker_id, start="2026-01-01T08:00Z", end="2026-01-01T10:00Z"))
        c.execute(member, dict(id=uuid4(), org=org_id, run=run_id, worker=worker_id, start="2026-01-01T11:00Z", end=None))
        with pytest.raises(sa.exc.IntegrityError), c.begin_nested():
            c.execute(member, dict(id=uuid4(), org=org_id, run=run_id, worker=worker_id, start="2026-01-01T12:00Z", end=None))
        with pytest.raises(RuntimeError, match="repeated run participation"):
            hardening.downgrade()
