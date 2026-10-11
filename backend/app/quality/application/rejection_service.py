"""Quality rejections (QUAL-001): the single writer of a rejection and its disposition decision.

pending ─decide(disposition)→ decided ─execute→ executed. "hold" is a temporary quarantine (re-decide,
never execute); "use_as_is" records who approved the concession and why. A rejection from a check
takes its order, line, unit and the quantity the check rejected; a manual one names its order.
"""
from __future__ import annotations

from sqlalchemy import and_, func, or_, select

from app.core.pagination import paginate
from app.core.interfaces.order_close_guards import Blocker
from app.core.utils import utc_now
from app.quality.domain import rules
from app.quality.domain.enums import Disposition, DispositionStatus as DS, QualityCheckStatus as S
from app.quality.domain.rules import QualityError, ZERO
from app.quality.infrastructure.models import QualityCheck, QualityDefect, QualityRejection, QualityRejectionDefect
from .support import log_activity, ProductionReads, ShippingReads, as_decimal, history, next_code, record, user_names


class _Pick:
    """A rejection's current defect link, in the shape of a request item."""
    def __init__(self, quality_defect_id, affected_quantity):
        self.quality_defect_id, self.affected_quantity = quality_defect_id, affected_quantity


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

    def list(self, params, *, production_order_id=None, quality_check_id=None, rejection_reason=None, disposition=None, disposition_status=None,
             date_from=None, date_to=None, search=None, unresolved=None):
        """One page of rejections, newest first, and the total matching the filters (ARCH-PAGE-001)."""
        query = select(QualityRejection).where(QualityRejection.organization_id == self.org)
        if unresolved:
            # The same rule as rules.is_unresolved: no decision yet, or only a hold (they keep the order from closing).
            query = query.where(or_(QualityRejection.disposition_status == DS.PENDING,
                                    and_(QualityRejection.disposition_status == DS.DECIDED, QualityRejection.disposition == Disposition.HOLD)))
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
        return paginate(self.db, query.order_by(QualityRejection.rejection_date.desc(), QualityRejection.created_at.desc(), QualityRejection.id.desc()), params)

    def views(self, rejections, can, *, detail=False) -> list[dict]:
        orders = self.production.numbers([r.production_order_id for r in rejections])
        lines = self.production.line_numbers([r.production_order_item_id for r in rejections])
        check_ids = [r.quality_check_id for r in rejections if r.quality_check_id]
        codes = dict(self.db.execute(select(QualityCheck.id, QualityCheck.inspection_code).where(
            QualityCheck.organization_id == self.org, QualityCheck.id.in_(check_ids))).all()) if check_ids else {}
        names = user_names(self.db, self.org, [u for r in rejections for u in (r.rejected_by_user_id, r.decided_by_user_id, r.executed_by_user_id)])
        returns = ShippingReads(self.db, self.org).return_numbers([r.return_id for r in rejections])
        out = []
        for r in rejections:
            defects = [dict(quality_defect_id=link.quality_defect_id, defect_category=link.defect.defect_category.value,
                            severity=link.defect.severity.value, defect_count=link.defect.defect_count, description=link.defect.description,
                            affected_quantity=link.affected_quantity) for link in r.defect_links]
            view = dict(order_number=orders.get(r.production_order_id), item_line_no=lines.get(r.production_order_item_id),
                        defects=defects, severity=rules.highest_severity(d["severity"] for d in defects),
                        return_no=returns.get(r.return_id),
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
        defects = self._defects(data.defects, check, quantity)
        if not (data.rejection_notes or "").strip():
            raise QualityError("NOTES_REQUIRED", 400)
        rejection = QualityRejection(
            organization_id=self.org, rejection_code=next_code(self.db, self.org, "QR"), quality_check_id=check.id if check else None,
            production_order_id=order.id, production_order_item_id=item.id if item else None,
            rejection_date=data.rejection_date, rejection_reason=data.rejection_reason, rejection_notes=data.rejection_notes.strip(),
            disposition=None, disposition_status=DS.PENDING, quantity_rejected=quantity,
            unit=(check.unit if check and check.unit else (item.unit if item else order.unit)) or "", rejected_by_user_id=self.tenant.user_id)
        self.db.add(rejection)
        self.db.flush()
        self._link(rejection, defects)
        record(self.db, self.org, "rejection", rejection.id, "create", None, DS.PENDING.value, self.tenant.user_id,
               detail=dict(defects=",".join(str(d.id) for d, _ in defects)) if defects else None)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "quality_rejection.created", "quality_rejection", rejection.id, rejection.rejection_code)
        return rejection

    def _defects(self, items, check, quantity):
        """The (defect, affected quantity) pairs a rejection is made for: defects of this organization and, for a rejection
        from an inspection, of that inspection; each named once; an affected quantity at most the rejected quantity.
        Defects have no catalog or inactive state: they are the findings recorded on the inspection."""
        ids = [item.quality_defect_id for item in items]
        if len(ids) != len(set(ids)):
            raise QualityError("REJECTION_DEFECT_DUPLICATE", 422)
        if not ids:
            return []
        if check is None:
            raise QualityError("DEFECTS_NEED_A_CHECK", 422)
        found = {d.id: d for d in self.db.scalars(select(QualityDefect).where(
            QualityDefect.organization_id == self.org, QualityDefect.quality_check_id == check.id, QualityDefect.id.in_(ids)))}
        pairs = []
        for item in items:
            defect = found.get(item.quality_defect_id)
            if defect is None:
                raise QualityError("DEFECT_NOT_FOUND", 404, quality_defect_id=str(item.quality_defect_id))
            affected = as_decimal(item.affected_quantity) if item.affected_quantity is not None else None
            if affected is not None and affected > quantity:
                raise QualityError("AFFECTED_QUANTITY_EXCEEDS_REJECTED", 422, quality_defect_id=str(defect.id))
            pairs.append((defect, affected))
        return pairs

    def _link(self, rejection, pairs):
        rejection.defect_links.clear()
        self.db.flush()
        for defect, affected in pairs:
            rejection.defect_links.append(QualityRejectionDefect(organization_id=self.org, quality_defect_id=defect.id,
                                                                 affected_quantity=affected))
        self.db.flush()

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
        if data.defects is not None or "quantity_rejected" in values:
            check = self.db.get(QualityCheck, rejection.quality_check_id) if rejection.quality_check_id else None
            current = [_Pick(link.quality_defect_id, link.affected_quantity) for link in rejection.defect_links]
            pairs = self._defects(data.defects if data.defects is not None else current, check, as_decimal(rejection.quantity_rejected))
            if data.defects is not None:
                self._link(rejection, pairs)
        values.pop("defects", None)
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
    """Production close gate (registered at the composition root): open checks and undecided or held rejections.
    Inspections of returned goods and their rejections never block it (QUAL-RET-001)."""
    open_checks = db.scalar(select(func.count()).select_from(QualityCheck).where(
        QualityCheck.organization_id == organization_id, QualityCheck.production_order_id == order_id,
        QualityCheck.return_line_id.is_(None), QualityCheck.status.in_([S.OPEN, S.UNDER_INSPECTION])))
    rejections = db.execute(select(QualityRejection.disposition_status, QualityRejection.disposition).where(
        QualityRejection.organization_id == organization_id, QualityRejection.production_order_id == order_id,
        QualityRejection.return_id.is_(None), QualityRejection.disposition_status != DS.EXECUTED)).all()
    unresolved = sum(1 for status, disposition in rejections if rules.is_unresolved(status, disposition))
    blockers = []
    if open_checks:
        blockers.append(Blocker("QUALITY_CHECKS_OPEN", open_checks))
    if unresolved:
        blockers.append(Blocker("QUALITY_REJECTIONS_UNRESOLVED", unresolved))
    return blockers
