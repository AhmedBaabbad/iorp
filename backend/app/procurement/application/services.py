"""Procurement services (PROC-001): the single writers of suppliers, materials and goods receipts.

Every write records the procurement history and the activity log. A supplier's record shows its receipts and the
non-conformance reports quality raised about it (read from quality's tables).
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.core.interfaces import approvals
from app.core.units import to_kilograms
from app.core.utils import utc_now
from app.core.interfaces.product_catalog import unknown_product_types
from app.core.interfaces.reference_lists import unknown_list_values
from app.procurement.domain import permissions as P
from app.procurement.domain import purchase_orders as PO
from app.procurement.domain import rules
from app.procurement.domain.rules import ProcurementError
from app.procurement.infrastructure.models import GoodsReceipt, GoodsReceiptLine, Material, PurchaseOrder, Supplier
from .purchase_order_service import PurchaseOrderService, by_line_owner
from .support import QualityReads, history, log_activity, next_code, next_receipt_number, record, settings, user_names
from . import notices

SUPPLIER_FIELDS = ("name", "category", "supplies", "contact_name", "email", "address", "city", "city_other", "country", "vat_number", "cr_number", "notes")
MATERIAL_FIELDS = ("name", "category", "unit", "inspection_required", "spec_product_type", "active", "notes")
RECEIPT_FIELDS = ("driver_id", "vehicle_id", "driver_affiliation", "receipt_date", "supplier_delivery_no", "supplier_invoice_no", "purchase_reference", "vehicle_plate", "driver_name", "notes")
LINE_FIELDS = ("material_id", "description", "supplier_lot", "quantity", "unit", "package_count", "weight", "weight_unit", "notes", "po_line_id")


def _set(target, values, fields, required=()):
    for field in fields:
        if field in values and not (field in required and values[field] is None):
            setattr(target, field, values[field])


class SupplierService:
    def __init__(self, db, tenant):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id

    def _get(self, supplier_id, lock=False) -> Supplier:
        query = select(Supplier).where(Supplier.id == supplier_id, Supplier.organization_id == self.org)
        found = self.db.scalar(query.with_for_update() if lock else query)
        if found is None:
            raise ProcurementError("SUPPLIER_NOT_FOUND", 404)
        return found

    def get(self, supplier_id) -> Supplier:
        return self._get(supplier_id)

    def list(self, status=None, category=None, search=None, usable=False, limit=500):
        query = select(Supplier).where(Supplier.organization_id == self.org)
        if status:
            query = query.where(Supplier.status == status)
        if category:
            query = query.where(Supplier.category == category)
        if usable:
            query = query.where(Supplier.status != rules.BLOCKED)
        if search:
            like = lambda column: column.icontains(search, autoescape=True)  # noqa: E731
            query = query.where(or_(like(Supplier.name), like(Supplier.supplier_code), like(Supplier.supplies)))
        return list(self.db.scalars(query.order_by(Supplier.name).limit(limit)))

    def views(self, suppliers, can, detail=False) -> list[dict]:
        ids = [s.id for s in suppliers]
        receipts = dict(self.db.execute(select(GoodsReceipt.supplier_id, func.count()).where(
            GoodsReceipt.organization_id == self.org, GoodsReceipt.supplier_id.in_(ids), GoodsReceipt.status == rules.RECEIVED)
            .group_by(GoodsReceipt.supplier_id)).all()) if ids else {}
        last = dict(self.db.execute(select(GoodsReceipt.supplier_id, func.max(GoodsReceipt.receipt_date)).where(
            GoodsReceipt.organization_id == self.org, GoodsReceipt.supplier_id.in_(ids), GoodsReceipt.status == rules.RECEIVED)
            .group_by(GoodsReceipt.supplier_id)).all()) if ids else {}
        ncr = QualityReads(self.db, self.org).counts(ids)
        names = user_names(self.db, self.org, [s.status_changed_by_user_id for s in suppliers])
        out = []
        for s in suppliers:
            view = dict(receipts_count=receipts.get(s.id, 0), last_receipt_date=last.get(s.id), ncr_count=ncr.get(s.id, (0, 0))[0],
                        open_ncr_count=ncr.get(s.id, (0, 0))[1], status_changed_by_name=names.get(s.status_changed_by_user_id),
                        evaluation=self.evaluation(s.id), actions=rules.supplier_actions(lambda a: can(P.SUPPLIER_ACTIONS[a])))
            if detail:
                view.update(history=history(self.db, self.org, "supplier", s.id),
                            non_conformances=QualityReads(self.db, self.org).of_supplier(s.id),
                            recent_receipts=[dict(id=r.id, receipt_no=r.receipt_no, receipt_date=r.receipt_date, status=r.status)
                                             for r in self.db.scalars(select(GoodsReceipt).where(GoodsReceipt.organization_id == self.org,
                                                                                                 GoodsReceipt.supplier_id == s.id)
                                                                      .order_by(GoodsReceipt.receipt_date.desc(), GoodsReceipt.created_at.desc()).limit(20))])
            out.append(view)
        return out

    def _apply(self, supplier, values):
        from app.core.location_fields import normalize_city, assert_city_country
        try:
            values = normalize_city(values, supplier)
            assert_city_country(self.db, self.org, values, supplier)
        except ValueError as exc:
            raise ProcurementError(str(exc), 400) from exc
        if values.get("category") and unknown_list_values(self.db, self.org, "supplier_category", [values["category"]],
                                                          [supplier.category] if getattr(supplier, "category", None) else ()):
            raise ProcurementError("CATEGORY_UNKNOWN", 400)  # MD-003: from the organization's supplier categories
        for field in ("country", "city"):  # MD-002: from the organization's lists; the value already stored may stay
            if values.get(field) and unknown_list_values(self.db, self.org, field, [values[field]], [getattr(supplier, field)] if getattr(supplier, field, None) else ()):
                raise ProcurementError("LIST_VALUE_UNKNOWN", 400, field=field, value=values[field])
        _set(supplier, values, SUPPLIER_FIELDS, required=("name", "category"))
        if "phone" in values:
            supplier.phone = rules.normalize_phone(values["phone"])

    def create(self, data) -> Supplier:
        supplier = Supplier(organization_id=self.org, supplier_code=next_code(self.db, self.org, "SUP"), name=data.name.strip(), status=rules.PENDING,
                            created_by_user_id=self.tenant.user_id)
        self._apply(supplier, data.model_dump())
        self.db.add(supplier)
        self.db.flush()
        record(self.db, self.org, "supplier", supplier.id, "create", self.tenant.user_id, None, rules.PENDING)
        notices.supplier_awaits_approval(self.db, self.tenant, supplier)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "supplier.created", "supplier", supplier.id, supplier.name)
        return self._get(supplier.id)

    def update(self, supplier_id, data) -> Supplier:
        supplier = self._get(supplier_id, lock=True)
        self._apply(supplier, data.model_dump(exclude_unset=True))
        record(self.db, self.org, "supplier", supplier.id, "update", self.tenant.user_id, supplier.status, supplier.status)
        self.db.commit()
        return self._get(supplier.id)

    def evaluation(self, supplier_id, months=12) -> dict:
        """The supplier's score over the last months, from its incoming lots and non-conformance reports (PROC-002)."""
        supplier = self._get(supplier_id)
        since = utc_now() - timedelta(days=30 * months)
        data = QualityReads(self.db, self.org).supplier_period(supplier.id, since)
        released = sum(1 for inspected, accepted in data["lots"] if accepted >= inspected)
        return dict(months=months, since=since.date(), **rules.evaluate(len(data["lots"]), released, data["severities"], data["cost"]))

    def set_status(self, supplier_id, status, reason) -> Supplier:
        supplier = self._get(supplier_id, lock=True)
        rules.assert_status_change(supplier.status, status, reason)
        before = supplier.status
        supplier.status, supplier.status_reason = status, (reason or "").strip() or None
        supplier.status_changed_at, supplier.status_changed_by_user_id = utc_now(), self.tenant.user_id
        approvals.sign(self.db, self.tenant, "supplier", supplier.id, status, "procurement:suppliers:approve", supplier.status_reason)
        record(self.db, self.org, "supplier", supplier.id, "status", self.tenant.user_id, before, status, supplier.status_reason)
        notices.supplier_status_changed(self.db, self.tenant, supplier)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, f"supplier.{status}", "supplier", supplier.id, supplier.name)
        return self._get(supplier.id)


class MaterialService:
    def __init__(self, db, tenant):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id

    def _get(self, material_id) -> Material:
        found = self.db.scalar(select(Material).where(Material.id == material_id, Material.organization_id == self.org))
        if found is None:
            raise ProcurementError("MATERIAL_NOT_FOUND", 404)
        return found

    def list(self, category=None, search=None, active_only=False, limit=500):
        query = select(Material).where(Material.organization_id == self.org)
        if category:
            query = query.where(Material.category == category)
        if active_only:
            query = query.where(Material.active.is_(True))
        if search:
            query = query.where(or_(Material.name.icontains(search, autoescape=True), Material.material_code.icontains(search, autoescape=True)))
        return list(self.db.scalars(query.order_by(Material.name).limit(limit)))

    def _apply(self, material, values):
        if values.get("category") and unknown_list_values(self.db, self.org, "material_category", [values["category"]],
                                                          [material.category] if getattr(material, "category", None) else ()):
            raise ProcurementError("CATEGORY_UNKNOWN", 400)  # MD-003: from the organization's material categories
        # MD-001: the specification key is a product of the organization (asked through core); the one stored may stay.
        if values.get("spec_product_type") and unknown_product_types(self.db, self.org, [values["spec_product_type"]],
                                                                     [material.spec_product_type] if material.spec_product_type else ()):
            raise ProcurementError("PRODUCT_TYPE_UNKNOWN", 400, product_type=values["spec_product_type"])
        _set(material, values, MATERIAL_FIELDS, required=("name", "category", "unit", "inspection_required", "active"))

    def create(self, data) -> Material:
        material = Material(organization_id=self.org, material_code=next_code(self.db, self.org, "MAT"), name=data.name.strip())
        self._apply(material, data.model_dump())
        self.db.add(material)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "material.created", "material", material.id, material.name)
        return self._get(material.id)

    def update(self, material_id, data) -> Material:
        material = self._get(material_id)
        self._apply(material, data.model_dump(exclude_unset=True))
        self.db.commit()
        return self._get(material.id)


class ReceiptService:
    def __init__(self, db, tenant):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id
        self.suppliers = SupplierService(db, tenant)

    def _get(self, receipt_id, lock=False) -> GoodsReceipt:
        query = select(GoodsReceipt).options(selectinload(GoodsReceipt.lines)).where(GoodsReceipt.id == receipt_id, GoodsReceipt.organization_id == self.org)
        found = self.db.scalar(query.with_for_update() if lock else query)
        if found is None:
            raise ProcurementError("RECEIPT_NOT_FOUND", 404)
        return found

    def get(self, receipt_id) -> GoodsReceipt:
        return self._get(receipt_id)

    def list(self, status=None, supplier_id=None, date_from=None, date_to=None, search=None, limit=500):
        query = select(GoodsReceipt).options(selectinload(GoodsReceipt.lines)).where(GoodsReceipt.organization_id == self.org)
        if status:
            query = query.where(GoodsReceipt.status == status)
        if supplier_id:
            query = query.where(GoodsReceipt.supplier_id == supplier_id)
        if date_from:
            query = query.where(GoodsReceipt.receipt_date >= date_from)
        if date_to:
            query = query.where(GoodsReceipt.receipt_date <= date_to)
        if search:
            lots = select(GoodsReceiptLine.receipt_id).where(GoodsReceiptLine.supplier_lot.icontains(search, autoescape=True))
            like = lambda column: column.icontains(search, autoescape=True)  # noqa: E731
            query = query.where(or_(like(GoodsReceipt.receipt_no), like(GoodsReceipt.supplier_name), like(GoodsReceipt.supplier_delivery_no),
                                    like(GoodsReceipt.supplier_invoice_no), like(GoodsReceipt.purchase_reference), GoodsReceipt.id.in_(lots)))
        return list(self.db.scalars(query.order_by(GoodsReceipt.receipt_date.desc(), GoodsReceipt.created_at.desc()).limit(limit)))

    def views(self, receipts, can, detail=False) -> list[dict]:
        names = user_names(self.db, self.org, [u for r in receipts for u in (r.created_by_user_id, r.received_by_user_id)])
        statuses = dict(self.db.execute(select(Supplier.id, Supplier.status).where(Supplier.id.in_({r.supplier_id for r in receipts}))).all()) if receipts else {}
        inspections = QualityReads(self.db, self.org).inspections_of([line.id for r in receipts for line in r.lines if line.inspection_required])
        orders = dict(self.db.execute(select(PurchaseOrder.id, PurchaseOrder.po_number).where(
            PurchaseOrder.id.in_({r.purchase_order_id for r in receipts if r.purchase_order_id}))).all()) if receipts else {}
        out = []
        for r in receipts:
            per_unit: dict = {}
            for line in r.lines:
                per_unit[line.unit] = per_unit.get(line.unit, 0) + line.quantity
            weights = [to_kilograms(line.weight, line.weight_unit) for line in r.lines if line.weight is not None]
            view = dict(created_by_name=names.get(r.created_by_user_id), received_by_name=names.get(r.received_by_user_id),
                        po_number=orders.get(r.purchase_order_id),
                        supplier_status=statuses.get(r.supplier_id), quantities=[dict(unit=u, quantity=q) for u, q in per_unit.items()],
                        weight_kg=sum(weights) if weights else None, inspection_lines=sum(1 for line in r.lines if line.inspection_required),
                        lots_pending=sum(1 for line in r.lines if r.status == rules.RECEIVED
                                         and rules.lot_status(line.inspection_required, inspections.get(line.id, [])) in ("awaiting", "inspecting")),
                        actions=rules.receipt_actions(r.status, lambda a: can(P.RECEIPT_ACTIONS[a])))
            if detail:
                view["history"] = history(self.db, self.org, "receipt", r.id)
                view["line_quality"] = {str(line.id): dict(status=rules.lot_status(line.inspection_required, inspections.get(line.id, [])),
                                                           inspection=(inspections.get(line.id) or [None])[-1])
                                        for line in r.lines}
            out.append(view)
        return out

    def _supplier(self, supplier_id):
        supplier = self.suppliers.get(supplier_id)
        rules.assert_supplier_usable(supplier.status)
        return supplier

    def _order(self, receipt, order_id):
        """The purchase order a receipt delivers against: the same supplier, still open for receiving."""
        if order_id is None:
            receipt.purchase_order_id = None
            return
        order = self.db.scalar(select(PurchaseOrder).where(PurchaseOrder.id == order_id, PurchaseOrder.organization_id == self.org))
        if order is None:
            raise ProcurementError("ORDER_NOT_FOUND", 404)
        if order.supplier_id != receipt.supplier_id:
            raise ProcurementError("ORDER_OF_ANOTHER_SUPPLIER", 400)
        PO.assert_receivable(order.status)
        receipt.purchase_order_id = order.id
        if not receipt.purchase_reference:
            receipt.purchase_reference = order.po_number

    def _write_lines(self, receipt, lines):
        owners = by_line_owner(self.db, [d.po_line_id for d in lines if d.po_line_id])
        for number, data in enumerate(lines, 1):
            if data.po_line_id:  # a line of the receipt's own order, counted in its unit
                owner = owners.get(data.po_line_id)
                if owner is None or owner[0] != receipt.purchase_order_id:
                    raise ProcurementError("ORDER_LINE_NOT_IN_ORDER", 400, line=number)
                if owner[1] != data.unit:
                    raise ProcurementError("ORDER_LINE_UNIT_MISMATCH", 400, line=number, unit=owner[1])
        materials = {m.id: m for m in self.db.scalars(select(Material).where(
            Material.organization_id == self.org, Material.id.in_([d.material_id for d in lines if d.material_id])))}
        receipt.lines.clear()
        self.db.flush()
        for number, data in enumerate(lines, 1):
            values = {f: getattr(data, f) for f in LINE_FIELDS}
            material = materials.get(data.material_id) if data.material_id else None
            if data.material_id and material is None:
                raise ProcurementError("MATERIAL_NOT_FOUND", 404, line=number)
            if material is not None:
                values["description"] = (data.description or "").strip() or material.name
            line = GoodsReceiptLine(line_no=number, inspection_required=bool(material and material.inspection_required), **values)
            rules.assert_line(line)
            receipt.lines.append(line)

    def create(self, data) -> GoodsReceipt:
        supplier = self._supplier(data.supplier_id)
        receipt = GoodsReceipt(organization_id=self.org, receipt_no=next_receipt_number(self.db, self.org), status=rules.DRAFT,
                               receipt_date=data.receipt_date, supplier_id=supplier.id, supplier_name=supplier.name, created_by_user_id=self.tenant.user_id)
        _set(receipt, apply_transport(self.db, self.org, receipt, data.model_dump(exclude={"lines", "supplier_id"})), RECEIPT_FIELDS, required=("receipt_date",))
        self._order(receipt, data.purchase_order_id)
        self.db.add(receipt)
        self.db.flush()
        self._write_lines(receipt, data.lines)
        record(self.db, self.org, "receipt", receipt.id, "create", self.tenant.user_id, None, rules.DRAFT)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "goods_receipt.created", "goods_receipt", receipt.id, receipt.receipt_no)
        return self._get(receipt.id)

    def update(self, receipt_id, data) -> GoodsReceipt:
        receipt = self._get(receipt_id, lock=True)
        rules.assert_editable(receipt.status)
        values = data.model_dump(exclude_unset=True, exclude={"lines"})
        if values.get("supplier_id"):
            supplier = self._supplier(values["supplier_id"])
            receipt.supplier_id, receipt.supplier_name = supplier.id, supplier.name
        _set(receipt, apply_transport(self.db, self.org, receipt, values), RECEIPT_FIELDS, required=("receipt_date",))
        if "purchase_order_id" in values or values.get("supplier_id"):
            self._order(receipt, values.get("purchase_order_id", receipt.purchase_order_id))
            if data.lines is None and any(line.po_line_id for line in receipt.lines):
                self._write_lines(receipt, [_LineData.of(line) for line in receipt.lines])
        if data.lines is not None:
            self._write_lines(receipt, data.lines)
        self.db.commit()
        return self._get(receipt.id)

    def receive(self, receipt_id) -> GoodsReceipt:
        receipt = self._get(receipt_id, lock=True)
        rules.assert_can_receive(receipt.status, len(receipt.lines), self.suppliers.get(receipt.supplier_id).status)
        if receipt.purchase_order_id:
            PO.assert_receivable(self.db.get(PurchaseOrder, receipt.purchase_order_id).status)
        receipt.status, receipt.received_at, receipt.received_by_user_id = rules.RECEIVED, utc_now(), self.tenant.user_id
        record(self.db, self.org, "receipt", receipt.id, "receive", self.tenant.user_id, rules.DRAFT, rules.RECEIVED)
        if receipt.purchase_order_id:
            self.db.flush()
            PurchaseOrderService(self.db, self.tenant).refresh_received(receipt.purchase_order_id)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "goods_receipt.received", "goods_receipt", receipt.id, receipt.receipt_no)
        return self._get(receipt.id)

    def cancel(self, receipt_id, reason) -> GoodsReceipt:
        receipt = self._get(receipt_id, lock=True)
        rules.assert_can_cancel(receipt.status, reason)
        before = receipt.status
        receipt.status, receipt.cancel_reason = rules.CANCELLED, reason.strip()
        record(self.db, self.org, "receipt", receipt.id, "cancel", self.tenant.user_id, before, rules.CANCELLED, receipt.cancel_reason)
        if receipt.purchase_order_id and before == rules.RECEIVED:
            self.db.flush()
            PurchaseOrderService(self.db, self.tenant).refresh_received(receipt.purchase_order_id)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "goods_receipt.cancelled", "goods_receipt", receipt.id, receipt.receipt_no)
        return self._get(receipt.id)

    def settings(self):
        current = settings(self.db, self.org)
        self.db.commit()
        return current

    def update_settings(self, values: dict):
        """Number prefixes (numbers already issued keep theirs) and the purchase order terms."""
        current = settings(self.db, self.org)
        for field in ("receipt_prefix", "po_prefix"):
            if values.get(field):
                setattr(current, field, values[field])
        for field in ("po_terms_ar", "po_terms_en"):
            if field in values:
                setattr(current, field, (values[field] or "").strip() or None)
        self.db.commit()
        return current


class _LineData:
    """A saved receipt line in the shape of its input, to check it again against a changed order."""
    @staticmethod
    def of(line):
        data = _LineData()
        for field in LINE_FIELDS:
            setattr(data, field, getattr(line, field))
        return data

from app.core.interfaces.transport_directory import apply_transport
