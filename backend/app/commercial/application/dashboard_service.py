"""The customers and sales dashboard (DASH-001): who came, what was offered and won, what was ordered, the samples and
the follow-ups, and what waits for the sales team.

Figures come from the commercial module's own tables only. A user whose read scope is "own" sees their own customers'
figures only (commercial/application/visibility.py); amounts keep their currency, never added across currencies.

  new_customers       customers registered in the period; active_customers: customers active now
  quotes_issued       quotations dated in the period and sent (not drafts)
  acceptance_rate     of those decided, the share accepted
  orders_confirmed    sales orders confirmed in the period; confirmed_value_<currency>: their value
  samples_requested   sample requests in the period; overdue_follow_ups: follow-ups past their date now
"""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.commercial.application.visibility import ORDERS_READ, QUOTES_READ, SAMPLES_READ, visible_owner
from app.commercial.domain.enums import CommercialOrderStatus, CustomerStatus, FollowUpStatus, QuoteStatus, RelationshipStage, SampleStatus
from app.commercial.infrastructure.models import CommercialOrder, CommercialOrderItem, Customer, FollowUp, Quote, Sample
from app.core.dashboard import (
    Attention, Card, Dashboard, Period, RankItem, Ranking, Series, Window, as_day, breakdown, card, count_by_day, points, rate, window,
)
from app.core.tenancy import TenantContext
from app.core.utils import utc_now
from app.commercial.domain.enums import SampleDecision

ATTENTION_LIMIT = 10
CUSTOMERS_READ, FOLLOW_UPS_READ = "commercial:customers:read", "commercial:follow_ups:read"
EXPIRY_DAYS, DRAFT_DAYS = 7, 7


class CommercialDashboard:
    def __init__(self, db: Session, tenant: TenantContext, can) -> None:
        self.db, self.tenant, self.org, self.can = db, tenant, tenant.organization_id, can

    def _mine(self, statement, customer_column, read_permission):
        """Only the user's own customers' rows when their read scope is "own"."""
        owner = visible_owner(self.db, self.tenant, read_permission)
        if owner is None:
            return statement
        return statement.where(customer_column.in_(select(Customer.id).where(Customer.organization_id == self.org,
                                                                             Customer.sales_owner_user_id == owner)))

    def build(self, period: Period) -> Dashboard:
        w = window(period)
        board = Dashboard(module="commercial", period=period, start=w.start, end=w.end - timedelta(days=1))
        if self.can(CUSTOMERS_READ):
            self._customers(w, board)
        if self.can(QUOTES_READ):
            self._quotes(w, board)
        if self.can(ORDERS_READ):
            self._orders(w, board)
        if self.can(SAMPLES_READ):
            self._samples(w, board)
        if self.can(FOLLOW_UPS_READ):
            self._follow_ups(w, board)
        board.attention.sort(key=lambda a: ({"danger": 0, "warning": 1, "info": 2}[a.severity], a.date or date.max))
        board.attention_total = len(board.attention)
        board.attention = board.attention[:ATTENTION_LIMIT]
        return board

    def _customers(self, w: Window, board: Dashboard) -> None:
        base = self._mine(select(Customer.created_at, Customer.status, Customer.relationship_stage).where(Customer.organization_id == self.org),
                          Customer.id, CUSTOMERS_READ)
        rows = self.db.execute(base).all()
        board.cards.append(card("new_customers", w, count_by_day(as_day(created) for created, _, _ in rows), href="/customers"))
        board.cards.append(Card(key="active_customers", style="count", href="/customers?status=active",
                                value=Decimal(sum(1 for _, status, _ in rows if status == CustomerStatus.ACTIVE))))
        stages = defaultdict(int)
        for _, status, stage in rows:
            if status == CustomerStatus.ACTIVE:
                stages[stage] += 1
        board.breakdowns.append(breakdown("pipeline", [(s, stages.get(s, 0)) for s in RelationshipStage], style="funnel"))

    def _quotes(self, w: Window, board: Dashboard) -> None:
        rows = self.db.execute(self._mine(select(Quote.issue_date, Quote.status).where(
            Quote.organization_id == self.org, Quote.status != QuoteStatus.DRAFT, Quote.issue_date >= w.at(w.previous_start),
            Quote.issue_date < w.at(w.end)), Quote.customer_id, QUOTES_READ)).all()
        issued = count_by_day(as_day(day) for day, _ in rows)
        accepted = count_by_day(as_day(day) for day, status in rows if status == QuoteStatus.ACCEPTED)
        board.cards.append(card("quotes_issued", w, issued, href="/quotes"))

        def acceptance(first, last):
            decided = [s for d, s in rows if first <= as_day(d) < last and s in (QuoteStatus.ACCEPTED, QuoteStatus.REJECTED)]
            return rate(sum(1 for s in decided if s == QuoteStatus.ACCEPTED), len(decided))
        board.cards.append(Card(key="acceptance_rate", unit="%", style="gauge", href="/quotes?status=accepted",
                                value=acceptance(w.start, w.end), previous=acceptance(w.previous_start, w.start)))
        board.series.append(Series(key="quotes_issued", points=points(w, issued)))
        board.series.append(Series(key="quotes_accepted", points=points(w, accepted)))
        by_status = defaultdict(int)
        for day, status in rows:
            if w.start <= as_day(day) < w.end:
                by_status[status] += 1
        board.breakdowns.append(breakdown("quotes_by_status", list(by_status.items()), style="donut"))
        soon = self.db.execute(self._mine(select(Quote.id, Quote.quote_number, Quote.valid_until, Customer.name)
                                          .join(Customer, Customer.id == Quote.customer_id)
                                          .where(Quote.organization_id == self.org, Quote.status == QuoteStatus.ISSUED,
                                                 Quote.valid_until >= w.at(w.today), Quote.valid_until < w.at(w.today + timedelta(days=EXPIRY_DAYS + 1)))
                                          .order_by(Quote.valid_until), Quote.customer_id, QUOTES_READ)).all()
        for quote_id, number, until, customer in soon:
            board.attention.append(Attention(kind="quote_expiring", id=str(quote_id), label=number, detail=customer, date=as_day(until),
                                             href=f"/quotes/{quote_id}", severity="warning"))

    def _orders(self, w: Window, board: Dashboard) -> None:
        orders = self.db.execute(self._mine(select(CommercialOrder.id, CommercialOrder.confirmed_at, CommercialOrder.currency,
                                                   CommercialOrder.customer_id, Customer.name)
                                            .join(Customer, Customer.id == CommercialOrder.customer_id)
                                            .where(CommercialOrder.organization_id == self.org, CommercialOrder.confirmed_at.is_not(None),
                                                   CommercialOrder.confirmed_at >= w.at(w.previous_start), CommercialOrder.confirmed_at < w.at(w.end)),
                                            CommercialOrder.customer_id, ORDERS_READ)).all()
        values = dict(self.db.execute(select(CommercialOrderItem.commercial_order_id, func.sum(CommercialOrderItem.line_total))
                                      .where(CommercialOrderItem.commercial_order_id.in_([o.id for o in orders]))
                                      .group_by(CommercialOrderItem.commercial_order_id)).all()) if orders else {}
        board.cards.append(card("orders_confirmed", w, count_by_day(as_day(o.confirmed_at) for o in orders), href="/commercial-orders"))
        by_currency, by_customer = defaultdict(lambda: defaultdict(lambda: Decimal(0))), defaultdict(lambda: Decimal(0))
        main = None
        for o in orders:
            value = Decimal(values.get(o.id) or 0)
            if o.currency:
                by_currency[o.currency][as_day(o.confirmed_at)] += value
        for currency in sorted(by_currency, key=lambda c: (c != "SAR", c)):
            board.cards.append(card(f"confirmed_value_{currency.lower()}", w, by_currency[currency], unit=currency, href="/commercial-orders"))
            main = main or currency
        for o in orders:
            if o.currency == main and w.start <= as_day(o.confirmed_at) < w.end:
                by_customer[(o.name, o.customer_id)] += Decimal(values.get(o.id) or 0)
        top = sorted(by_customer.items(), key=lambda kv: kv[1], reverse=True)[:6]
        board.rankings.append(Ranking(key="top_customers", unit=main, items=[
            RankItem(label=name, value=v, href=f"/customers/{customer_id}") for (name, customer_id), v in top]))
        statuses = dict(self.db.execute(self._mine(select(CommercialOrder.status, func.count(CommercialOrder.id))
                                                   .where(CommercialOrder.organization_id == self.org), CommercialOrder.customer_id, ORDERS_READ)
                                        .group_by(CommercialOrder.status)).all())
        board.breakdowns.append(breakdown("orders_by_status", list(statuses.items()), style="donut"))
        stale = self.db.execute(self._mine(select(CommercialOrder.id, CommercialOrder.order_number, CommercialOrder.created_at, Customer.name)
                                           .join(Customer, Customer.id == CommercialOrder.customer_id)
                                           .where(CommercialOrder.organization_id == self.org, CommercialOrder.status == CommercialOrderStatus.DRAFT,
                                                  CommercialOrder.created_at < w.at(w.today - timedelta(days=DRAFT_DAYS)))
                                           .order_by(CommercialOrder.created_at), CommercialOrder.customer_id, ORDERS_READ)).all()
        for order_id, number, created, customer in stale:
            board.attention.append(Attention(kind="draft_order", id=str(order_id), label=number, detail=customer, date=as_day(created),
                                             href=f"/commercial-orders/{order_id}", severity="info"))

    def _samples(self, w: Window, board: Dashboard) -> None:
        rows = self.db.execute(self._mine(select(Sample.id, Sample.request_date, Sample.status, Sample.sample_code, Sample.sample_decision, Customer.name)
                                          .join(Customer, Customer.id == Sample.customer_id).where(Customer.organization_id == self.org),
                                          Sample.customer_id, SAMPLES_READ)).all()
        board.cards.append(card("samples_requested", w, count_by_day(as_day(r.request_date) for r in rows), href="/samples"))
        active = [r for r in rows if r.status != SampleStatus.CANCELLED]
        for key, count in (
            ("samples_accepted", sum(r.sample_decision == SampleDecision.ACCEPTED for r in active)),
            ("samples_rejected", sum(r.sample_decision == SampleDecision.REJECTED for r in active)),
            ("samples_pending_decision", sum(r.sample_decision in (None, SampleDecision.PENDING) for r in active)),
            ("samples_awaiting_evaluation", sum(r.status == SampleStatus.DELIVERED for r in active)),
        ):
            board.cards.append(Card(key=key, style="count", value=Decimal(count), href="/samples"))
        board.breakdowns.append(breakdown("samples_by_status", [(s, sum(1 for r in rows if r.status == s)) for s in SampleStatus
                                                                 if s != SampleStatus.CANCELLED], style="donut"))
        for r in rows:
            if r.status == SampleStatus.DELIVERED:
                board.attention.append(Attention(kind="sample_to_evaluate", id=str(r.id), label=r.sample_code, detail=r.name,
                                                 date=as_day(r.request_date), href=f"/samples/{r.id}", severity="info"))

    def _follow_ups(self, w: Window, board: Dashboard) -> None:
        now = utc_now()
        tomorrow = w.at(now.date() + timedelta(days=1))
        statement = (select(FollowUp.id, FollowUp.due_date, FollowUp.reason, Customer.name)
                     .join(Customer, Customer.id == FollowUp.customer_id)
                     .where(Customer.organization_id == self.org, FollowUp.status.in_((FollowUpStatus.PENDING, FollowUpStatus.IN_PROGRESS)),
                            FollowUp.due_date < now + timedelta(days=7)))
        if visible_owner(self.db, self.tenant, FOLLOW_UPS_READ) is not None:
            statement = statement.where(FollowUp.assigned_user_id == self.tenant.user_id)
        rows = self.db.execute(statement.order_by(FollowUp.due_date)).all()
        for key, count in (
            ("overdue_follow_ups", sum(r.due_date < now for r in rows)),
            ("due_today_follow_ups", sum(now <= r.due_date < tomorrow for r in rows)),
            ("upcoming_follow_ups", sum(tomorrow <= r.due_date < now + timedelta(days=7) for r in rows)),
        ):
            board.cards.append(Card(key=key, style="count", good_when="down", value=Decimal(count), href="/follow-ups?tab=all"))
        for follow_up_id, due, reason, customer in rows:
            if due < tomorrow:
                overdue = due < now
                board.attention.append(Attention(kind="overdue_follow_up" if overdue else "due_follow_up", id=str(follow_up_id),
                    label=customer, detail=(reason or "")[:80], date=as_day(due), href="/follow-ups?tab=all",
                    severity="danger" if overdue else "warning"))
