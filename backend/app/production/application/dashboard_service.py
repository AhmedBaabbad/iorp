"""The production dashboard (DASH-001): what the floor made, lost and stopped for, how the orders stand, and what waits.

Figures come from production's own tables only. Quantities are added in kilograms when the floor records weights: a
result in a weight unit is converted, one in another unit (rolls) counts through its secondary weight. Where no weight is
recorded, the figures are in the unit recorded the most (rolls); two different units are never added up.

  produced          good output (customer, stock, samples) in the period
  scrap_rate        loss / (good + loss), in %
  downtime          unplanned stop hours that started in the period (an open stop counts until now)
  completed_orders  production orders that reached "completed" in the period
  on_time           of those, the share completed by their planned end date
  active_orders     orders running now; on_hold: orders held now; waiting_demands: demands ready for planning now
"""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dashboard import (
    Attention, Card, Dashboard, Period, RankItem, Ranking, Series, Window, as_day, breakdown, card, count_by_day, points, rate, tally, window,
)
from app.core.units import KILOGRAMS
from app.production.domain import permissions as P
from app.production.domain.enums import DowntimeStatus, ProductionOrderStatus
from app.production.infrastructure.models import (
    DowntimeEvent,
    ProductionDemand,
    ProductionOrder,
    ProductionOrderStatusHistory,
    ProductionResultEntry,
    WorkCenter,
)

ZERO = Decimal(0)
OPEN_ORDER = (ProductionOrderStatus.RELEASED, ProductionOrderStatus.IN_PROGRESS, ProductionOrderStatus.ON_HOLD)
ATTENTION_LIMIT = 10


def _kg(quantity, unit, secondary_quantity, secondary_unit) -> Decimal | None:
    if unit in KILOGRAMS:
        return Decimal(quantity) * KILOGRAMS[unit]
    if secondary_unit in KILOGRAMS and secondary_quantity is not None:
        return Decimal(secondary_quantity) * KILOGRAMS[secondary_unit]
    return None


class ProductionDashboard:
    def __init__(self, db: Session, organization_id, can) -> None:
        self.db, self.org, self.can = db, organization_id, can

    def build(self, period: Period) -> Dashboard:
        w = window(period)
        board = Dashboard(module="production", period=period, start=w.start, end=w.end - timedelta(days=1))
        if self.can(P.RESULTS_READ):
            self._results(w, board)
        if self.can(P.DOWNTIME_READ):
            self._downtime(w, board)
        if self.can(P.ORDERS_READ):
            self._orders(w, board)
        if self.can(P.DEMANDS_READ):
            self._waiting_demands(board)
        board.attention.sort(key=lambda a: ({"danger": 0, "warning": 1, "info": 2}[a.severity], a.date or date.max))
        board.attention_total = len(board.attention)
        board.attention = board.attention[:ATTENTION_LIMIT]
        return board

    # ── output and scrap ──────────────────────────────────────────────────────────────────────────────────────
    def _results(self, w: Window, board: Dashboard) -> None:
        rows = self.db.execute(select(
            ProductionResultEntry.created_at, ProductionResultEntry.quantity, ProductionResultEntry.unit,
            ProductionResultEntry.secondary_quantity, ProductionResultEntry.secondary_unit, ProductionResultEntry.counts_as_loss,
            ProductionResultEntry.reason_code, ProductionResultEntry.disposition, ProductionOrder.product_type, WorkCenter.name,
        ).join(ProductionOrder, ProductionOrder.id == ProductionResultEntry.production_order_id)
         .join(WorkCenter, WorkCenter.id == ProductionOrder.work_center_id)
         .where(ProductionResultEntry.organization_id == self.org, ProductionResultEntry.created_at >= w.at(w.previous_start),
                ProductionResultEntry.created_at < w.at(w.end))).all()
        measured = []  # (day, unit, amount, loss, reason, product, center)
        for created_at, quantity, unit, sq, su, is_loss, reason, disposition, product, center in rows:
            kg = _kg(quantity, unit, sq, su)
            measured.append((as_day(created_at), "kg" if kg is not None else unit, kg if kg is not None else Decimal(quantity), is_loss,
                             reason or disposition, product, center))
        # Kilograms when the floor records weights; otherwise the unit it records the most (never two units added up).
        volume = defaultdict(lambda: ZERO)
        for _, u, amount, *_ in measured:
            volume[u] += amount
        unit = "kg" if volume.get("kg") else max(volume, key=volume.get, default="kg")
        good, loss = defaultdict(lambda: ZERO), defaultdict(lambda: ZERO)
        by_product, by_center, by_reason = defaultdict(lambda: ZERO), defaultdict(lambda: ZERO), defaultdict(lambda: ZERO)
        for day, u, amount, is_loss, reason, product, center in measured:
            if u != unit:
                continue
            (loss if is_loss else good)[day] += amount
            if w.start <= day < w.end:
                if is_loss:
                    by_reason[reason or "other"] += amount
                else:
                    by_product[product] += amount
                    by_center[center] += amount

        board.cards.append(card("produced", w, good, unit=unit, href="/production-results"))
        g_now, g_before, g_today = tally(w, good)
        l_now, l_before, l_today = tally(w, loss)
        board.cards.append(Card(key="scrap_rate", unit="%", good_when="down", href="/production-results", style="gauge",
                                value=rate(l_now, g_now + l_now), previous=rate(l_before, g_before + l_before), today=rate(l_today, g_today + l_today)))
        board.series.append(Series(key="produced", unit=unit, points=points(w, good)))
        board.series.append(Series(key="scrap", unit=unit, points=points(w, loss)))
        board.breakdowns.append(breakdown("output_by_center", list(by_center.items()), unit=unit, labels={k: k for k in by_center}, limit=8))
        board.breakdowns.append(breakdown("scrap_by_reason", list(by_reason.items()), unit=unit, limit=8))
        top = sorted(by_product.items(), key=lambda kv: kv[1], reverse=True)[:6]
        board.rankings.append(Ranking(key="top_products", unit=unit, items=[RankItem(label=k, value=v) for k, v in top]))

    # ── stops ─────────────────────────────────────────────────────────────────────────────────────────────────
    def _downtime(self, w: Window, board: Dashboard) -> None:
        now = datetime.now(timezone.utc)
        rows = self.db.execute(select(DowntimeEvent.start_time, DowntimeEvent.end_time, DowntimeEvent.duration_minutes, DowntimeEvent.category)
                               .where(DowntimeEvent.organization_id == self.org, DowntimeEvent.planned.is_(False),
                                      DowntimeEvent.start_time >= w.at(w.previous_start), DowntimeEvent.start_time < w.at(w.end))).all()
        hours, by_category = defaultdict(lambda: ZERO), defaultdict(lambda: ZERO)
        for start, end, minutes, category in rows:
            if minutes is None:
                start = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
                minutes = Decimal(max(0, ((end or now) - start).total_seconds()) / 60)
            h = Decimal(minutes) / 60
            hours[as_day(start)] += h
            if w.start <= as_day(start) < w.end:
                by_category[category] += h
        downtime = card("downtime", w, hours, unit="h", good_when="down", href="/downtime-events")
        downtime.value, downtime.previous, downtime.today = (x.quantize(Decimal("0.1")) for x in (downtime.value, downtime.previous, downtime.today))
        board.cards.append(downtime)
        board.breakdowns.append(breakdown("downtime_by_category", [(k, v.quantize(Decimal("0.1"))) for k, v in by_category.items()], unit="h"))
        open_stops = self.db.execute(select(DowntimeEvent.id, DowntimeEvent.start_time, DowntimeEvent.category, WorkCenter.name)
                                     .join(WorkCenter, WorkCenter.id == DowntimeEvent.work_center_id)
                                     .where(DowntimeEvent.organization_id == self.org, DowntimeEvent.status == DowntimeStatus.OPEN)
                                     .order_by(DowntimeEvent.start_time).limit(ATTENTION_LIMIT)).all()
        for event_id, start, category, center in open_stops:
            board.attention.append(Attention(kind="open_downtime", id=str(event_id), label=center, detail=category, date=as_day(start),
                                             href=f"/downtime-events/{event_id}", severity="danger"))

    # ── orders ────────────────────────────────────────────────────────────────────────────────────────────────
    def _orders(self, w: Window, board: Dashboard) -> None:
        done = self.db.execute(select(ProductionOrderStatusHistory.created_at, ProductionOrder.planned_end_date)
                               .join(ProductionOrder, ProductionOrder.id == ProductionOrderStatusHistory.production_order_id)
                               .where(ProductionOrderStatusHistory.organization_id == self.org, ProductionOrderStatusHistory.to_status == "completed",
                                      ProductionOrderStatusHistory.created_at >= w.at(w.previous_start),
                                      ProductionOrderStatusHistory.created_at < w.at(w.end))).all()
        completed = count_by_day(as_day(at) for at, _ in done)
        board.cards.append(card("completed_orders", w, completed, href="/production-orders"))

        def on_time(first, last):
            rows = [(as_day(at), due) for at, due in done if first <= as_day(at) < last]
            return rate(sum(1 for day, due in rows if day <= due), len(rows))
        board.cards.append(Card(key="on_time", unit="%", style="gauge", target=Decimal(95), href="/production-orders",
                                value=on_time(w.start, w.end), previous=on_time(w.previous_start, w.start)))

        statuses = dict(self.db.execute(select(ProductionOrder.status, func.count(ProductionOrder.id))
                                        .where(ProductionOrder.organization_id == self.org).group_by(ProductionOrder.status)).all())
        get = lambda s: Decimal(statuses.get(s, 0))  # noqa: E731
        board.cards.append(Card(key="active_orders", style="count", value=get(ProductionOrderStatus.IN_PROGRESS), href="/production-orders"))
        board.cards.append(Card(key="on_hold", style="count", good_when="down", value=get(ProductionOrderStatus.ON_HOLD), href="/production-orders"))
        board.breakdowns.append(breakdown("orders_by_status", [(s, n) for s, n in statuses.items()
                                                                if s not in (ProductionOrderStatus.CLOSED, ProductionOrderStatus.CANCELLED)], style="donut"))
        late = self.db.execute(select(ProductionOrder.id, ProductionOrder.production_order_number, ProductionOrder.planned_end_date,
                                      ProductionOrder.status, WorkCenter.name)
                               .join(WorkCenter, WorkCenter.id == ProductionOrder.work_center_id)
                               .where(ProductionOrder.organization_id == self.org, ProductionOrder.status.in_(OPEN_ORDER),
                                      ProductionOrder.planned_end_date < w.today)
                               .order_by(ProductionOrder.planned_end_date).limit(ATTENTION_LIMIT)).all()
        for order_id, number, due, status, center in late:
            board.attention.append(Attention(kind="overdue_order", id=str(order_id), label=number, detail=center, date=due,
                                             href=f"/production-orders/{order_id}",
                                             severity="danger" if status != ProductionOrderStatus.ON_HOLD else "warning"))

    def _waiting_demands(self, board: Dashboard) -> None:
        waiting = self.db.execute(select(ProductionDemand.id, ProductionDemand.demand_number, ProductionDemand.requested_delivery_date)
                                  .where(ProductionDemand.organization_id == self.org, ProductionDemand.status == "ready_for_planning")
                                  .order_by(ProductionDemand.requested_delivery_date.is_(None), ProductionDemand.requested_delivery_date)).all()
        board.cards.append(Card(key="waiting_demands", style="count", value=Decimal(len(waiting)), href="/production/planning"))
        for demand_id, number, due in waiting[:ATTENTION_LIMIT]:
            board.attention.append(Attention(kind="waiting_demand", id=str(demand_id), label=number, date=due,
                                             href=f"/production/demands/{demand_id}", severity="info"))
