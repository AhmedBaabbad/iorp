"""Numbering, history and reads from other modules for procurement (PROC-001).

User names and quality's non-conformance reports are read through the shared tables (Base.metadata), never by
importing another module's models (ADR-004).
"""
from decimal import Decimal

from sqlalchemy import case, func, select

from app.core.db import Base
from app.core.interfaces.activity_log import get_registered_activity_logger
from app.core.utils import utc_now
from app.procurement.domain import rules
from app.procurement.infrastructure.models import ProcurementCounter, ProcurementEvent, ProcurementSettings


def _t(name):
    return Base.metadata.tables[name]


def user_names(db, organization_id, user_ids) -> dict:
    users = _t("foundation_users")
    ids = [i for i in set(user_ids) if i]
    return dict(db.execute(select(users.c.id, users.c.full_name).where(users.c.organization_id == organization_id, users.c.id.in_(ids))).all()) if ids else {}


def settings(db, organization_id) -> ProcurementSettings:
    current = db.get(ProcurementSettings, organization_id)
    if current is None:
        current = ProcurementSettings(organization_id=organization_id, receipt_prefix=rules.DEFAULT_PREFIX)
        db.add(current)
        db.flush()
    return current


def _next(db, organization_id, kind, year) -> int:
    counter = db.get(ProcurementCounter, (organization_id, kind, year), with_for_update=True)
    if counter is None:
        counter = ProcurementCounter(organization_id=organization_id, kind=kind, year=year, value=0)
        db.add(counter)
    counter.value += 1
    db.flush()
    return counter.value


def next_code(db, organization_id, kind) -> str:
    """SUP-0001, MAT-0001: never restarting, never repeated under concurrency."""
    return rules.code(f"{kind}-", _next(db, organization_id, kind, 0))


def next_receipt_number(db, organization_id) -> str:
    year = utc_now().year
    return rules.number(settings(db, organization_id).receipt_prefix, year, _next(db, organization_id, "GRN", year))


def record(db, organization_id, entity_type, entity_id, action, actor_id, from_status=None, to_status=None, reason=None):
    db.add(ProcurementEvent(organization_id=organization_id, entity_type=entity_type, entity_id=entity_id, action=action,
                            from_status=from_status, to_status=to_status, reason=reason, actor_user_id=actor_id))


def history(db, organization_id, entity_type, entity_id) -> list[dict]:
    rows = list(db.scalars(select(ProcurementEvent).where(ProcurementEvent.organization_id == organization_id, ProcurementEvent.entity_type == entity_type,
                                                          ProcurementEvent.entity_id == entity_id).order_by(ProcurementEvent.occurred_at, ProcurementEvent.id)))
    names = user_names(db, organization_id, [r.actor_user_id for r in rows])
    return [dict(action=r.action, from_status=r.from_status, to_status=r.to_status, reason=r.reason, actor_name=names.get(r.actor_user_id),
                 at=r.occurred_at) for r in rows]


class QualityReads:
    """Quality's non-conformance reports about a supplier (read only)."""

    def __init__(self, db, organization_id):
        self.db, self.org = db, organization_id

    def counts(self, supplier_ids) -> dict:
        """supplier id -> (all reports, open reports)."""
        ids = [i for i in set(supplier_ids) if i]
        if not ids:
            return {}
        reports = _t("non_conformance_reports")
        open_ = func.sum(case((reports.c.status.notin_(("closed", "cancelled")), 1), else_=0))
        rows = self.db.execute(select(reports.c.supplier_id, func.count(), open_).where(reports.c.organization_id == self.org,
                                                                                         reports.c.supplier_id.in_(ids))
                               .group_by(reports.c.supplier_id)).all()
        return {r[0]: (r[1], int(r[2] or 0)) for r in rows}

    def inspections_of(self, line_ids) -> dict:
        """receipt line id -> its incoming inspections (oldest first), read from quality."""
        ids = [i for i in set(line_ids) if i]
        out: dict = {i: [] for i in ids}
        if not ids:
            return out
        checks = _t("quality_checks")
        rows = self.db.execute(select(checks.c.id, checks.c.inspection_code, checks.c.status, checks.c.result, checks.c.receipt_line_id,
                                      checks.c.qty_inspected, checks.c.qty_accepted, checks.c.closed_at)
                               .where(checks.c.organization_id == self.org, checks.c.receipt_line_id.in_(ids)).order_by(checks.c.created_at)).all()
        for r in rows:
            out[r.receipt_line_id].append(dict(id=r.id, inspection_code=r.inspection_code, status=getattr(r.status, "value", r.status),
                                               result=getattr(r.result, "value", r.result), qty_inspected=r.qty_inspected,
                                               qty_accepted=r.qty_accepted, closed_at=r.closed_at))
        return out

    def supplier_period(self, supplier_id, since) -> dict:
        """What quality recorded about a supplier since a date: its decided incoming lots, and its non-conformance reports
        (severity and cost)."""
        checks, reports = _t("quality_checks"), _t("non_conformance_reports")
        receipts = _t("procurement_receipts")
        lots = self.db.execute(select(checks.c.qty_inspected, checks.c.qty_accepted).join(receipts, receipts.c.id == checks.c.receipt_id)
                               .where(checks.c.organization_id == self.org, receipts.c.supplier_id == supplier_id,
                                      checks.c.status == "closed", checks.c.closed_at >= since)).all()
        costs = (reports.c.cost_material, reports.c.cost_labor, reports.c.cost_scrap, reports.c.cost_transport, reports.c.cost_other)
        ncrs = self.db.execute(select(reports.c.severity, *costs).where(reports.c.organization_id == self.org, reports.c.supplier_id == supplier_id,
                                                                         reports.c.status != "cancelled", reports.c.report_date >= since.date())).all()
        return dict(lots=[(r.qty_inspected, r.qty_accepted) for r in lots], severities=[r.severity for r in ncrs],
                    cost=sum((v for r in ncrs for v in r[1:] if v is not None), Decimal("0")))

    def of_supplier(self, supplier_id, limit=50) -> list[dict]:
        reports = _t("non_conformance_reports")
        rows = self.db.execute(select(reports.c.id, reports.c.report_number, reports.c.report_date, reports.c.title, reports.c.status,
                                      reports.c.severity, reports.c.reference_code)
                               .where(reports.c.organization_id == self.org, reports.c.supplier_id == supplier_id)
                               .order_by(reports.c.report_date.desc(), reports.c.report_number.desc()).limit(limit)).all()
        return [dict(r._mapping) for r in rows]


def log_activity(db, organization_id, actor_id, action, entity_type, entity_id, name):
    """The tenant activity log (best effort, after the business commit), like the other modules."""
    try:
        get_registered_activity_logger().log_activity(db, organization_id, action, entity_type, entity_id, name, actor_id)
        db.commit()
    except Exception:  # noqa: BLE001 - logging never fails the business action
        db.rollback()
