"""Quality checks (QUAL-001): the single writer of an inspection and its lifecycle.

open ─start→ under_inspection ─close(result, quantities)→ closed, or ─cancel(reason)→ cancelled.
A check on a production order needs the order running, held or completed, and locks it like production
does. Closing with a rejected quantity opens a rejection awaiting a decision, in the same transaction.
An inspection of returned goods (QUAL-RET-001, return_inspection_service.py) is closed by its return decision instead.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.utils import utc_now
from app.quality.domain import rules
from app.quality.domain.permissions import NCR_CREATE, REJECTIONS_DECIDE
from app.quality.domain.enums import DispositionStatus, QualityCheckStatus as S, QualityCheckType as T, RejectionReason
from app.quality.domain.rules import QualityError, ZERO
from app.quality.infrastructure.models import QualityCheck, QualityRejection
from .measurement_service import MeasurementService
from .support import log_activity, CommercialReads, ProcurementReads, ProductionReads, ShippingReads, as_decimal, history, next_code, record, user_names

# Types inspecting a production lot: the production order is required.
ORDER_TYPES = frozenset({T.IN_PROCESS_INSPECTION, T.FINISHED_PRODUCT_INSPECTION, T.REINSPECTION})


class QualityCheckService:
    def __init__(self, db, tenant):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id
        self.production, self.commercial = ProductionReads(db, self.org), CommercialReads(db, self.org)

    # ── reads ──────────────────────────────────────────────────────────────────────────────────
    def _get(self, check_id, lock=False) -> QualityCheck:
        query = select(QualityCheck).where(QualityCheck.id == check_id, QualityCheck.organization_id == self.org)
        check = self.db.scalar(query.with_for_update() if lock else query)
        if check is None:
            raise QualityError("QUALITY_CHECK_NOT_FOUND", 404)
        return check

    def list(self, *, production_order_id=None, check_type=None, status=None, result=None, date_from=None, date_to=None, search=None, limit=200):
        query = select(QualityCheck).where(QualityCheck.organization_id == self.org)
        for column, value in ((QualityCheck.production_order_id, production_order_id), (QualityCheck.check_type, check_type),
                              (QualityCheck.status, status), (QualityCheck.result, result)):
            if value is not None:
                query = query.where(column == value)
        if date_from:
            query = query.where(QualityCheck.check_datetime >= date_from)
        if date_to:
            query = query.where(QualityCheck.check_datetime <= date_to)
        if search:
            query = query.where(QualityCheck.inspection_code.icontains(search, autoescape=True))
        return list(self.db.scalars(query.order_by(QualityCheck.check_datetime.desc(), QualityCheck.id).limit(limit)))

    def views(self, checks, can, *, detail=False) -> list[dict]:
        orders = self.production.numbers([c.production_order_id for c in checks])
        lines = self.production.line_numbers([c.production_order_item_id for c in checks])
        samples = self.commercial.sample_codes([c.sample_id for c in checks])
        names = user_names(self.db, self.org, [c.checked_by_user_id for c in checks] + [c.closed_by_user_id for c in checks])
        returned = ShippingReads(self.db, self.org).refs([c.return_line_id for c in checks])
        received = ProcurementReads(self.db, self.org).lots([c.receipt_line_id for c in checks])
        out = []
        for c in checks:
            actions = rules.check_actions(c.status, can)
            source = returned.get(c.return_line_id)
            if c.return_line_id:  # returned goods are closed by their return decision
                actions = ["return_decision" if a == "close" else a for a in actions if a != "close" or can(REJECTIONS_DECIDE)]
            if c.receipt_line_id:  # a received lot is closed by its lot decision (QUAL-INC-001)
                actions = ["lot_decision" if a == "close" else a for a in actions if a != "close" or can(NCR_CREATE)]
            lot = received.get(c.receipt_line_id)
            view = dict(order_number=orders.get(c.production_order_id), item_line_no=lines.get(c.production_order_item_id),
                        sample_code=samples.get(c.sample_id), checked_by_name=names.get(c.checked_by_user_id),
                        closed_by_name=names.get(c.closed_by_user_id), actions=actions,
                        return_source=dict(return_id=source["return_id"], return_no=source["return_no"], kind=source["kind"],
                                           reason=source["reason"], responsibility=source["responsibility"], details=source["details"],
                                           shipment_id=source["shipment_id"], shipment_no=source["shipment_no"],
                                           customer_name=source["customer_name"], line_no=source["line_no"], description=source["description"],
                                           production_order_no=source["production_order_no"]) if source else None,
                        incoming_source=dict(receipt_id=lot["receipt_id"], receipt_no=lot["receipt_no"], receipt_date=lot["receipt_date"],
                                             supplier_id=lot["supplier_id"], supplier_name=lot["supplier_name"], line_no=lot["line_no"],
                                             description=lot["description"], material_code=lot["material_code"], supplier_lot=lot["supplier_lot"],
                                             spec_product_type=lot["spec_product_type"]) if lot else None)
            if detail:
                view["history"] = history(self.db, self.org, "check", c.id)
                view["measurements"] = MeasurementService(self.db, self.tenant).measurements(c.id)
                view["rejections"] = [dict(id=r.id, rejection_code=r.rejection_code, disposition_status=r.disposition_status,
                                           disposition=r.disposition, quantity_rejected=r.quantity_rejected, unit=r.unit)
                                      for r in self.db.scalars(select(QualityRejection).where(QualityRejection.organization_id == self.org,
                                                               QualityRejection.quality_check_id == c.id).order_by(QualityRejection.created_at))]
            out.append(view)
        return out

    def get(self, check_id) -> QualityCheck:
        return self._get(check_id)

    def inspectable_orders(self, search="", check_type=None):
        return self.production.inspectable_orders(search, statuses=rules.order_statuses(check_type) if check_type else rules.ORDER_STATUSES)

    def samples(self, search=""):
        return self.commercial.samples(search)

    # ── writes ─────────────────────────────────────────────────────────────────────────────────
    def _context(self, check_type, order_id, item_id, sample_id, *, lock=True):
        """Validate the inspected object; return (order, item, unit). Locks the order (production's close lock)."""
        if T(check_type) == T.SAMPLE_INSPECTION:
            if not sample_id:
                raise QualityError("SAMPLE_REQUIRED", 400)
            sample = self.commercial.sample(sample_id)
            return None, None, sample["unit"]
        if T(check_type) in ORDER_TYPES and not order_id:
            raise QualityError("PRODUCTION_ORDER_REQUIRED", 400)
        if not order_id:
            if item_id:
                raise QualityError("PRODUCTION_ORDER_REQUIRED", 400)
            return None, None, None
        order = self.production.order(order_id, lock=lock, inspectable=True, statuses=rules.order_statuses(check_type))
        item = self.production.item(order.id, item_id) if item_id else None
        return order, item, (item.unit if item else order.unit)

    def create(self, data) -> QualityCheck:
        order, item, unit = self._context(data.check_type, data.production_order_id, data.production_order_item_id, data.sample_id)
        inspected = as_decimal(data.qty_inspected)
        if inspected < ZERO:
            raise QualityError("QUANTITY_NEGATIVE", 400)
        check = QualityCheck(
            organization_id=self.org, inspection_code=next_code(self.db, self.org, "QI"), check_type=data.check_type,
            check_datetime=data.check_datetime, status=S.OPEN, result=None,
            production_order_id=order.id if order else None, production_order_item_id=item.id if item else None,
            sample_id=data.sample_id if T(data.check_type) == T.SAMPLE_INSPECTION else None, unit=unit,
            qty_inspected=inspected, qty_accepted=ZERO, qty_rejected=ZERO, notes=data.notes, checked_by_user_id=self.tenant.user_id)
        self.db.add(check)
        self.db.flush()
        record(self.db, self.org, "check", check.id, "create", None, S.OPEN.value, self.tenant.user_id)
        # QUAL-SPEC-001: the product's specification in force becomes the measurement plan, when there is exactly one.
        MeasurementService(self.db, self.tenant).auto_apply(check)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "quality_check.created", "quality_check", check.id, check.inspection_code)
        return check

    def update(self, check_id, data) -> QualityCheck:
        check = self._get(check_id, lock=True)
        rules.assert_editable(check.status)
        values = data.model_dump(exclude_unset=True)
        check_type = values.get("check_type", check.check_type)
        if {"check_type", "production_order_item_id", "sample_id"} & values.keys():
            order, item, unit = self._context(check_type, check.production_order_id, values.get("production_order_item_id", check.production_order_item_id),
                                              values.get("sample_id", check.sample_id))
            check.production_order_item_id, check.unit = (item.id if item else None), unit
            check.sample_id = values.get("sample_id", check.sample_id) if T(check_type) == T.SAMPLE_INSPECTION else None
        for field in ("check_type", "check_datetime", "notes"):
            if field in values:
                setattr(check, field, values[field])
        if "qty_inspected" in values:
            if as_decimal(values["qty_inspected"]) < ZERO:
                raise QualityError("QUANTITY_NEGATIVE", 400)
            check.qty_inspected = as_decimal(values["qty_inspected"])
        record(self.db, self.org, "check", check.id, "update", check.status.value, check.status.value, self.tenant.user_id,
               detail={k: str(v) for k, v in values.items()})
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "quality_check.updated", "quality_check", check.id, check.inspection_code)
        return check

    def start(self, check_id) -> QualityCheck:
        check = self._get(check_id, lock=True)
        rules.assert_can_start(check.status)
        check.status, check.started_at = S.UNDER_INSPECTION, utc_now()
        record(self.db, self.org, "check", check.id, "start", S.OPEN.value, S.UNDER_INSPECTION.value, self.tenant.user_id)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "quality_check.started", "quality_check", check.id, check.inspection_code)
        return check

    def close(self, check_id, data) -> QualityCheck:
        check = self._get(check_id, lock=True)
        rules.assert_can_finish(check.status)
        if check.return_line_id:
            raise QualityError("RETURN_INSPECTION_NEEDS_DECISION")
        if check.receipt_line_id:
            raise QualityError("INCOMING_INSPECTION_NEEDS_DECISION")
        if check.production_order_id:
            self.production.order(check.production_order_id, lock=True)  # serialize with the order's close
        inspected, accepted, rejected = as_decimal(data.qty_inspected), as_decimal(data.qty_accepted), as_decimal(data.qty_rejected)
        rules.assert_quantities(inspected, accepted, rejected)
        rules.assert_result_matches(data.result, rejected)
        MeasurementService(self.db, self.tenant).assert_complete(check, data.result)
        before = check.status.value
        check.qty_inspected, check.qty_accepted, check.qty_rejected = inspected, accepted, rejected
        check.result, check.status, check.closed_at, check.closed_by_user_id = data.result, S.CLOSED, utc_now(), self.tenant.user_id
        if data.notes is not None:
            check.notes = data.notes
        record(self.db, self.org, "check", check.id, "close", before, S.CLOSED.value, self.tenant.user_id,
               detail=dict(result=data.result.value, inspected=str(inspected), accepted=str(accepted), rejected=str(rejected)))
        if rejected > ZERO:
            # The rejected quantity awaits a disposition decision; nothing to type again.
            rejection = QualityRejection(
                organization_id=self.org, rejection_code=next_code(self.db, self.org, "QR"), quality_check_id=check.id,
                production_order_id=check.production_order_id, production_order_item_id=check.production_order_item_id,
                rejection_date=utc_now().date(), rejection_reason=data.rejection_reason or RejectionReason.FAILED_QUALITY_CHECK,
                rejection_notes=(data.notes or "").strip() or check.inspection_code, disposition=None,
                disposition_status=DispositionStatus.PENDING, quantity_rejected=rejected, unit=check.unit or "",
                rejected_by_user_id=self.tenant.user_id)
            self.db.add(rejection)
            self.db.flush()
            record(self.db, self.org, "rejection", rejection.id, "create", None, DispositionStatus.PENDING.value, self.tenant.user_id,
                   detail=dict(source=check.inspection_code))
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "quality_check.closed", "quality_check", check.id, check.inspection_code)
        return check

    def cancel(self, check_id, reason) -> QualityCheck:
        check = self._get(check_id, lock=True)
        rules.assert_can_finish(check.status)
        if not (reason or "").strip():
            raise QualityError("REASON_REQUIRED", 400)
        before = check.status.value
        check.status, check.cancel_reason, check.closed_at, check.closed_by_user_id = S.CANCELLED, reason.strip(), utc_now(), self.tenant.user_id
        record(self.db, self.org, "check", check.id, "cancel", before, S.CANCELLED.value, self.tenant.user_id, reason=reason.strip())
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "quality_check.cancelled", "quality_check", check.id, check.inspection_code)
        return check
