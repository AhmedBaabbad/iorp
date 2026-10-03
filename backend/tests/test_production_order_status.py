"""Production order status lifecycle: backend-enforced state machine."""
from datetime import date, timedelta
from types import SimpleNamespace
from typing import get_args
from uuid import UUID
import pytest
from sqlalchemy import func, select
from app.main import app
from app.dependencies import get_current_user
from app.core.config import settings
from app.core.tenancy import TenantContext
from app.commercial.infrastructure.models import Customer
from app.production.api.planning_schemas import TransitionRequest
from app.production.application.order_status_service import OrderStatusService, auto_start_due_orders, organization_today
from app.production.domain import order_lifecycle as lifecycle
from app.production.domain.enums import ProductionOrderStatus as S
from app.production.infrastructure.models import ProductionAllocation, ProductionOrder, ProductionOrderStatusHistory, WorkCenter
from tests.test_production_allocation_lifecycle import other_org_demand

ROOT = "/api/v1/production"
ORDER_ACTIONS = ["release", "start", "hold", "complete", "close", "cancel"]
PERMISSIONS = frozenset(["production:production_orders:read", "production:production_orders:update", "production:production_orders:manage_items", "production:planning:read", "production:planning:allocate",
                         "production:production_orders:create"] + [f"production:production_orders:{a}" for a in ORDER_ACTIONS] + [f"production:demands:{a}" for a in ("read", "create", "update")])
ALL_STATUSES = list(S)


@pytest.fixture
def env(client, db, test_org, test_user):
    customer = Customer(organization_id=test_org.id, customer_code="C-STATUS", name="Status Customer")
    center = WorkCenter(organization_id=test_org.id, code="WC-STATUS", name="Line")
    db.add_all([customer, center]); db.commit()
    ctx = SimpleNamespace(user=SimpleNamespace(is_organization_root=False), auth_user=SimpleNamespace(permissions=set(PERMISSIONS)),
                          tenant=TenantContext(test_user.id, test_org.id, permissions=PERMISSIONS))
    app.dependency_overrides[get_current_user] = lambda: ctx

    def order(start=None, end=None):
        r = client.post(f"{ROOT}/demands", json={"customer_id": str(customer.id), "items": [{"product_type": "film", "required_quantity": "1000", "unit": "kg"}]})
        demand_id = r.json()["id"]
        client.post(f"{ROOT}/demands/{demand_id}/status", json={"status": "ready_for_planning"})
        item_id = client.get(f"{ROOT}/demands/{demand_id}").json()["items"][0]["id"]
        today = date.today()
        r = client.post(f"{ROOT}/planning/create-production-order", json=dict(
            allocations=[{"production_demand_item_id": item_id, "allocated_quantity": "400"}], work_center_id=str(center.id),
            planned_start_date=str(start or today + timedelta(days=1)), planned_end_date=str(end or today + timedelta(days=3))))
        assert r.status_code == 201, r.text
        return r.json()

    def act(order_id, action, reason=None, **extra):
        return client.post(f"{ROOT}/production-orders/{order_id}/transitions", json={"action": action, **({"reason": reason} if reason else {}), **extra})

    def walk(order_id, *actions):
        body = None
        for a in actions:
            # These orders record no final result, so closing is the zero-output close (PROD-OUTPUT-001).
            r = act(order_id, a, "because", **({"zero_output": True} if a == "close" else {}))
            assert r.status_code == 200, r.text
            body = r.json()
        return body

    def force(order_id, status):
        row = db.get(ProductionOrder, UUID(order_id)); row.status = status; db.commit()

    return SimpleNamespace(db=db, client=client, org=test_org, user=test_user, ctx=ctx, order=order, act=act, walk=walk, force=force)


# ---- domain rules ------------------------------------------------------------------------

def test_transition_map_matches_the_specification():
    expected = {
        S.DRAFT: {S.RELEASED, S.CANCELLED},
        S.RELEASED: {S.IN_PROGRESS, S.CANCELLED, S.DRAFT},
        S.IN_PROGRESS: {S.ON_HOLD, S.COMPLETED},
        S.ON_HOLD: {S.IN_PROGRESS},
        S.COMPLETED: {S.CLOSED},
        S.CLOSED: set(),
        S.CANCELLED: set(),
    }
    assert {status: {a.target for a in lifecycle.available(status)} for status in S} == expected
    assert lifecycle.TERMINAL == {S.CLOSED, S.CANCELLED}


def test_reasons_confirmations_and_request_schema_stay_in_sync():
    assert {a.name for a in lifecycle.ACTIONS.values() if a.requires_reason} == {"hold", "cancel"}
    assert {a.name for a in lifecycle.ACTIONS.values() if a.confirm} == {"close", "cancel"}
    # The API accepts exactly the domain's actions.
    assert set(get_args(TransitionRequest.model_fields["action"].annotation)) == set(lifecycle.ACTIONS)


def test_planned_dates_raise_flags_but_never_change_status():
    today = date(2026, 10, 10)
    assert lifecycle.start_overdue(S.RELEASED, date(2026, 10, 9), today)
    assert not lifecycle.start_overdue(S.RELEASED, date(2026, 10, 10), today)
    assert not lifecycle.start_overdue(S.IN_PROGRESS, date(2026, 10, 1), today)
    assert lifecycle.finish_overdue(S.ON_HOLD, date(2026, 10, 9), today)
    assert not lifecycle.finish_overdue(S.COMPLETED, date(2026, 10, 1), today)


# ---- the lifecycle through the API --------------------------------------------------------

def test_full_lifecycle_records_dates_and_history(env):
    po = env.order()
    assert po["status"] == "draft" and [a["action"] for a in po["lifecycle"]["actions"]] == ["release", "cancel"]
    started = env.walk(po["id"], "release", "start")
    first_start = started["lifecycle"]["actual_start_at"]
    assert first_start and started["lifecycle"]["actual_end_at"] is None
    resumed = env.walk(po["id"], "hold", "resume")
    assert resumed["status"] == "in_progress" and resumed["lifecycle"]["actual_start_at"] == first_start  # resume keeps start
    done = env.walk(po["id"], "complete")
    assert done["lifecycle"]["actual_end_at"] is not None
    closed = env.walk(po["id"], "close")
    assert closed["status"] == "closed" and closed["lifecycle"]["actions"] == [] and closed["lifecycle"]["terminal"]
    history = env.client.get(f"{ROOT}/production-orders/{po['id']}/status-history").json()
    assert [(h["from_status"], h["to_status"]) for h in history] == [
        ("draft", "released"), ("released", "in_progress"), ("in_progress", "on_hold"), ("on_hold", "in_progress"), ("in_progress", "completed"), ("completed", "closed")]
    assert all(h["trigger"] == "manual" and h["actor_user_id"] == str(env.user.id) for h in history)
    assert history[2]["reason"] == "because"
    assert closed["lifecycle"]["status_version"] == 7


DISALLOWED = [(status, name) for status in ALL_STATUSES for name, action in lifecycle.ACTIONS.items() if status not in action.sources]


@pytest.mark.parametrize("status,action", DISALLOWED)
def test_every_disallowed_transition_is_rejected(env, status, action):
    po = env.order()
    env.force(po["id"], status.value)
    r = env.act(po["id"], action, "reason")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "TRANSITION_NOT_ALLOWED"
    assert env.db.get(ProductionOrder, UUID(po["id"])).status == status


@pytest.mark.parametrize("action,setup", [("hold", ("release", "start")), ("cancel", ())])
def test_hold_and_cancel_need_a_reason(env, action, setup):
    po = env.order()
    env.walk(po["id"], *setup)
    for reason in (None, "   "):
        r = env.act(po["id"], action, reason)
        assert r.status_code == 400 and r.json()["detail"]["code"] == "REASON_REQUIRED"


def test_each_action_needs_its_own_permission(env):
    po = env.order()
    env.ctx.auth_user.permissions = set(PERMISSIONS) - {"production:production_orders:release"}
    body = env.client.get(f"{ROOT}/production-orders/{po['id']}").json()
    assert [a["action"] for a in body["lifecycle"]["actions"]] == ["cancel"]  # release hidden
    r = env.act(po["id"], "release")
    assert r.status_code == 403 and r.json()["detail"]["code"] == "ACTION_FORBIDDEN"
    env.ctx.auth_user.permissions = set(PERMISSIONS)
    env.walk(po["id"], "release")
    env.ctx.auth_user.permissions = set(PERMISSIONS) - {"production:production_orders:start"}
    assert env.act(po["id"], "start").status_code == 403
    assert "start" not in [a["action"] for a in env.client.get(f"{ROOT}/production-orders/{po['id']}").json()["lifecycle"]["actions"]]


def test_organization_root_may_take_every_action(env):
    po = env.order()
    env.ctx.user.is_organization_root = True
    env.ctx.auth_user.permissions = {"production:production_orders:read"}
    assert env.act(po["id"], "release").status_code == 200


def test_stale_version_is_a_conflict(env):
    po = env.order()
    seen = po["lifecycle"]["status_version"]
    assert env.act(po["id"], "release", expected_version=seen).status_code == 200
    r = env.act(po["id"], "return_to_draft", expected_version=seen)  # someone released it after this user loaded the page
    assert r.status_code == 409 and r.json()["detail"]["code"] == "ORDER_STATUS_CHANGED"
    assert r.json()["detail"]["current_status"] == "released"


def test_status_cannot_be_patched(env):
    po = env.order()
    assert env.client.patch(f"{ROOT}/production-orders/{po['id']}", json={"status": "completed"}).status_code == 422
    assert env.db.get(ProductionOrder, UUID(po["id"])).status == S.DRAFT


def test_release_locks_lines_and_return_to_draft_unlocks_them(env):
    po = env.order()
    released = env.walk(po["id"], "release")
    assert released["editable"] is False
    assert env.walk(po["id"], "return_to_draft")["editable"] is True


def test_cancel_transition_returns_quantities_to_planning(env):
    po = env.order()
    body = env.walk(po["id"], "release", "cancel")
    assert body["status"] == "cancelled" and {a["status"] for a in body["allocations"]} == {"released"}
    assert env.db.scalar(select(func.count()).select_from(ProductionAllocation).where(ProductionAllocation.status == "active")) == 0


def test_closed_orders_cannot_be_edited(env):
    po = env.order()
    env.walk(po["id"], "release", "start", "complete", "close")
    assert env.client.patch(f"{ROOT}/production-orders/{po['id']}", json={"notes": "late change"}).status_code == 400


def test_history_is_tenant_scoped_and_names_the_actor(env):
    po = env.order()
    env.walk(po["id"], "release")
    history = env.client.get(f"{ROOT}/production-orders/{po['id']}/status-history").json()
    assert history[0]["actor_name"] == env.user.full_name
    other = other_org_demand(env.db)
    assert env.client.get(f"{ROOT}/production-orders/{other.order.id}/status-history").status_code == 404
    assert env.act(other.order.id, "release").status_code == 404


def test_overdue_flags_on_the_order(env):
    today = organization_today(env.db, env.org.id)  # planned dates are the factory's local days
    po = env.order(start=today - timedelta(days=2), end=today - timedelta(days=1))
    assert po["lifecycle"]["start_overdue"] is True and po["lifecycle"]["finish_overdue"] is True
    started = env.walk(po["id"], "release", "start")
    assert started["lifecycle"]["start_overdue"] is False and started["lifecycle"]["finish_overdue"] is True


# ---- automatic transitions ----------------------------------------------------------------

def test_date_based_start_is_off_by_default():
    assert settings.production_auto_start_by_date is False


def test_scheduled_start_is_idempotent_and_touches_only_due_released_orders(env):
    today = date.today()
    due, later, draft = env.order(start=today), env.order(start=today + timedelta(days=5), end=today + timedelta(days=9)), env.order(start=today)
    env.walk(due["id"], "release"); env.walk(later["id"], "release")
    assert auto_start_due_orders(env.db, today) == 1
    assert auto_start_due_orders(env.db, today) == 0  # second run changes nothing
    env.db.expire_all()
    assert env.db.get(ProductionOrder, UUID(due["id"])).status == S.IN_PROGRESS
    assert env.db.get(ProductionOrder, UUID(later["id"])).status == S.RELEASED
    assert env.db.get(ProductionOrder, UUID(draft["id"])).status == S.DRAFT
    row = env.db.scalar(select(ProductionOrderStatusHistory).where(ProductionOrderStatusHistory.production_order_id == UUID(due["id"]), ProductionOrderStatusHistory.trigger == "schedule"))
    assert row.actor_user_id is None and row.to_status == "in_progress"


def test_activity_extension_point_starts_only_released_orders(env):
    po = env.order()
    service = OrderStatusService(env.db, TenantContext(env.user.id, env.org.id))
    assert service.start_from_activity(UUID(po["id"]), "production_run").status == S.DRAFT  # not released: no change
    env.walk(po["id"], "release")
    assert service.start_from_activity(UUID(po["id"]), "production_run").status == S.IN_PROGRESS
    assert service.start_from_activity(UUID(po["id"]), "production_run").status == S.IN_PROGRESS  # idempotent
    rows = env.db.scalars(select(ProductionOrderStatusHistory).where(ProductionOrderStatusHistory.production_order_id == UUID(po["id"]), ProductionOrderStatusHistory.trigger == "activity")).all()
    assert len(rows) == 1 and rows[0].actor_user_id is None


def test_scheduler_loop_runs_survives_errors_and_stops(monkeypatch):
    import asyncio
    from app.production.application import order_scheduler
    calls = []
    def run_once():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("database briefly unavailable")
        return 0
    monkeypatch.setattr(order_scheduler, "run_once", run_once)
    monkeypatch.setattr(order_scheduler.settings, "production_auto_start_interval_minutes", 1)
    async def scenario():
        stop = asyncio.Event()
        real_wait_for = asyncio.wait_for
        async def fast_wait_for(awaitable, timeout):  # skip the minute between runs
            if len(calls) >= 2:
                stop.set()
            return await real_wait_for(awaitable, timeout=0.01)
        monkeypatch.setattr(order_scheduler.asyncio, "wait_for", fast_wait_for)
        await real_wait_for(order_scheduler.auto_start_loop(stop), timeout=5)
    asyncio.run(scenario())
    assert len(calls) >= 2  # the failed first run did not stop the loop


@pytest.mark.parametrize("zone", ["Pacific/Kiritimati", "Pacific/Pago_Pago"])  # UTC+14 and UTC-11
def test_scheduled_start_uses_each_organizations_local_date(env, zone):
    env.org.timezone = zone; env.db.commit()
    local = organization_today(env.db, env.org.id)
    due, tomorrow = env.order(start=local), env.order(start=local + timedelta(days=1), end=local + timedelta(days=4))
    env.walk(due["id"], "release"); env.walk(tomorrow["id"], "release")
    assert auto_start_due_orders(env.db) == 1  # no pinned date: the organization's own "today"
    env.db.expire_all()
    assert env.db.get(ProductionOrder, UUID(due["id"])).status == S.IN_PROGRESS
    assert env.db.get(ProductionOrder, UUID(tomorrow["id"])).status == S.RELEASED
