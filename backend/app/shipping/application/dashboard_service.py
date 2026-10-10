"""The shipping and delivery dashboard (DASH-001): what left the factory, what reached the customer, what came back,
and what waits at the gate or on the road.

Figures come from shipping's own tables only.

  dispatched      delivery notes that left the factory in the period; shipped_weight: their gate weight (kg)
  delivered       notes the customer received (in full or in part) in the period
  delivery_rate   of the deliveries settled in the period, the share received (in full or in part)
  failed          deliveries that failed in the period; returns: customer returns registered in the period
  ready, in_transit   notes waiting at the gate and on the road now
"""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dashboard import (
    Attention, Card, Dashboard, Period, RankItem, Ranking, Series, Window, as_day, breakdown, card, count_by_day, points, rate, window,
)
from app.shipping.domain import permissions as S
from app.shipping.domain import returns as R
from app.shipping.domain import rules
from app.shipping.infrastructure.models import Shipment, ShipmentReturn

ZERO = Decimal(0)
ATTENTION_LIMIT = 10
RECEIVED = (rules.DELIVERED, rules.PARTIALLY_DELIVERED)
IN_TRANSIT_DAYS = 3  # on the road longer than this asks for attention


class ShippingDashboard:
    def __init__(self, db: Session, organization_id, can) -> None:
        self.db, self.org, self.can = db, organization_id, can

    def build(self, period: Period) -> Dashboard:
        w = window(period)
        board = Dashboard(module="shipping", period=period, start=w.start, end=w.end - timedelta(days=1))
        if self.can(S.SHIPMENTS_READ):
            self._shipments(w, board)
        if self.can(S.RETURNS_READ):
            self._returns(w, board)
        board.attention.sort(key=lambda a: ({"danger": 0, "warning": 1, "info": 2}[a.severity], a.date or date.max))
        board.attention_total = len(board.attention)
        board.attention = board.attention[:ATTENTION_LIMIT]
        return board

    def _shipments(self, w: Window, board: Dashboard) -> None:
        since = w.at(w.previous_start)
        rows = self.db.execute(select(Shipment.dispatched_at, Shipment.delivered_at, Shipment.failed_at, Shipment.status, Shipment.gate_weight_kg,
                                      Shipment.customer_name, Shipment.customer_id, Shipment.delivery_city)
                               .where(Shipment.organization_id == self.org,
                                      (Shipment.dispatched_at >= since) | (Shipment.delivered_at >= since) | (Shipment.failed_at >= since))).all()
        dispatched, weight, delivered, failed = defaultdict(int), defaultdict(lambda: ZERO), defaultdict(int), defaultdict(int)
        by_customer, by_city = defaultdict(lambda: ZERO), defaultdict(int)
        settled_ok, settled_all = defaultdict(int), defaultdict(int)
        for dispatched_at, delivered_at, failed_at, status, gate, customer, customer_id, city in rows:
            if dispatched_at:
                day = as_day(dispatched_at)
                dispatched[day] += 1
                weight[day] += Decimal(gate or 0)
                if w.start <= day < w.end:
                    by_customer[(customer, customer_id)] += Decimal(gate or 0)
                    by_city[city or "—"] += 1
            if delivered_at and status in RECEIVED:
                delivered[as_day(delivered_at)] += 1
                settled_ok[as_day(delivered_at)] += 1
                settled_all[as_day(delivered_at)] += 1
            if failed_at:
                failed[as_day(failed_at)] += 1
                if status not in RECEIVED:
                    settled_all[as_day(failed_at)] += 1
        board.cards.append(card("dispatched", w, dispatched, href="/shipments"))
        board.cards.append(card("delivered", w, delivered, href="/shipments"))
        ok_now = sum(v for d, v in settled_ok.items() if w.start <= d < w.end)
        all_now = sum(v for d, v in settled_all.items() if w.start <= d < w.end)
        ok_before = sum(v for d, v in settled_ok.items() if w.previous_start <= d < w.start)
        all_before = sum(v for d, v in settled_all.items() if w.previous_start <= d < w.start)
        board.cards.append(Card(key="delivery_rate", unit="%", style="gauge", target=Decimal(98), href="/shipments",
                                value=rate(ok_now, all_now), previous=rate(ok_before, all_before)))
        board.cards.append(card("shipped_weight", w, weight, unit="kg", href="/shipments"))
        board.cards.append(card("failed", w, failed, good_when="down", href="/shipments"))
        board.series.append(Series(key="dispatched", points=points(w, dispatched)))
        board.series.append(Series(key="delivered", points=points(w, delivered)))
        board.breakdowns.append(breakdown("deliveries_by_city", list(by_city.items()), labels={k: k for k in by_city}, limit=8))
        top = sorted(by_customer.items(), key=lambda kv: kv[1], reverse=True)[:6]
        board.rankings.append(Ranking(key="top_customers", unit="kg", items=[
            RankItem(label=name, value=v, href=f"/customers/{customer_id}" if customer_id else None) for (name, customer_id), v in top]))

        statuses = dict(self.db.execute(select(Shipment.status, func.count(Shipment.id)).where(
            Shipment.organization_id == self.org, Shipment.status.in_((rules.DRAFT, rules.READY, rules.DISPATCHED, rules.NOT_DELIVERED)))
            .group_by(Shipment.status)).all())
        board.cards.append(Card(key="ready", style="count", value=Decimal(statuses.get(rules.READY, 0)), href="/shipments"))
        board.cards.append(Card(key="in_transit", style="count", value=Decimal(statuses.get(rules.DISPATCHED, 0)), href="/shipments"))
        board.breakdowns.append(breakdown("open_by_status", [(s, statuses.get(s, 0)) for s in (rules.DRAFT, rules.READY, rules.DISPATCHED,
                                                                                               rules.NOT_DELIVERED)], style="funnel"))
        waiting = self.db.execute(select(Shipment.id, Shipment.shipment_no, Shipment.customer_name, Shipment.status, Shipment.shipment_date,
                                         Shipment.dispatched_at)
                                  .where(Shipment.organization_id == self.org,
                                         Shipment.status.in_((rules.READY, rules.DISPATCHED, rules.NOT_DELIVERED)))
                                  .order_by(Shipment.shipment_date)).all()
        for shipment_id, number, customer, status, planned, dispatched_at in waiting:
            if status == rules.NOT_DELIVERED:
                kind, severity = "failed_delivery", "danger"
            elif status == rules.READY and planned <= w.today:
                kind, severity = "ready_to_dispatch", "warning"
            elif status == rules.DISPATCHED and dispatched_at and as_day(dispatched_at) < w.today - timedelta(days=IN_TRANSIT_DAYS):
                kind, severity = "long_in_transit", "warning"
            else:
                continue
            board.attention.append(Attention(kind=kind, id=str(shipment_id), label=number, detail=customer, date=planned,
                                             href=f"/shipments/{shipment_id}", severity=severity))

    def _returns(self, w: Window, board: Dashboard) -> None:
        rows = self.db.execute(select(ShipmentReturn.requested_at, ShipmentReturn.reason).where(
            ShipmentReturn.organization_id == self.org, ShipmentReturn.requested_at >= w.at(w.previous_start),
            ShipmentReturn.requested_at < w.at(w.end))).all()
        board.cards.append(card("returns", w, count_by_day(as_day(at) for at, _ in rows), good_when="down", href="/shipment-returns"))
        by_reason = defaultdict(int)
        for at, reason in rows:
            if w.start <= as_day(at) < w.end:
                by_reason[reason] += 1
        board.breakdowns.append(breakdown("returns_by_reason", list(by_reason.items()), style="donut"))
        waiting = self.db.execute(select(ShipmentReturn.id, ShipmentReturn.return_no, ShipmentReturn.customer_name, ShipmentReturn.status,
                                         ShipmentReturn.requested_at)
                                  .where(ShipmentReturn.organization_id == self.org, ShipmentReturn.status.in_((R.REQUESTED, R.APPROVED)))
                                  .order_by(ShipmentReturn.requested_at)).all()
        for return_id, number, customer, status, at in waiting:
            board.attention.append(Attention(kind="return_to_decide" if status == R.REQUESTED else "return_to_receive", id=str(return_id),
                                             label=number, detail=customer, date=as_day(at), href=f"/shipment-returns/{return_id}",
                                             severity="warning" if status == R.REQUESTED else "info"))
