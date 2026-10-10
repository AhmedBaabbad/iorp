"""PROD-DOWNTIME-001: machine downtime — belongs to a work center; order and run are optional context."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.commercial.infrastructure.models import Customer
from app.core.tenancy import TenantContext
from app.dependencies import get_current_user
from app.main import app
from app.production.infrastructure.execution_models import ProductionRun
from app.production.infrastructure.models import DowntimeEvent, WorkCenter
from tests.test_production_allocation_lifecycle import other_org_demand

ROOT = "/api/v1/production"
DT = f"{ROOT}/downtime-events"
PERMISSIONS = frozenset(
    ["production:production_orders:read", "production:production_orders:update", "production:production_orders:manage_items", "production:planning:read", "production:planning:allocate",
     "production:production_orders:create", "production:downtime_events:read", "production:downtime_events:create", "production:downtime_events:update", "production:downtime_events:delete", "production:downtime_events:close"]
    + [f"production:production_orders:{a}" for a in ("release", "start", "hold", "complete", "close", "cancel")]
    + [f"production:demands:{a}" for a in ("read", "create", "update", "release", "cancel")])
PLANNED = {"planned_maintenance", "break_meeting", "no_orders"}
UNPLANNED = {"changeover_setup", "breakdown", "material_shortage", "waiting_labor", "quality_issue", "utilities", "other"}
T0 = datetime(2026, 9, 29, 8, 0, tzinfo=timezone.utc)


def at(minutes):
    return (T0 + timedelta(minutes=minutes)).isoformat()


@pytest.fixture
def env(client, db, test_org, test_user):
    customer = Customer(organization_id=test_org.id, customer_code="C-DT", name="Downtime Customer")
    center = WorkCenter(organization_id=test_org.id, code="WC-DT", name="Extruder 1")
    other_center = WorkCenter(organization_id=test_org.id, code="WC-DT2", name="Extruder 2")
    db.add_all([customer, center, other_center]); db.commit()
    ctx = SimpleNamespace(user=SimpleNamespace(is_organization_root=False), auth_user=SimpleNamespace(permissions=set(PERMISSIONS)),
                          tenant=TenantContext(test_user.id, test_org.id, permissions=PERMISSIONS))
    app.dependency_overrides[get_current_user] = lambda: ctx

    def transition(order_id, action, reason="because", **extra):
        return client.post(f"{ROOT}/production-orders/{order_id}/transitions", json={"action": action, "reason": reason, **extra})

    def order(to="in_progress"):
        items = [dict(product_type="film", unit="kg", required_quantity="1000", target_spec_json={"width_mm": 10})]
        demand_id = client.post(f"{ROOT}/demands", json={"customer_id": str(customer.id), "items": items}).json()["id"]
        client.post(f"{ROOT}/demands/{demand_id}/status", json={"status": "ready_for_planning"})
        demand = client.get(f"{ROOT}/demands/{demand_id}").json()
        r = client.post(f"{ROOT}/planning/create-production-order", json=dict(
            allocations=[{"production_demand_item_id": i["id"], "allocated_quantity": "400"} for i in demand["items"]],
            work_center_id=str(center.id), planned_start_date="2026-10-01", planned_end_date="2026-10-03"))
        assert r.status_code == 201, r.text
        po = r.json()
        path = {"draft": [], "released": ["release"], "in_progress": ["release", "start"], "on_hold": ["release", "start", "hold"],
                "completed": ["release", "start", "complete"], "closed": ["release", "start", "complete", "close"], "cancelled": ["cancel"]}[to]
        for action in path:
            assert transition(po["id"], action, **({"zero_output": True} if action == "close" else {})).status_code == 200
        return po

    def run(po, status="in_progress", work_center=None):
        row = ProductionRun(organization_id=test_org.id, production_order_id=UUID(po["id"]), work_center_id=(work_center or other_center).id,
                            run_date=date(2026, 9, 29), status=status, created_by_user_id=test_user.id)
        db.add(row); db.commit()
        return row

    def add(category="breakdown", start=0, end=30, center_=None, **extra):
        body = {"work_center_id": str((center_ or center).id), "start_time": at(start), "category": category, **extra}
        if end is not None:
            body["end_time"] = at(end)
        return client.post(DT, json={k: v for k, v in body.items() if v is not None})

    def added(*args, **kwargs):
        r = add(*args, **kwargs)
        assert r.status_code == 201, r.text
        return r.json()

    def rows():
        db.expire_all()
        return list(db.scalars(select(DowntimeEvent).order_by(DowntimeEvent.start_time)))

    return SimpleNamespace(db=db, client=client, org=test_org, user=test_user, ctx=ctx, center=center, other_center=other_center,
                           order=order, run=run, add=add, added=added, rows=rows, transition=transition)


def code(r):
    return r.json()["detail"]["code"]


# ---- open, close and derived fields -------------------------------------------------------------

def test_open_stop_then_close_derives_status_duration_and_closer(env):
    event = env.added("breakdown", start=0, end=None, reason_code="HYD-PUMP")
    assert (event["status"], event["duration_minutes"], event["planned"]) == ("open", None, False)
    assert event["labels"]["actions"] == ["close", "edit", "delete"] and Decimal(event["labels"]["elapsed_minutes"]) > 0
    r = env.client.post(f"{DT}/{event['id']}/close", json={"end_time": at(42.5)})
    assert r.status_code == 200, r.text
    (row,) = env.rows()
    assert (row.status.value, row.duration_minutes, row.closed_by_user_id) == ("closed", Decimal("42.50"), env.user.id)
    assert code(env.client.post(f"{DT}/{event['id']}/close", json={})) == "DOWNTIME_ALREADY_CLOSED"


def test_close_defaults_to_now(env):
    start = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    event = env.client.post(DT, json={"work_center_id": str(env.center.id), "start_time": start, "category": "utilities"}).json()
    closed = env.client.post(f"{DT}/{event['id']}/close", json={}).json()
    assert closed["status"] == "closed" and Decimal("9.9") < Decimal(str(closed["duration_minutes"])) < Decimal("11")


def test_derived_fields_are_never_accepted(env):
    for extra in ({"status": "closed"}, {"duration_minutes": 5}, {"planned": True}, {"organization_id": str(uuid4())}):
        assert env.add(**extra).status_code == 422
    assert env.rows() == []


@pytest.mark.parametrize("category", sorted(PLANNED | UNPLANNED))
def test_planned_is_derived_from_the_category(env, category):
    event = env.added(category)
    assert event["planned"] is (category in PLANNED)


def test_old_categories_are_rejected(env):
    for old in ("machine", "manpower", "setup", "material"):
        assert env.add(old).status_code == 422


# ---- one machine, one stop at a time -------------------------------------------------------------

def test_periods_on_one_machine_never_overlap(env):
    env.added(start=0, end=30)
    r = env.add(start=20, end=50)
    assert r.status_code == 409 and code(r) == "DOWNTIME_OVERLAP"
    env.added(start=30, end=40)                       # touching the end is fine
    env.added(start=20, end=50, center_=env.other_center)  # another machine is fine
    env.added(start=60, end=None)                     # an open stop
    r = env.add(start=90, end=100)
    assert code(r) == "DOWNTIME_OVERLAP" and r.json()["detail"]["conflicting_status"] == "open"
    assert code(env.add(start=70, end=None)) == "DOWNTIME_OVERLAP"  # only one open stop per machine
    env.added(start=50, end=60)                       # before the open stop
    assert len(env.rows()) == 5


def test_period_rules(env):
    assert code(env.add(start=30, end=30)) == "END_BEFORE_START"
    assert code(env.add(start=30, end=10)) == "END_BEFORE_START"
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    r = env.client.post(DT, json={"work_center_id": str(env.center.id), "start_time": future, "category": "other"})
    assert code(r) == "START_IN_FUTURE"
    # Times need a timezone, so a device's local clock is never misread.
    r = env.client.post(DT, json={"work_center_id": str(env.center.id), "start_time": "2026-09-29T08:00:00", "category": "other"})
    assert r.status_code == 422


def test_editing_rechecks_overlap_and_planned(env):
    first = env.added(start=0, end=30)
    env.added(start=40, end=50)
    assert code(env.client.patch(f"{DT}/{first['id']}", json={"end_time": at(45)})) == "DOWNTIME_OVERLAP"
    r = env.client.patch(f"{DT}/{first['id']}", json={"end_time": at(35), "category": "planned_maintenance"})
    assert r.status_code == 200, r.text
    row = env.rows()[0]
    assert (row.duration_minutes, row.category, row.planned, row.updated_by_user_id) == (Decimal("35.00"), "planned_maintenance", True, env.user.id)
    # Reopening clears the end and the duration.
    reopened = env.client.patch(f"{DT}/{first['id']}", json={"end_time": None})
    assert code(reopened) == "DOWNTIME_OVERLAP"  # it would run into the next stop


# ---- order and run -----------------------------------------------------------------------------

@pytest.mark.parametrize("status,expected", [("draft", "ORDER_NOT_RUNNING"), ("released", "ORDER_NOT_RUNNING"), ("cancelled", "ORDER_NOT_RUNNING"),
                                             ("closed", "DOWNTIME_LOCKED")])
def test_order_link_only_while_it_runs(env, status, expected):
    po = env.order(to=status)
    r = env.add(production_order_id=po["id"])
    assert code(r) == expected and env.rows() == []


@pytest.mark.parametrize("status", ["in_progress", "on_hold", "completed"])
def test_order_link_while_running_or_completed(env, status):
    po = env.order(to=status)
    event = env.added(production_order_id=po["id"])
    assert event["labels"]["order_number"] == po["production_order_number"]


def test_closing_the_order_locks_its_downtime(env):
    po = env.order(to="completed")
    event = env.added(production_order_id=po["id"], end=None)
    assert env.transition(po["id"], "close", zero_output=True).status_code == 200
    for r in (env.client.patch(f"{DT}/{event['id']}", json={"reason_code": "x"}), env.client.delete(f"{DT}/{event['id']}"),
              env.client.post(f"{DT}/{event['id']}/close", json={})):
        assert r.status_code == 409 and code(r) == "DOWNTIME_LOCKED"
    assert env.client.get(f"{DT}/{event['id']}").json()["labels"]["actions"] == []


def test_run_gives_machine_and_order(env):
    po = env.order()
    run = env.run(po)
    r = env.client.post(DT, json={"production_run_id": str(run.id), "start_time": at(0), "end_time": at(5), "category": "material_shortage"})
    assert r.status_code == 201, r.text
    row = env.rows()[0]
    assert (row.work_center_id, str(row.production_order_id), row.production_run_id) == (env.other_center.id, po["id"], run.id)
    assert code(env.add(production_run_id=str(run.id), start=10, end=20)) == "WORK_CENTER_MISMATCH"
    other = env.order()
    r = env.client.post(DT, json={"production_run_id": str(run.id), "production_order_id": other["id"], "start_time": at(10), "category": "other"})
    assert code(r) == "RUN_NOT_IN_ORDER"
    cancelled = env.run(po, status="cancelled")
    r = env.client.post(DT, json={"production_run_id": str(cancelled.id), "start_time": at(10), "category": "other"})
    assert code(r) == "RUN_CANCELLED"


def test_a_machine_is_required_without_a_run(env):
    r = env.client.post(DT, json={"start_time": at(0), "category": "other"})
    assert r.status_code == 422 and code(r) == "WORK_CENTER_REQUIRED"


def test_a_machine_can_stop_without_any_order(env):
    event = env.added("no_orders", start=0, end=480)
    assert event["production_order_id"] is None and event["planned"] is True


# ---- reports -----------------------------------------------------------------------------------

def test_summary_for_reports(env):
    env.added("breakdown", start=0, end=30)
    env.added("breakdown", start=40, end=100)
    env.added("changeover_setup", start=100, end=115)
    env.added("break_meeting", start=120, end=150)
    env.added("utilities", start=0, end=10, center_=env.other_center)
    env.added("other", start=200, end=None)
    s = env.client.get(f"{DT}/summary").json()
    assert (s["count"], Decimal(s["total_minutes"]), Decimal(s["planned_minutes"]), Decimal(s["unplanned_minutes"])) == (5, Decimal("145"), Decimal("30"), Decimal("115"))
    assert s["open_count"] == 1 and Decimal(s["open_minutes_so_far"]) > 0
    assert Decimal(s["mttr_minutes"]) == Decimal("45.00")  # (30 + 60) / 2
    assert [(c["category"], c["planned"], c["count"], Decimal(c["minutes"])) for c in s["by_category"]] == [
        ("breakdown", False, 2, Decimal("90")), ("break_meeting", True, 1, Decimal("30")), ("changeover_setup", False, 1, Decimal("15")), ("utilities", False, 1, Decimal("10"))]
    machines = {m["work_center_name"]: (Decimal(m["minutes"]), Decimal(m["unplanned_minutes"])) for m in s["by_work_center"]}
    assert machines == {"Extruder 1": (Decimal("135"), Decimal("105")), "Extruder 2": (Decimal("10"), Decimal("10"))}
    only = env.client.get(f"{DT}/summary", params={"work_center_id": str(env.other_center.id)}).json()
    assert only["count"] == 1 and Decimal(only["total_minutes"]) == 10


def test_date_filters_use_the_factory_local_day(env):
    env.org.timezone = "Asia/Riyadh"; env.db.commit()  # UTC+3
    late = datetime(2026, 9, 28, 22, 30, tzinfo=timezone.utc)  # 01:30 on the 29th in Riyadh
    env.client.post(DT, json={"work_center_id": str(env.center.id), "start_time": late.isoformat(), "end_time": (late + timedelta(minutes=10)).isoformat(), "category": "other"})
    assert len(env.client.get(DT, params={"date_from": "2026-09-29", "date_to": "2026-09-29"}).json()) == 1
    assert env.client.get(DT, params={"date_to": "2026-09-28"}).json() == []


def test_list_filters(env):
    po = env.order()
    env.added("breakdown", start=0, end=10, production_order_id=po["id"])
    env.added("planned_maintenance", start=20, end=30)
    env.added("other", start=40, end=None)
    names = lambda **q: {e["category"] for e in env.client.get(DT, params=q).json()}  # noqa: E731
    assert names(planned="true") == {"planned_maintenance"}
    assert names(planned="false") == {"breakdown", "other"}
    assert names(status="open") == {"other"}
    assert names(production_order_id=po["id"]) == {"breakdown"}
    assert names(category="planned_maintenance") == {"planned_maintenance"}


# ---- security and records ------------------------------------------------------------------------

def test_other_organizations_are_invisible(env):
    foreign = other_org_demand(env.db)
    center = env.db.scalar(select(WorkCenter).where(WorkCenter.organization_id == foreign.org.id))
    r = env.client.post(DT, json={"work_center_id": str(center.id), "start_time": at(0), "category": "other"})
    assert r.status_code == 422 and code(r) == "WORK_CENTER_NOT_FOUND"
    env.db.add(DowntimeEvent(organization_id=foreign.org.id, work_center_id=center.id, start_time=T0, category="other", planned=False,
                             status="open", created_by_user_id=env.user.id))
    env.db.commit()
    foreign_id = env.db.scalar(select(DowntimeEvent.id).where(DowntimeEvent.organization_id == foreign.org.id))
    assert env.client.get(DT).json() == [] and env.client.get(f"{DT}/{foreign_id}").status_code == 404
    assert env.client.post(f"{DT}/{foreign_id}/close", json={}).status_code == 404
    assert env.client.get(f"{DT}/summary").json()["open_count"] == 0


def test_permissions(env):
    event = env.added(end=None)
    env.ctx.auth_user.permissions = set(PERMISSIONS) - {"production:downtime_events:create", "production:downtime_events:update", "production:downtime_events:delete", "production:downtime_events:close"}
    assert env.add(start=100, end=110).status_code == 403
    assert env.client.post(f"{DT}/{event['id']}/close", json={}).status_code == 403
    assert env.client.patch(f"{DT}/{event['id']}", json={"notes": "x"}).status_code == 403
    assert env.client.delete(f"{DT}/{event['id']}").status_code == 403
    assert env.client.get(f"{DT}/{event['id']}").json()["labels"]["actions"] == []
    env.ctx.auth_user.permissions = set(PERMISSIONS) - {"production:downtime_events:read"}
    assert env.client.get(DT).status_code == 403 and env.client.get(f"{DT}/summary").status_code == 403


def test_delete(env):
    event = env.added()
    assert env.client.delete(f"{DT}/{event['id']}").status_code == 204 and env.rows() == []


def test_work_center_delete_refused_while_downtime_exists(env):
    env.added(center_=env.other_center)
    env.ctx.auth_user.permissions = set(PERMISSIONS) | {"production:work_centers:delete"}
    r = env.client.delete(f"{ROOT}/work-centers/{env.other_center.id}")
    assert r.status_code == 409 and "downtime" in r.json()["detail"]
    assert len(env.rows()) == 1 and env.db.get(WorkCenter, env.other_center.id) is not None
