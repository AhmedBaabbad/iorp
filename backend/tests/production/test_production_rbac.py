from tests.route_inventory import discover_routes
"""PROD-RBAC-001: production permissions are explicit per action, one source, every route guarded."""
import importlib.util
import os
import re
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from app.core.db import Base, engine
from app.foundation.domain.permission_catalog import ALL_TENANT_PERMISSIONS
from app.foundation.domain.system_roles import SYSTEM_ROLE_BY_CODE, SYSTEM_ROLES
from app.main import app
from app.production.domain import permissions as P
from app.production.domain.order_lifecycle import ACTIONS
from app.foundation.infrastructure.models import Organization, Permission, Role, RolePermission
from tests.production.test_downtime_events import DT, env as downtime_env
from tests.production.test_order_results import entry_url, env as result_env
from tests.production.test_waste_records import WASTE, env as waste_env

BACKEND = Path(__file__).parents[2]
REMOVED = {"production:work_centers:write", "production:production_orders:write", "production:results:write",
           "production:downtime_events:write", "production:waste_records:write", "production:shift_definitions:read",
           "production:shift_definitions:write", *(f"production:orders:{a}" for a in ("create", "cancel", "release", "start", "hold", "complete", "close"))}


# ---- one source of truth ---------------------------------------------------------------------

def test_catalog_holds_exactly_the_production_permissions():
    catalog = {p.code for p in ALL_TENANT_PERMISSIONS if p.code.startswith(("production:", "reports:production:"))}
    assert catalog == set(P.ALL) | set(P.REPORTS)
    assert len(P.ALL) == 55 and len(catalog) == 59
    assert not catalog & REMOVED
    assert all(not code.endswith(":write") for code in P.ALL)  # no bundled code survives


def test_every_production_permission_has_arabic_and_english_labels():
    for p in (p for p in ALL_TENANT_PERMISSIONS if p.code in P.ALL):
        assert p.name_en and p.name_ar and p.name_en != p.code and p.description_ar, p.code


def test_no_application_code_spells_a_production_permission():
    # Historical migrations keep the codes they introduced; everything else uses domain/permissions.py.
    pattern = re.compile(r"""["']production:[a-z_]+:[a-z_*]+["']""")
    offenders = [str(path.relative_to(BACKEND)) for path in (BACKEND / "app").rglob("*.py")
                 if path.name not in ("permissions.py", "permission_labels.py") and pattern.search(path.read_text(encoding="utf-8"))]
    assert offenders == []


def test_order_actions_use_the_transition_map():
    assert {name: action.permission for name, action in ACTIONS.items()} == P.ORDER_TRANSITIONS
    assert P.ORDER_TRANSITIONS["resume"] == P.ORDERS_START and P.ORDER_TRANSITIONS["return_to_draft"] == P.ORDERS_RELEASE
    assert set(P.ORDER_TRANSITIONS.values()) <= set(P.ALL)
    for mapping in (P.RUN_TRANSITIONS, P.RESULT_ACTIONS, P.DOWNTIME_ACTIONS, P.WASTE_ACTIONS):
        assert set(mapping.values()) <= set(P.ALL)


def test_production_manager_holds_every_production_permission_explicitly():
    role = SYSTEM_ROLE_BY_CODE["production_manager"]
    # QUAL-NCR-002: production also reads non-conformance reports and completes the corrective actions it owns.
    ncr_owner = {"quality:ncr_reports:read", "quality:ncr_actions:read", "quality:ncr_actions:complete"}
    # MD-001: production defines products and their specification templates, and reads the general settings.
    products = {"masterdata:products:read", "masterdata:products:create", "masterdata:products:update", "masterdata:products:map_legacy", "masterdata:settings:read",
                "masterdata:lists:read"}
    # RBAC-003: the production manager also keeps the workforce (crews) and reads the sales orders it plans from.
    workforce = {"workforce:*", "commercial:orders:read"}
    assert set(role["permissions"]) == set(P.ALL) | set(P.REPORTS) | workforce | ncr_owner | products
    for definition in SYSTEM_ROLES:  # no production wildcard: a new code is granted on purpose
        assert not [p for p in definition["permissions"] if str(p).startswith("production:") and "*" in str(p)], definition["code"]


def test_the_supervisor_records_the_shift_but_does_not_decide():
    # RBAC-003: the production supervisor records; the production manager plans, releases, closes and cancels.
    supervisor = set(SYSTEM_ROLE_BY_CODE["production_supervisor"]["permissions"])
    assert {P.RESULTS_CREATE, P.DOWNTIME_CLOSE, P.WASTE_CREATE, P.code("runs", "start")} <= supervisor
    assert not supervisor & {P.ORDERS_RELEASE, P.ORDERS_CLOSE, P.ORDERS_CANCEL, P.RESULTS_DELETE, P.RESULTS_CORRECT,
                             P.code("runs", "cancel"), P.code("planning", "allocate"), P.DEMANDS_RELEASE}


# ---- every route declares its permission -------------------------------------------------------

def _policies(dependant):
    for dep in dependant.dependencies:
        policy = getattr(dep.call, "permission_policy", None)
        if policy:
            yield policy
        yield from _policies(dep)


def test_every_production_and_report_route_declares_a_permission():
    routes = [r for r in discover_routes(app) if isinstance(r, APIRoute)
              and (r.path.startswith("/api/v1/production") or r.path.startswith("/api/v1/reports"))]
    assert len(routes) > 60
    unguarded = sorted(f"{sorted(r.methods)} {r.path}" for r in routes if not list(_policies(r.dependant)))
    assert unguarded == []
    known = set(P.ALL) | set(P.REPORTS) | {c.code for c in ALL_TENANT_PERMISSIONS}
    for route in routes:
        for kind, codes in _policies(route.dependant):
            assert kind in {"all", "any", "in_handler"}
            assert all(c in known or c.startswith("reports:<") for c in codes), (route.path, codes)


def test_transition_route_names_every_order_action_permission():
    route = next(r for r in discover_routes(app) if isinstance(r, APIRoute) and r.path.endswith("/production-orders/{production_order_id}/transitions"))
    declared = {c for kind, codes in _policies(route.dependant) if kind == "in_handler" for c in codes}
    assert declared == set(P.ORDER_TRANSITIONS.values())


# ---- write split: one permission per action ---------------------------------------------------

def test_downtime_actions_follow_their_own_permissions(downtime_env):
    env = downtime_env
    event = env.added(end=None)
    env.ctx.auth_user.permissions = {P.DOWNTIME_READ, P.DOWNTIME_UPDATE}
    assert env.client.get(f"{DT}/{event['id']}").json()["labels"]["actions"] == ["edit"]
    assert env.client.post(f"{DT}/{event['id']}/close", json={}).status_code == 403
    assert env.client.delete(f"{DT}/{event['id']}").status_code == 403
    assert env.add(start=100, end=110).status_code == 403
    assert env.client.patch(f"{DT}/{event['id']}", json={"notes": "x"}).status_code == 200
    env.ctx.auth_user.permissions = {P.DOWNTIME_READ, P.DOWNTIME_CLOSE}
    assert env.client.get(f"{DT}/{event['id']}").json()["labels"]["actions"] == ["close"]
    assert env.client.post(f"{DT}/{event['id']}/close", json={}).status_code == 200


def test_waste_actions_follow_their_own_permissions(waste_env):
    env = waste_env
    po = env.order()
    record = env.added(po)
    env.ctx.auth_user.permissions = {P.WASTE_READ, P.WASTE_DELETE}
    assert env.client.get(f"{WASTE}/{record['id']}").json()["labels"]["actions"] == ["delete"]
    assert env.client.get(f"{WASTE}/summary", params={"production_order_id": po["id"]}).json()["actions"] == []
    assert env.add(po).status_code == 403
    assert env.client.patch(f"{WASTE}/{record['id']}", json={"quantity_wasted": "1"}).status_code == 403
    assert env.client.delete(f"{WASTE}/{record['id']}").status_code == 204


def test_result_actions_follow_their_own_permissions(result_env):
    env = result_env
    po = env.planned()
    entry = env.added(po, "stock_good", "5")["entries"][0]
    full = set(env.ctx.auth_user.permissions)
    env.ctx.auth_user.permissions = full - {P.RESULTS_CREATE, P.RESULTS_DELETE}
    result = env.result(po)
    assert result["entries"][0]["actions"] == ["edit"] and "create" not in result["actions"]
    assert env.client.patch(entry_url(po, entry["id"]), json={"quantity": "4"}).status_code == 200
    assert env.client.delete(entry_url(po, entry["id"])).status_code == 403
    env.ctx.auth_user.permissions = full - {P.RESULTS_UPDATE}
    assert env.result(po)["entries"][0]["actions"] == ["delete"]


def test_dashboard_shows_production_only_with_order_read(result_env):
    env = result_env
    env.planned()
    env.ctx.auth_user.permissions = set()
    body = env.client.get("/api/v1/dashboard/summary").json()
    assert body["production_orders_count"] is None and body["production_by_status"] is None
    assert body["quality_checks_count"] is None
    env.ctx.auth_user.permissions = {P.ORDERS_READ}
    assert env.client.get("/api/v1/dashboard/summary").json()["production_orders_count"] == 1


# ---- migrations f6a1b2h9 / f6a1b2i0 on real PostgreSQL ----------------------------------------

VERSIONS = BACKEND / "alembic/versions"


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, VERSIONS / filename)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


postgres = pytest.mark.skipif(os.environ.get("RUN_POSTGRES_TESTS") != "1", reason="Opt-in isolated PostgreSQL tests")


@pytest.fixture
def old_grants():
    """An organization as it was before PROD-RBAC-001: bundled codes held by a system and a custom role."""
    h9 = _load("rbac_split", "2026_10_09_0900_f6a1b2h9_production_rbac_split.py")
    i0 = _load("rbac_grants", "2026_10_10_0900_f6a1b2i0_production_system_role_grants.py")
    schema = "test_rbac_" + uuid4().hex
    with engine.begin() as c:
        c.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated = sa.create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(isolated)
        with Session(isolated) as db:
            org = Organization(name="RBAC", code="rbac", timezone="UTC")
            db.add(org); db.flush()
            roles = {code: Role(organization_id=org.id, code=code, name=code, is_system=system)
                     for code, system in (("production_manager", True), ("viewer", True), ("line_lead", False))}
            db.add_all(roles.values()); db.flush()
            perms = {}
            for code in [*REMOVED, P.WORK_CENTERS_READ, P.RUNS_READ, P.ROSTERS_READ]:
                _, resource, action = code.split(":")
                perms[code] = Permission(organization_id=org.id, code=code, name=code, description=code, module_name="production",
                                         resource_name=resource, action_name=action)
            db.add_all(perms.values()); db.flush()
            grants = [("production_manager", c, "organization") for c in REMOVED] + [
                ("viewer", "production:shift_definitions:read", "organization"),
                ("line_lead", "production:downtime_events:write", "own"), ("line_lead", "production:orders:start", "organization"),
                ("line_lead", P.WORK_CENTERS_READ, "organization")]
            db.add_all(RolePermission(role_id=roles[r].id, permission_id=perms[c].id, scope=s) for r, c, s in grants)
            db.commit()
            ids = dict(org=org.id, **{f"role_{k}": v.id for k, v in roles.items()})
        yield isolated, ids, h9, i0
    finally:
        isolated.dispose()
        with engine.begin() as c:
            c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))


def _held(c, role_id):
    return dict(c.execute(sa.text("SELECT p.code, rp.scope FROM foundation_role_permissions rp JOIN foundation_permissions p ON p.id=rp.permission_id "
                                  "WHERE rp.role_id=:r"), dict(r=role_id)).all())


def _snapshot(c):
    return sorted(c.execute(sa.text("SELECT r.code, p.code, rp.scope FROM foundation_role_permissions rp JOIN foundation_permissions p ON p.id=rp.permission_id "
                                    "JOIN foundation_roles r ON r.id=rp.role_id")).all())


@postgres
def test_split_keeps_every_role_s_access_and_scope(old_grants):
    isolated, ids, h9, _ = old_grants
    with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
        h9.upgrade()
        manager = _held(c, ids["role_production_manager"])
        assert not set(manager) & REMOVED
        assert {P.WORK_CENTERS_CREATE, P.WORK_CENTERS_UPDATE, P.WORK_CENTERS_DELETE, P.ORDERS_UPDATE, P.ORDERS_MANAGE_ITEMS,
                P.RESULTS_CREATE, P.RESULTS_UPDATE, P.RESULTS_DELETE, P.DOWNTIME_CLOSE, P.WASTE_DELETE, P.ORDERS_CANCEL} <= set(manager)
        # The custom role keeps its narrower scope on every replacement, and nothing more.
        assert _held(c, ids["role_line_lead"]) == {P.DOWNTIME_CREATE: "own", P.DOWNTIME_UPDATE: "own", P.DOWNTIME_DELETE: "own",
                                                   P.DOWNTIME_CLOSE: "own", P.ORDERS_START: "organization", P.WORK_CENTERS_READ: "organization"}
        assert _held(c, ids["role_viewer"]) == {}  # shift_definitions guarded no route
        codes = set(c.scalars(sa.text("SELECT code FROM foundation_permissions")))
        assert not codes & REMOVED


@postgres
def test_split_is_reversible_exactly(old_grants):
    isolated, _, h9, i0 = old_grants
    with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
        before = _snapshot(c)
        rows_before = sorted(c.scalars(sa.text("SELECT code FROM foundation_permissions")))
        h9.upgrade(); i0.upgrade()
        assert _snapshot(c) != before
        i0.downgrade(); h9.downgrade()
        assert _snapshot(c) == before
        assert sorted(c.scalars(sa.text("SELECT code FROM foundation_permissions"))) == rows_before
        assert {"production_rbac_h9_backup", "production_rbac_i0_added_grants"}.isdisjoint(sa.inspect(c).get_table_names())


@postgres
def test_split_leaves_an_already_migrated_organization_alone(old_grants):
    isolated, ids, h9, _ = old_grants
    with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
        h9.upgrade()
        after = _snapshot(c)
        # Running the split again over migrated data (only new codes left) changes nothing.
        c.execute(sa.text("DROP TABLE production_rbac_h9_backup"))
        h9.upgrade()
        assert _snapshot(c) == after


@postgres
def test_system_roles_receive_runs_and_rosters_custom_roles_do_not(old_grants):
    isolated, ids, h9, i0 = old_grants
    with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
        h9.upgrade(); i0.upgrade()
        assert _held(c, ids["role_viewer"]) == {P.RUNS_READ: "organization", P.ROSTERS_READ: "organization"}
        assert P.RUNS_READ in _held(c, ids["role_production_manager"])
        assert P.RUNS_READ not in _held(c, ids["role_line_lead"])
