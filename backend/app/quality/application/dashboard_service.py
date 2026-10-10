"""The quality dashboard (DASH-001): what was inspected and how much passed, what was rejected and why, the
non-conformances and their corrective actions, the certificates issued, and what waits for a quality decision.

Figures come from quality's own tables only.

  checks_closed      inspections closed with a result in the period
  acceptance_rate    accepted or conditionally accepted inspections / closed inspections, in % (never mixed quantities)
  defects            defects recorded in the period (their count)
  certificates       certificates of analysis issued in the period
  open_checks, pending_rejections, open_ncrs, overdue_actions   what stands open now
"""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dashboard import (
    Attention, Card, Dashboard, Period, Series, Window, as_day, breakdown, card, count_by_day, points, rate, tally, window,
)
from app.quality.domain import ncr as N
from app.quality.domain import permissions as Q
from app.quality.domain.enums import DispositionStatus, QualityCheckResult, QualityCheckStatus
from app.quality.infrastructure.models import (
    NCRAction, NonConformanceReport, QualityCertificate, QualityCheck, QualityDefect, QualityRejection,
)

ZERO = Decimal(0)
ATTENTION_LIMIT = 10
PASSING = (QualityCheckResult.ACCEPTED, QualityCheckResult.CONDITIONAL_ACCEPT)


class QualityDashboard:
    def __init__(self, db: Session, organization_id, can) -> None:
        self.db, self.org, self.can = db, organization_id, can

    def build(self, period: Period) -> Dashboard:
        w = window(period)
        board = Dashboard(module="quality", period=period, start=w.start, end=w.end - timedelta(days=1))
        if self.can(Q.CHECKS_READ):
            self._checks(w, board)
        if self.can(Q.DEFECTS_READ):
            self._defects(w, board)
        if self.can(Q.REJECTIONS_READ):
            self._rejections(w, board)
        if self.can(Q.NCR_READ):
            self._ncrs(w, board)
        if self.can(Q.COA_READ):
            self._certificates(w, board)
        board.attention.sort(key=lambda a: ({"danger": 0, "warning": 1, "info": 2}[a.severity], a.date or date.max))
        board.attention_total = len(board.attention)
        board.attention = board.attention[:ATTENTION_LIMIT]
        return board

    # ── inspections ───────────────────────────────────────────────────────────────────────────────────────────
    def _checks(self, w: Window, board: Dashboard) -> None:
        rows = self.db.execute(select(QualityCheck.closed_at, QualityCheck.result, QualityCheck.qty_inspected, QualityCheck.qty_accepted,
                                      QualityCheck.check_type)
                               .where(QualityCheck.organization_id == self.org, QualityCheck.status == QualityCheckStatus.CLOSED,
                                      QualityCheck.closed_at >= w.at(w.previous_start), QualityCheck.closed_at < w.at(w.end))).all()
        closed, passed, failed = defaultdict(int), defaultdict(int), defaultdict(int)
        inspected, accepted = defaultdict(lambda: ZERO), defaultdict(lambda: ZERO)
        by_result, by_type = defaultdict(int), defaultdict(int)
        for closed_at, result, qty_inspected, qty_accepted, check_type in rows:
            day = as_day(closed_at)
            closed[day] += 1
            (passed if result in PASSING else failed)[day] += 1
            inspected[day] += Decimal(qty_inspected or 0)
            accepted[day] += Decimal(qty_accepted or 0)
            if w.start <= day < w.end:
                by_result[result] += 1
                by_type[check_type] += 1
        board.cards.append(card("checks_closed", w, closed, href="/quality-checks"))
        i_now, i_before, i_today = tally(w, closed)
        a_now, a_before, a_today = tally(w, passed)
        board.cards.append(Card(key="acceptance_rate", unit="%", style="gauge", target=Decimal(98), href="/quality-checks",
                                value=rate(a_now, i_now), previous=rate(a_before, i_before), today=rate(a_today, i_today)))
        board.series.append(Series(key="passed", points=points(w, passed)))
        board.series.append(Series(key="failed", points=points(w, failed)))
        board.breakdowns.append(breakdown("checks_by_result", list(by_result.items()), style="donut"))
        board.breakdowns.append(breakdown("checks_by_type", list(by_type.items())))
        open_rows = self.db.execute(select(QualityCheck.id, QualityCheck.inspection_code, QualityCheck.status, QualityCheck.check_datetime)
                                    .where(QualityCheck.organization_id == self.org,
                                           QualityCheck.status.in_((QualityCheckStatus.OPEN, QualityCheckStatus.UNDER_INSPECTION)))
                                    .order_by(QualityCheck.check_datetime)).all()
        board.cards.append(Card(key="open_checks", style="count", value=Decimal(len(open_rows)), href="/quality-checks"))
        for check_id, code, status, when in open_rows:
            if as_day(when) < w.today - timedelta(days=2):  # waiting more than two days
                board.attention.append(Attention(kind="waiting_check", id=str(check_id), label=code, detail=getattr(status, "value", status),
                                                 date=as_day(when), href=f"/quality-checks/{check_id}", severity="warning"))

    def _defects(self, w: Window, board: Dashboard) -> None:
        rows = self.db.execute(select(QualityDefect.defect_date, QualityDefect.defect_category, QualityDefect.defect_count)
                               .where(QualityDefect.organization_id == self.org, QualityDefect.defect_date >= w.previous_start,
                                      QualityDefect.defect_date < w.end)).all()
        by_day, by_category = defaultdict(int), defaultdict(int)
        for day, category, count in rows:
            by_day[day] += count or 1
            if w.start <= day < w.end:
                by_category[category] += count or 1
        board.cards.append(card("defects", w, by_day, good_when="down", href="/quality-checks"))
        board.breakdowns.append(breakdown("defects_by_category", list(by_category.items()), limit=8))

    def _rejections(self, w: Window, board: Dashboard) -> None:
        rows = self.db.execute(select(QualityRejection.rejection_date, QualityRejection.rejection_reason)
                               .where(QualityRejection.organization_id == self.org, QualityRejection.rejection_date >= w.start,
                                      QualityRejection.rejection_date < w.end)).all()
        by_reason = defaultdict(int)
        for _, reason in rows:
            by_reason[reason] += 1
        board.breakdowns.append(breakdown("rejections_by_reason", list(by_reason.items()), limit=8))
        pending = self.db.execute(select(QualityRejection.id, QualityRejection.rejection_code, QualityRejection.rejection_date,
                                         QualityRejection.quantity_rejected)
                                  .where(QualityRejection.organization_id == self.org,
                                         QualityRejection.disposition_status == DispositionStatus.PENDING)
                                  .order_by(QualityRejection.rejection_date)).all()
        board.cards.append(Card(key="pending_rejections", style="count", good_when="down", value=Decimal(len(pending)), href="/quality-rejections"))
        for rejection_id, code, day, quantity in pending:
            board.attention.append(Attention(kind="pending_rejection", id=str(rejection_id), label=code, detail=str(Decimal(quantity).normalize()),
                                             date=day, href=f"/quality-rejections/{rejection_id}", severity="danger"))

    # ── non-conformances and corrective actions ───────────────────────────────────────────────────────────────
    def _ncrs(self, w: Window, board: Dashboard) -> None:
        statuses = dict(self.db.execute(select(NonConformanceReport.status, func.count(NonConformanceReport.id))
                                        .where(NonConformanceReport.organization_id == self.org,
                                               NonConformanceReport.status.notin_(tuple(N.FINAL)))
                                        .group_by(NonConformanceReport.status)).all())
        board.cards.append(Card(key="open_ncrs", style="count", good_when="down", value=Decimal(sum(statuses.values())), href="/non-conformance-reports"))
        board.breakdowns.append(breakdown("ncrs_by_stage", [(s, statuses.get(s, 0)) for s in N.STATUSES if s not in N.FINAL], style="funnel"))
        opened = self.db.execute(select(NonConformanceReport.report_date).where(
            NonConformanceReport.organization_id == self.org, NonConformanceReport.report_date >= w.previous_start,
            NonConformanceReport.report_date < w.end)).scalars().all()
        board.cards.append(card("ncrs_opened", w, count_by_day(opened), good_when="down", href="/non-conformance-reports"))
        waiting = self.db.execute(select(NonConformanceReport.id, NonConformanceReport.report_number, NonConformanceReport.report_date)
                                  .where(NonConformanceReport.organization_id == self.org, NonConformanceReport.status == N.VERIFICATION)
                                  .order_by(NonConformanceReport.report_date)).all()
        for report_id, number, day in waiting:
            board.attention.append(Attention(kind="ncr_to_verify", id=str(report_id), label=number, date=day,
                                             href=f"/non-conformance-reports/{report_id}", severity="warning"))
        late = self.db.execute(select(NCRAction.ncr_id, NonConformanceReport.report_number, NCRAction.description, NCRAction.due_date)
                               .join(NonConformanceReport, NonConformanceReport.id == NCRAction.ncr_id)
                               .where(NCRAction.organization_id == self.org, NCRAction.status == N.ACTION_OPEN, NCRAction.due_date < w.today)
                               .order_by(NCRAction.due_date)).all()
        board.cards.append(Card(key="overdue_actions", style="count", good_when="down", value=Decimal(len(late)), href="/corrective-actions"))
        for report_id, number, description, due in late:
            board.attention.append(Attention(kind="overdue_action", id=str(report_id), label=number, detail=description[:80], date=due,
                                             href=f"/non-conformance-reports/{report_id}", severity="danger"))

    def _certificates(self, w: Window, board: Dashboard) -> None:
        issued = self.db.execute(select(QualityCertificate.issued_at).where(
            QualityCertificate.organization_id == self.org, QualityCertificate.status == "issued",
            QualityCertificate.issued_at >= w.at(w.previous_start), QualityCertificate.issued_at < w.at(w.end))).scalars().all()
        board.cards.append(card("certificates", w, count_by_day(as_day(at) for at in issued), href="/quality-certificates"))
        drafts = self.db.execute(select(QualityCertificate.id, QualityCertificate.customer_name, QualityCertificate.created_at)
                                 .where(QualityCertificate.organization_id == self.org, QualityCertificate.status == "draft")
                                 .order_by(QualityCertificate.created_at)).all()
        for certificate_id, customer, created in drafts:
            board.attention.append(Attention(kind="draft_certificate", id=str(certificate_id), label=customer or "—", date=as_day(created),
                                             href=f"/quality-certificates/{certificate_id}", severity="info"))
