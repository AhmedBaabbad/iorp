"""DASH-001: the production dashboard — output and scrap in kilograms, unplanned stop hours, completed orders, the
chart over the period, and what waits for someone; each part only with the permission to read its data."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.dashboard import window
from app.core.tenancy import TenantContext
from app.dependencies import get_current_user
from app.main import app
from app.production.infrastructure.models import (
    DowntimeEvent, ProductionDemand, ProductionOrder, ProductionOrderStatusHistory, ProductionResultEntry, WorkCenter,
)
from app.commercial.infrastructure.models import Customer

URL = "/api/v1/production/dashboard"
ALL = {"production:production_orders:read", "production:results:read", "production:downtime_events:read", "production:demands:read"}


@pytest.fixture
def floor(client, db, test_org, test_user):
    now = datetime.now(timezone.utc)
    center = WorkCenter(organization_id=test_org.id, code="WC-1", name="Extruder 1")
    db.add(center)
    db.flush()

    def order(status, end):
        o = ProductionOrder(organization_id=test_org.id, production_order_number=f"PO-{uuid4().hex[:6]}", work_center_id=center.id,
                            product_type="pp_strap", planned_quantity=Decimal(100), unit="kg", status=status,
                            planned_start_date=end - timedelta(days=2), planned_end_date=end, created_by_user_id=test_user.id)
        db.add(o)
        db.flush()
        return o

    done = order("completed", now.date())
    late = order("in_progress", now.date() - timedelta(days=3))

    def result(qty, unit, loss, when, sq=None, su=None):
        db.add(ProductionResultEntry(organization_id=test_org.id, production_order_id=done.id, disposition="scrap" if loss else "stock_good",
                                     quantity=Decimal(qty), unit=unit, secondary_quantity=sq, secondary_unit=su, counts_as_loss=loss,
                                     entry_type="original", created_by_user_id=test_user.id, created_at=when))

    result("900", "kg", False, now)                                   # today
    result("2", "ton", False, now - timedelta(days=10))               # 2000 kg in the period
    result("100", "kg", True, now - timedelta(days=10))               # scrap
    result("50", "roll", False, now - timedelta(days=5), Decimal("500"), "kg")  # rolls count through their weight
    result("30", "roll", False, now - timedelta(days=5))              # no weight: left out
    result("400", "kg", False, now - timedelta(days=120))             # the previous period (3m)
    db.add(DowntimeEvent(organization_id=test_org.id, work_center_id=center.id, start_time=now - timedelta(days=2), end_time=now - timedelta(days=2) + timedelta(hours=3),
                         duration_minutes=Decimal(180), category="breakdown", planned=False, status="closed", created_by_user_id=test_user.id))
    db.add(DowntimeEvent(organization_id=test_org.id, work_center_id=center.id, start_time=now - timedelta(days=1),
                         end_time=now - timedelta(days=1) + timedelta(hours=10), duration_minutes=Decimal(600),
                         category="planned_maintenance", planned=True, status="closed", created_by_user_id=test_user.id))  # planned: not counted
    db.add(DowntimeEvent(organization_id=test_org.id, work_center_id=center.id, start_time=now - timedelta(hours=1), category="breakdown",
                         planned=False, status="open", created_by_user_id=test_user.id))
    db.add(ProductionOrderStatusHistory(organization_id=test_org.id, production_order_id=done.id, from_status="in_progress", to_status="completed",
                                        action="complete", trigger="manual", actor_user_id=test_user.id, created_at=now - timedelta(days=1)))
    customer = Customer(organization_id=test_org.id, customer_code="C-1", name="Gulf")
    db.add(customer)
    db.flush()
    db.add(ProductionDemand(organization_id=test_org.id, demand_number="PD-1", customer_id=customer.id, status="ready_for_planning",
                            request_date=now.date(), created_by_user_id=test_user.id))
    db.commit()

    def as_user(permissions):
        ctx = SimpleNamespace(user=SimpleNamespace(is_organization_root=False), auth_user=SimpleNamespace(permissions=set(permissions)),
                              tenant=TenantContext(test_user.id, test_org.id, permissions=frozenset(permissions)))
        app.dependency_overrides[get_current_user] = lambda: ctx
    yield SimpleNamespace(client=client, as_user=as_user, late=late)
    app.dependency_overrides.pop(get_current_user, None)


def card(board, key):
    return next(c for c in board["cards"] if c["key"] == key)


def test_the_cards_compare_the_period_with_the_one_before(floor):
    floor.as_user(ALL)
    board = floor.client.get(f"{URL}?period=3m").json()
    produced = card(board, "produced")
    assert (Decimal(produced["value"]), Decimal(produced["previous"]), Decimal(produced["today"])) == (Decimal(3400), Decimal(400), Decimal(900))
    assert Decimal(card(board, "scrap_rate")["value"]) == Decimal("2.9")  # 100 / (3400 + 100)
    downtime = Decimal(card(board, "downtime")["value"])
    assert Decimal("3.9") <= downtime <= Decimal("4.1")  # 3 h closed + the open stop's first hour; planned stops are not losses
    assert Decimal(card(board, "completed_orders")["value"]) == 1
    assert card(board, "scrap_rate")["good_when"] == "down"


def test_the_chart_has_a_point_for_every_day_or_week(floor):
    floor.as_user(ALL)
    daily = floor.client.get(f"{URL}?period=1m").json()
    produced = next(s for s in daily["series"] if s["key"] == "produced")
    assert len(produced["points"]) == 30 and sum(Decimal(p["value"]) for p in produced["points"]) == Decimal(3400)
    yearly = floor.client.get(f"{URL}?period=1y").json()
    assert len(next(s for s in yearly["series"] if s["key"] == "produced")["points"]) in (53, 54)  # weeks


def test_what_waits_for_someone(floor):
    floor.as_user(ALL)
    board = floor.client.get(URL).json()
    kinds = [a["kind"] for a in board["attention"]]
    assert set(kinds[:2]) == {"open_downtime", "overdue_order"} and kinds[-1] == "waiting_demand"  # urgent first, then by date
    assert next(a for a in board["attention"] if a["kind"] == "overdue_order")["href"] == f"/production-orders/{floor.late.id}"


def test_each_part_needs_the_permission_to_read_its_data(floor):
    floor.as_user({"production:downtime_events:read"})
    board = floor.client.get(URL).json()
    assert [c["key"] for c in board["cards"]] == ["downtime"] and board["series"] == []
    assert {a["kind"] for a in board["attention"]} == {"open_downtime"}
    floor.as_user({"commercial:customers:read"})
    assert floor.client.get(URL).status_code == 403


def test_periods():
    today = date(2026, 10, 7)
    assert (window("1w", today).start, window("1w", today).days) == (date(2026, 10, 1), 7)
    ytd = window("ytd", today)
    assert ytd.start == date(2026, 1, 1) and ytd.weekly and ytd.previous_start == date(2025, 3, 27)  # 280 days before
    assert not window("3m", today).weekly


def test_without_weights_the_figures_are_in_the_unit_recorded_the_most(client, db, test_org, test_user):
    """A floor that records rolls only sees rolls, never zero kilograms; two units are never added up."""
    now = datetime.now(timezone.utc)
    center = WorkCenter(organization_id=test_org.id, code="WC-R", name="Rewinder")
    db.add(center)
    db.flush()
    order = ProductionOrder(organization_id=test_org.id, production_order_number="PO-R1", work_center_id=center.id, product_type="pp_strap",
                            planned_quantity=Decimal(100), unit="roll", status="completed", planned_start_date=now.date(),
                            planned_end_date=now.date(), created_by_user_id=test_user.id)
    db.add(order)
    db.flush()
    for qty, unit, loss in (("15", "roll", False), ("5", "roll", True), ("3", "box", False)):
        db.add(ProductionResultEntry(organization_id=test_org.id, production_order_id=order.id, disposition="scrap" if loss else "stock_good",
                                     quantity=Decimal(qty), unit=unit, counts_as_loss=loss, entry_type="original", created_by_user_id=test_user.id,
                                     created_at=now - timedelta(days=1)))
    db.commit()
    ctx = SimpleNamespace(user=SimpleNamespace(is_organization_root=False), auth_user=SimpleNamespace(permissions=set(ALL)),
                          tenant=TenantContext(test_user.id, test_org.id, permissions=frozenset(ALL)))
    app.dependency_overrides[get_current_user] = lambda: ctx
    try:
        board = client.get(URL).json()
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    produced = card(board, "produced")
    assert (produced["unit"], Decimal(produced["value"])) == ("roll", Decimal(15))
    assert Decimal(card(board, "scrap_rate")["value"]) == Decimal(25)  # 5 / (15 + 5)
