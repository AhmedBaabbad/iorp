"""Quality rejections (QUAL-001): the single writer of a rejection and its disposition decision.

pending ─decide(disposition)→ decided ─execute→ executed. "hold" is a temporary quarantine (re-decide,
never execute); "use_as_is" records who approved the concession and why. A rejection from a check
takes its order, line, unit and the quantity the check rejected; a manual one names its order.
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.interfaces.order_close_guards import Blocker
from app.core.utils import utc_now
from app.quality.domain import rules
from app.quality.domain.enums import Disposition, DispositionStatus as DS, QualityCheckStatus as S
from app.quality.domain.rules import QualityError, ZERO
from app.quality.infrastructure.models import QualityCheck, QualityDefect, QualityRejection
from .support import log_activity, ProductionReads, as_decimal, history, next_code, record, user_names


class QualityRejectionService:
    def __init__(self, db, tenant):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id
        self.production = ProductionReads(db, self.org)

    # ── reads ──────────────────────────────────────────────────────────────────────────────────
    def _get(self, rejection_id, lock=False) -> QualityRejection:
        query = select(QualityRejection).where(QualityRejection.id == rejection_id, QualityRejection.organization_id == self.org)
        rejection = self.db.scalar(query.with_for_update() if lock else query)
        if rejection is None:
            raise QualityError("QUALITY_REJECTION_NOT_FOUND", 404)
        return rejection

    def get(self, rejection_id):
        return self._get(rejection_id)

    def list(self, *, production_order_id=None, quality_check_id=None, rejection_reason=None, disposition=None, disposition_status=None,
             date_from=None, date_to=None, search=None, limit=200):
        query = select(QualityRejection).where(QualityRejection.organization_id == self.org)
        for column, value in ((QualityRejection.production_order_id, production_order_id), (QualityRejection.quality_check_id, quality_check_id),
                              (QualityRejection.rejection_reason, rejection_reason), (QualityRejection.disposition, disposition),
                              (QualityRejection.disposition_status, disposition_status)):
            if value is not None:
                query = query.where(column == value)
        if date_from:
            query = query.where(QualityRejection.rejection_date >= date_from)
        if date_to:
            query = query.where(QualityRejection.rejection_date <= date_to)
        if search:
            query = query.where(QualityRejection.rejection_code.icontains(search, autoescape=True))
        return list(self.db.scalars(query.order_by(QualityRejection.rejection_date.desc(), QualityRejection.created_at.desc()).limit(limit)))

    def views(self, rejections, can, *, detail=False) -> list[dict]:
        orders = self.production.numbers([r.production_order_id for r in rejections])
        lines = self.production.line_numbers([r.production_order_item_id for r in rejections])
        check_ids = [r.quality_check_id for r in rejections if r.quality_check_id]
        codes = dict(self.db.execute(select(QualityCheck.id, QualityCheck.inspection_code).where(
            QualityCheck.organization_id == self.org, QualityCheck.id.in_(check_ids))).all()) if check_ids else {}
        names = user_names(self.db, self.org, [u for r in rejections for u in (r.rejected_by_user_id, r.decided_by_user_id, r.executed_by_user_id)])
        out = []
        for r in rejections:
            view = dict(order_number=orders.get(r.production_order_id), item_line_no=lines.get(r.production_order_item_id),
                        inspection_code=codes.get(r.quality_check_id), rejected_by_name=names.get(r.rejected_by_user_id),
                        decided_by_name=names.get(r.decided_by_user_id), executed_by_name=names.get(r.executed_by_user_id),
                        unresolved=rules.is_unresolved(r.disposition_status, r.disposition),
                        actions=rules.rejection_actions(r.disposition_status, r.disposition, can))
            if detail:
                view["history"] = history(self.db, self.org, "rejection", r.id)
            out.append(view)
        return out

    def _available_from_check(self, check: QualityCheck, excluding=None):
        query = select(func.coalesce(func.sum(QualityRejection.quantity_rejected), 0)).where(
            QualityRejection.organization_id == self.org, QualityRejection.quality_check_id == check.id)
        if excluding is not None:
            query = query.where(QualityRejection.id != excluding)
        return as_decimal(check.qty_rejected) - as_decimal(self.db.scalar(query))

    # ── writes ─────────────────────────────────────────────────────────────────────────────────
    def create(self, data) -> QualityRejection:
        check = None
        if data.quality_check_id:
            check = self.db.scalar(select(QualityCheck).where(QualityCheck.id == data.quality_check_id, QualityCheck.organization_id == self.org))
            if check is None:
                raise QualityError("QUALITY_CHECK_NOT_FOUND", 404)
            if check.status != S.CLOSED or as_decimal(check.qty_rejected) <= ZERO:
                raise QualityError("CHECK_HAS_NO_REJECTED_QUANTITY")
        order_id = check.production_order_id if check else data.production_order_id
        if not order_id:
            raise QualityError("PRODUCTION_ORDER_REQUIRED", 400)
        order = self.production.order(order_id, lock=True, inspectable=True)
        item_id = check.production_order_item_id if check else data.production_order_item_id
        item = self.production.item(order.id, item_id) if item_id else None
        quantity = as_decimal(data.quantity_rejected)
        rules.assert_rejection_quantity(quantity, self._available_from_check(check) if check else None)
        self._defect(data.quality_defect_id, check)
        if not (data.rejection_notes or "").strip():
            raise QualityError("NOTES_REQUIRED", 400)
        rejection = QualityRejection(
            organization_id=self.org, rejection_code=next_code(self.db, self.org, "QR"), quality_check_id=check.id if check else None,
            quality_defect_id=data.quality_defect_id, production_order_id=order.id, production_order_item_id=item.id if item else None,
            rejection_date=data.rejection_date, rejection_reason=data.rejection_reason, rejection_notes=data.rejection_notes.strip(),
            disposition=None, disposition_status=DS.PENDING, quantity_rejected=quantity,
            unit=(check.unit if check and check.unit else (item.unit if item else order.unit)) or "", rejected_by_user_id=self.tenant.user_id)
        self.db.add(rejection)
        self.db.flush()
        record(self.db, self.org, "rejection", rejection.id, "create", None, DS.PENDING.value, self.tenant.user_id)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "quality_rejection.created", "quality_rejection", rejection.id, rejection.rejection_code)
        return rejection

    def _defect(self, defect_id, check):
        if not defect_id:
            return
        defect = self.db.scalar(select(QualityDefect).where(QualityDefect.id == defect_id, QualityDefect.organization_id == self.org))
        if defect is None or (check is not None and defect.quality_check_id != check.id):
            raise QualityError("DEFECT_NOT_FOUND", 404)

    def update(self, rejection_id, data) -> QualityRejection:
        rejection = self._get(rejection_id, lock=True)
        rules.assert_rejection_editable(rejection.disposition_status)
        values = data.model_dump(exclude_unset=True)
        if "quantity_rejected" in values:
            check = self.db.get(QualityCheck, rejection.quality_check_id) if rejection.quality_check_id else None
            quantity = as_decimal(values["quantity_rejected"])
            rules.assert_rejection_quantity(quantity, self._available_from_check(check, excluding=rejection.id) if check else None)
            rejection.quantity_rejected = quantity
        if "rejection_notes" in values and not (values["rejection_notes"] or "").strip():
            raise QualityError("NOTES_REQUIRED", 400)
        for field in ("rejection_date", "rejection_reason", "rejection_notes"):
            if field in values:
                setattr(rejection, field, values[field].strip() if field == "rejection_notes" else values[field])
        record(self.db, self.org, "rejection", rejection.id, "update", DS.PENDING.value, DS.PENDING.value, self.tenant.user_id,
               detail={k: str(v) for k, v in values.items()})
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "quality_rejection.updated", "quality_rejection", rejection.id, rejection.rejection_code)
        return rejection

    def decide(self, rejection_id, data) -> QualityRejection:
        rejection = self._get(rejection_id, lock=True)
        rules.assert_can_decide(rejection.disposition_status)
        rules.assert_decision(data.disposition, data.concession_approved_by, data.decision_notes)
        before = rejection.disposition_status.value
        rejection.disposition, rejection.disposition_status = data.disposition, DS.DECIDED
        rejection.decision_notes = (data.decision_notes or "").strip() or None
        rejection.concession_approved_by = (data.concession_approved_by or "").strip() or None if data.disposition == Disposition.USE_AS_IS else None
        rejection.decided_at, rejection.decided_by_user_id = utc_now(), self.tenant.user_id
        record(self.db, self.org, "rejection", rejection.id, "decide", before, DS.DECIDED.value, self.tenant.user_id,
               reason=rejection.decision_notes, detail=dict(disposition=data.disposition.value, concession_approved_by=rejection.concession_approved_by))
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "quality_rejection.decided", "quality_rejection", rejection.id, rejection.rejection_code)
        return rejection

    def execute(self, rejection_id, notes=None) -> QualityRejection:
        rejection = self._get(rejection_id, lock=True)
        rules.assert_can_execute(rejection.disposition_status, rejection.disposition)
        rejection.disposition_status, rejection.executed_at, rejection.executed_by_user_id = DS.EXECUTED, utc_now(), self.tenant.user_id
        rejection.execution_notes = (notes or "").strip() or None
        record(self.db, self.org, "rejection", rejection.id, "execute", DS.DECIDED.value, DS.EXECUTED.value, self.tenant.user_id,
               reason=rejection.execution_notes, detail=dict(disposition=rejection.disposition.value))
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "quality_rejection.executed", "quality_rejection", rejection.id, rejection.rejection_code)
        return rejection


def close_blockers(db, organization_id, order_id):
    """Production close gate (registered at the composition root): open checks and undecided or held rejections."""
    open_checks = db.scalar(select(func.count()).select_from(QualityCheck).where(
        QualityCheck.organization_id == organization_id, QualityCheck.production_order_id == order_id,
        QualityCheck.status.in_([S.OPEN, S.UNDER_INSPECTION])))
    rejections = db.execute(select(QualityRejection.disposition_status, QualityRejection.disposition).where(
        QualityRejection.organization_id == organization_id, QualityRejection.production_order_id == order_id,
        QualityRejection.disposition_status != DS.EXECUTED)).all()
    unresolved = sum(1 for status, disposition in rejections if rules.is_unresolved(status, disposition))
    blockers = []
    if open_checks:
        blockers.append(Blocker("QUALITY_CHECKS_OPEN", open_checks))
    if unresolved:
        blockers.append(Blocker("QUALITY_REJECTIONS_UNRESOLVED", unresolved))
    return blockers
