"""Purchase orders (PROC-003): the single writer of an order and its lines.

Amounts are computed here from the lines (domain/purchase_orders.py). What was received comes from the confirmed goods
receipts made against the order's lines; ReceiptService calls refresh_received() after a receipt is confirmed or cancelled.
Every write records the procurement history and the activity log.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.core.interfaces import approvals
from app.core.interfaces.product_catalog import business_settings
from app.core.utils import utc_now
from app.procurement.domain import permissions as P
from app.procurement.domain import purchase_orders as PO
from app.procurement.domain import rules
from app.procurement.domain.rules import ProcurementError
from app.procurement.infrastructure.models import GoodsReceipt, GoodsReceiptLine, Material, PurchaseOrder, PurchaseOrderLine, Supplier
from .support import history, log_activity, next_po_number, record, settings, user_names
from . import notices

HEADER = ("order_date", "required_date", "attention", "supplier_quote_ref", "subject", "currency", "payment_terms", "payment_terms_note", "incoterm",
          "delivery_place", "notes")
REQUIRED = ("order_date", "currency")


def received_by_line(db, line_ids) -> dict:
    """{po_line_id: quantity received} from confirmed goods receipts."""
    if not line_ids:
        return {}
    rows = db.execute(select(GoodsReceiptLine.po_line_id, func.sum(GoodsReceiptLine.quantity)).join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.receipt_id)
                      .where(GoodsReceiptLine.po_line_id.in_(list(line_ids)), GoodsReceipt.status == rules.RECEIVED)
                      .group_by(GoodsReceiptLine.po_line_id)).all()
    return {line_id: Decimal(quantity or 0) for line_id, quantity in rows}


class PurchaseOrderService:
    def __init__(self, db, tenant):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id

    # ── reads ──────────────────────────────────────────────────────────────────────────────────
    def _get(self, order_id, lock=False) -> PurchaseOrder:
        query = select(PurchaseOrder).options(selectinload(PurchaseOrder.lines)).where(PurchaseOrder.id == order_id, PurchaseOrder.organization_id == self.org)
        found = self.db.scalar(query.with_for_update() if lock else query)
        if found is None:
            raise ProcurementError("ORDER_NOT_FOUND", 404)
        return found

    def get(self, order_id) -> PurchaseOrder:
        return self._get(order_id)

    def list(self, status=None, supplier_id=None, date_from=None, date_to=None, search=None, open_only=False, limit=500):
        query = select(PurchaseOrder).options(selectinload(PurchaseOrder.lines)).where(PurchaseOrder.organization_id == self.org)
        if status:
            query = query.where(PurchaseOrder.status == status)
        if open_only:
            query = query.where(PurchaseOrder.status.in_(PO.RECEIVABLE))
        if supplier_id:
            query = query.where(PurchaseOrder.supplier_id == supplier_id)
        if date_from:
            query = query.where(PurchaseOrder.order_date >= date_from)
        if date_to:
            query = query.where(PurchaseOrder.order_date <= date_to)
        if search:
            like = lambda column: column.icontains(search, autoescape=True)  # noqa: E731
            items = select(PurchaseOrderLine.order_id).where(like(PurchaseOrderLine.description))
            query = query.where(or_(like(PurchaseOrder.po_number), like(PurchaseOrder.supplier_name), like(PurchaseOrder.supplier_quote_ref),
                                    like(PurchaseOrder.subject), PurchaseOrder.id.in_(items)))
        return list(self.db.scalars(query.order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.created_at.desc()).limit(limit)))

    def views(self, orders, can, detail=False) -> list[dict]:
        received = received_by_line(self.db, [line.id for o in orders for line in o.lines])
        names = user_names(self.db, self.org, [u for o in orders for u in (o.created_by_user_id, o.approved_by_user_id, o.sent_by_user_id)])
        statuses = dict(self.db.execute(select(Supplier.id, Supplier.status).where(Supplier.id.in_({o.supplier_id for o in orders}))).all()) if orders else {}
        signed = approvals.signatures(self.db, self.org, "purchase_order", [o.id for o in orders])
        out = []
        for o in orders:
            got = {line.id: received.get(line.id, Decimal(0)) for line in o.lines}
            any_received = any(q > 0 for q in got.values())
            ordered = sum((line.quantity for line in o.lines), Decimal(0))
            view = dict(supplier_status=statuses.get(o.supplier_id), created_by_name=names.get(o.created_by_user_id),
                        approved_by_name=names.get(o.approved_by_user_id), sent_by_name=names.get(o.sent_by_user_id),
                        approval=approvals.latest(signed.get(o.id, []), "approve"),
                        line_count=len(o.lines), received_pct=(min(Decimal(100), sum(min(got[l.id], l.quantity) for l in o.lines) * 100 / ordered)
                                                               .quantize(Decimal("0.1")) if ordered else Decimal(0)),
                        actions=PO.actions(o.status, lambda a: can(P.PO_ACTIONS[a]), any_received))
            if detail:
                view["line_received"] = {str(line.id): dict(received=got[line.id], remaining=max(Decimal(0), line.quantity - got[line.id]))
                                         for line in o.lines}
                view["receipts"] = [dict(id=r.id, receipt_no=r.receipt_no, receipt_date=r.receipt_date, status=r.status) for r in self.db.scalars(
                    select(GoodsReceipt).where(GoodsReceipt.organization_id == self.org, GoodsReceipt.purchase_order_id == o.id)
                    .order_by(GoodsReceipt.receipt_date, GoodsReceipt.created_at))]
                view["history"] = history(self.db, self.org, "purchase_order", o.id)
            out.append(view)
        return out

    def open_for_receipt(self, supplier_id) -> list[dict]:
        """The supplier's orders that goods may be received against, with what each line still expects."""
        orders = self.list(supplier_id=supplier_id, open_only=True, limit=50)
        received = received_by_line(self.db, [line.id for o in orders for line in o.lines])
        return [dict(id=o.id, po_number=o.po_number, order_date=o.order_date, status=o.status, lines=[
            dict(id=line.id, line_no=line.line_no, material_id=line.material_id, description=line.description, unit=line.unit, quantity=line.quantity,
                 remaining=max(Decimal(0), line.quantity - received.get(line.id, Decimal(0)))) for line in o.lines]) for o in orders]

    # ── writes ─────────────────────────────────────────────────────────────────────────────────
    def _supplier(self, supplier_id) -> Supplier:
        supplier = self.db.scalar(select(Supplier).where(Supplier.id == supplier_id, Supplier.organization_id == self.org))
        if supplier is None:
            raise ProcurementError("SUPPLIER_NOT_FOUND", 404)
        rules.assert_supplier_usable(supplier.status)
        return supplier

    def _apply(self, order, values, lines=None):
        from app.procurement.infrastructure.contact_models import SupplierContact
        selected=values.get('supplier_contact_id',order.supplier_contact_id)
        if selected:
            contact=self.db.scalar(select(SupplierContact).where(SupplierContact.id==selected,
                SupplierContact.organization_id==self.org,SupplierContact.supplier_id==order.supplier_id))
            if not contact or (selected!=order.supplier_contact_id and not contact.active):
                raise ProcurementError('SUPPLIER_CONTACT_UNAVAILABLE',422)
            values['attention']=contact.name if selected!=order.supplier_contact_id else order.attention
        if 'supplier_contact_id' in values:
            order.supplier_contact_id=selected
        kept_rate = order.tax_rate
        for field in HEADER:
            if field in values and not (field in REQUIRED and values[field] is None):
                setattr(order, field, values[field])
        if values.get("tax_rate") is not None:
            order.tax_rate = values["tax_rate"]
        if values.get("discount_amount") is not None:
            order.discount_amount = values["discount_amount"]
        PO.assert_header(order.currency, order.tax_rate, order.incoterm, order.payment_terms,
                         (0, business_settings(self.db, self.org).vat_rate, *([kept_rate] if kept_rate is not None else [])))
        if lines is not None:
            self._write_lines(order, lines)
        amounts = PO.totals([(line.quantity, line.unit_price) for line in order.lines], order.discount_amount, order.tax_rate)
        order.subtotal_amount, order.discount_amount = amounts["subtotal"], amounts["discount"]
        order.tax_amount, order.total_amount = amounts["tax_amount"], amounts["total"]

    def _write_lines(self, order, lines):
        materials = {m.id: m for m in self.db.scalars(select(Material).where(
            Material.organization_id == self.org, Material.id.in_([d.material_id for d in lines if d.material_id])))}
        order.lines.clear()
        self.db.flush()
        for number, data in enumerate(lines, 1):
            material = materials.get(data.material_id) if data.material_id else None
            if data.material_id and material is None:
                raise ProcurementError("MATERIAL_NOT_FOUND", 404, line=number)
            description = (data.description or "").strip() or (material.name if material else "")
            line = PurchaseOrderLine(line_no=number, material_id=data.material_id, description=description, notes=data.notes, quantity=data.quantity,
                                     unit=data.unit, unit_price=data.unit_price, line_total=PO.line_total(data.quantity, data.unit_price))
            PO.assert_line(line)
            order.lines.append(line)

    def _commit(self, order, action, before=None, reason=None):
        record(self.db, self.org, "purchase_order", order.id, action, self.tenant.user_id, before, order.status, reason)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, f"purchase_order.{action}", "purchase_order", order.id, order.po_number)
        return self._get(order.id)

    def create(self, data) -> PurchaseOrder:
        supplier = self._supplier(data.supplier_id)
        general = business_settings(self.db, self.org)  # the organization's VAT rate and default currency (master data)
        order = PurchaseOrder(organization_id=self.org, po_number=next_po_number(self.db, self.org), status=PO.DRAFT, supplier_id=supplier.id,
                              supplier_name=supplier.name, attention=supplier.contact_name, created_by_user_id=self.tenant.user_id,
                              order_date=data.order_date, currency=data.currency or general.default_currency, discount_amount=Decimal(0))
        order.tax_rate = Decimal(data.tax_rate) if data.tax_rate is not None else general.vat_rate
        self.db.add(order)
        self.db.flush()
        values = data.model_dump(exclude={"lines", "supplier_id", "tax_rate"})
        if not values.get("attention"):  # the supplier's contact, unless another is named
            values.pop("attention")
        if values.get("currency") is None:
            values.pop("currency")
        self._apply(order, values, data.lines)
        notices.order_awaits_approval(self.db, self.tenant, order)
        return self._commit(order, "create")

    def update(self, order_id, data) -> PurchaseOrder:
        order = self._get(order_id, lock=True)
        PO.assert_editable(order.status)
        values = data.model_dump(exclude_unset=True, exclude={"lines"})
        if values.get("supplier_id"):
            supplier = self._supplier(values["supplier_id"])
            if supplier.id != order.supplier_id:
                order.supplier_contact_id=None
                order.attention=supplier.contact_name
            order.supplier_id, order.supplier_name = supplier.id, supplier.name
        self._apply(order, values, data.lines)
        return self._commit(order, "update", order.status)

    def approve(self, order_id) -> PurchaseOrder:
        order = self._get(order_id, lock=True)
        supplier = self.db.get(Supplier, order.supplier_id)
        PO.assert_can_approve(order.status, len(order.lines), order.total_amount, supplier.status if supplier else None)
        # Separation of duties: who prepared the order does not approve it (the organization's root excepted: a one-person company).
        if order.created_by_user_id == self.tenant.user_id and not self.tenant.is_organization_root:
            raise ProcurementError("APPROVER_IS_PREPARER", 409)
        order.status, order.approved_at, order.approved_by_user_id = PO.APPROVED, utc_now(), self.tenant.user_id
        try:  # whose authority and who signed, fixed now (directly, or under a delegation in force)
            approvals.record(self.db, self.tenant, "purchase_order", order.id, "approve", P.PO_APPROVE)
        except PermissionError as exc:
            self.db.rollback()
            raise ProcurementError("APPROVAL_AUTHORITY_REQUIRED", 403) from exc
        notices.order_approved(self.db, self.tenant, order)
        return self._commit(order, "approve", PO.DRAFT)

    def send(self, order_id) -> PurchaseOrder:
        order = self._get(order_id, lock=True)
        PO.assert_can_send(order.status)
        order.status, order.sent_at, order.sent_by_user_id = PO.SENT, utc_now(), self.tenant.user_id
        return self._commit(order, "send", PO.APPROVED)

    def close(self, order_id, reason) -> PurchaseOrder:
        order = self._get(order_id, lock=True)
        PO.assert_can_close(order.status, reason)
        before = order.status
        order.status, order.closed_at, order.close_reason = PO.CLOSED, utc_now(), reason.strip()
        return self._commit(order, "close", before, order.close_reason)

    def cancel(self, order_id, reason) -> PurchaseOrder:
        order = self._get(order_id, lock=True)
        received = received_by_line(self.db, [line.id for line in order.lines])
        pending = self.db.scalar(select(func.count()).select_from(GoodsReceipt).where(GoodsReceipt.purchase_order_id == order.id,
                                                                                    GoodsReceipt.status == rules.DRAFT))
        PO.assert_can_cancel(order.status, any(q > 0 for q in received.values()) or bool(pending), reason)
        before = order.status
        order.status, order.cancel_reason = PO.CANCELLED, reason.strip()
        notices.order_cancelled(self.db, self.tenant, order)
        return self._commit(order, "cancel", before, order.cancel_reason)

    def refresh_received(self, order_id) -> None:
        """After a goods receipt against the order is confirmed or cancelled: partially received or received, by itself.
        The caller commits."""
        order = self.db.scalar(select(PurchaseOrder).options(selectinload(PurchaseOrder.lines)).where(PurchaseOrder.id == order_id).with_for_update())
        if order is None:
            return
        received = received_by_line(self.db, [line.id for line in order.lines])
        status = PO.received_status(order.status, [(line.quantity, received.get(line.id, Decimal(0))) for line in order.lines])
        if status != order.status:
            record(self.db, self.org, "purchase_order", order.id, "received" if status == PO.RECEIVED else "receipt", self.tenant.user_id, order.status, status)
            order.status = status

    # ── settings ───────────────────────────────────────────────────────────────────────────────
    def terms(self, lang) -> list[str]:
        current = settings(self.db, self.org)
        text = (current.po_terms_ar if lang == "ar" else (current.po_terms_en or current.po_terms_ar)) or ""
        return [line.strip() for line in text.splitlines() if line.strip()]


def by_line_owner(db, po_line_ids) -> dict:
    """{po_line_id: (order_id, unit)} for lines a receipt names."""
    if not po_line_ids:
        return {}
    return {i: (o, u) for i, o, u in db.execute(select(PurchaseOrderLine.id, PurchaseOrderLine.order_id, PurchaseOrderLine.unit)
                                               .where(PurchaseOrderLine.id.in_(list(po_line_ids)))).all()}

