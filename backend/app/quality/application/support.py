"""Reads Quality needs from other modules, numbering and lifecycle history (QUAL-001).

Production, commercial and foundation rows are read through the shared tables (Base.metadata), never
by importing another module's models (ADR-004). The production order row is locked FOR UPDATE by
every quality write tied to an order, the same lock production takes to close it, so a close and
a new check or rejection never cross.
"""
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from app.core.db import Base
from app.core.interfaces.activity_log import get_registered_activity_logger
from app.core.utils import utc_now
from app.quality.domain.rules import ORDER_STATUSES, QualityError
from app.quality.infrastructure.models import QualityCodeCounter, QualityStatusHistory


def _t(name):
    return Base.metadata.tables[name]


@dataclass(frozen=True)
class OrderRef:
    id: UUID
    number: str
    product_type: str
    status: str
    unit: str


@dataclass(frozen=True)
class ItemRef:
    id: UUID
    line_no: int
    unit: str


class ProductionReads:
    def __init__(self, db, organization_id):
        self.db, self.org = db, organization_id

    def order(self, order_id, *, lock=False, inspectable=False, statuses=ORDER_STATUSES) -> OrderRef:
        orders = _t("production_orders")
        query = select(orders.c.id, orders.c.production_order_number, orders.c.product_type, orders.c.status, orders.c.unit).where(
            orders.c.id == order_id, orders.c.organization_id == self.org)
        row = self.db.execute(query.with_for_update() if lock else query).first()
        if row is None:
            raise QualityError("PRODUCTION_ORDER_NOT_FOUND", 404)
        ref = OrderRef(row.id, row.production_order_number, row.product_type, getattr(row.status, "value", row.status), row.unit)
        if inspectable and ref.status not in statuses:
            raise QualityError("ORDER_NOT_INSPECTABLE", order_status=ref.status)
        return ref

    def item(self, order_id, item_id) -> ItemRef:
        items = _t("production_order_items")
        row = self.db.execute(select(items.c.id, items.c.line_no, items.c.unit).where(
            items.c.id == item_id, items.c.production_order_id == order_id)).first()
        if row is None:
            raise QualityError("ORDER_ITEM_NOT_FOUND", 404)
        return ItemRef(row.id, row.line_no, row.unit)

    def lot_spec(self, order_id, item_id=None) -> tuple[str, dict]:
        """(product type, specification values) of the inspected lot: the order line's, else the order's."""
        orders, items = _t("production_orders"), _t("production_order_items")
        order = self.db.execute(select(orders.c.product_type, orders.c.target_spec_json).where(
            orders.c.id == order_id, orders.c.organization_id == self.org)).first()
        if order is None:
            raise QualityError("PRODUCTION_ORDER_NOT_FOUND", 404)
        spec = order.target_spec_json
        if item_id:
            spec = self.db.scalar(select(items.c.target_spec_json).where(items.c.id == item_id, items.c.production_order_id == order_id)) or spec
        return order.product_type, dict(spec or {})

    def lot_facts(self, order_id, item_id=None) -> dict:
        """Order number, line number and completion time of a lot, for its certificate."""
        orders, items = _t("production_orders"), _t("production_order_items")
        order = self.db.execute(select(orders.c.production_order_number, orders.c.product_type, orders.c.actual_end_at).where(
            orders.c.id == order_id, orders.c.organization_id == self.org)).first()
        if order is None:
            raise QualityError("PRODUCTION_ORDER_NOT_FOUND", 404)
        line_no = self.db.scalar(select(items.c.line_no).where(items.c.id == item_id, items.c.production_order_id == order_id)) if item_id else None
        return dict(number=order.production_order_number, product_type=order.product_type, completed_at=order.actual_end_at, line_no=line_no)

    def customers(self, order_id, item_id=None) -> list[dict]:
        """The customers whose demand the lot was allocated to (the line's allocations, else the order's)."""
        allocations, demands, customers = _t("production_allocations"), _t("production_demands"), _t("commercial_customers")
        query = (select(customers.c.id, customers.c.name).distinct()
                 .select_from(allocations.join(demands, demands.c.id == allocations.c.production_demand_id)
                              .join(customers, customers.c.id == demands.c.customer_id))
                 .where(allocations.c.organization_id == self.org, allocations.c.production_order_id == order_id,
                        customers.c.organization_id == self.org))
        if item_id:
            query = query.where(allocations.c.production_order_item_id == item_id)
        return [dict(id=i, name=n) for i, n in self.db.execute(query.order_by(customers.c.name)).all()]

    def numbers(self, order_ids) -> dict:
        orders = _t("production_orders")
        ids = [i for i in set(order_ids) if i]
        return dict(self.db.execute(select(orders.c.id, orders.c.production_order_number).where(
            orders.c.organization_id == self.org, orders.c.id.in_(ids))).all()) if ids else {}

    def line_numbers(self, item_ids) -> dict:
        items = _t("production_order_items")
        ids = [i for i in set(item_ids) if i]
        return dict(self.db.execute(select(items.c.id, items.c.line_no).where(items.c.id.in_(ids))).all()) if ids else {}

    def inspectable_orders(self, search: str = "", limit: int = 50, statuses=ORDER_STATUSES) -> list[dict]:
        """Orders a check can be opened on (running, held, completed), with their lines, newest first."""
        orders, items = _t("production_orders"), _t("production_order_items")
        query = select(orders.c.id, orders.c.production_order_number, orders.c.product_type, orders.c.status, orders.c.unit).where(
            orders.c.organization_id == self.org, orders.c.status.in_(sorted(statuses)))
        if search:
            query = query.where(orders.c.production_order_number.icontains(search, autoescape=True)
                                | orders.c.product_type.icontains(search, autoescape=True))
        rows = self.db.execute(query.order_by(orders.c.created_at.desc()).limit(limit)).all()
        lines = {}
        if rows:
            for r in self.db.execute(select(items.c.id, items.c.production_order_id, items.c.line_no, items.c.unit, items.c.planned_quantity,
                                            items.c.target_spec_json).where(items.c.production_order_id.in_([r.id for r in rows]))
                                     .order_by(items.c.line_no)).all():
                lines.setdefault(r.production_order_id, []).append(dict(id=r.id, line_no=r.line_no, unit=r.unit,
                                                                         planned_quantity=r.planned_quantity, spec=r.target_spec_json))
        return [dict(id=r.id, number=r.production_order_number, product_type=r.product_type, status=getattr(r.status, "value", r.status),
                     unit=r.unit, items=lines.get(r.id, [])) for r in rows]


class CommercialReads:
    def __init__(self, db, organization_id):
        self.db, self.org = db, organization_id

    def sample(self, sample_id) -> dict:
        samples, customers = _t("commercial_samples"), _t("commercial_customers")
        row = self.db.execute(select(samples.c.id, samples.c.sample_code, samples.c.product_type, samples.c.unit).join(
            customers, customers.c.id == samples.c.customer_id).where(samples.c.id == sample_id, customers.c.organization_id == self.org)).first()
        if row is None:
            raise QualityError("SAMPLE_NOT_FOUND", 404)
        return dict(id=row.id, code=row.sample_code, product_type=row.product_type, unit=row.unit)

    def sample_spec(self, sample_id) -> tuple[str, dict]:
        """(product type, requested specification) of a commercial sample."""
        samples, customers = _t("commercial_samples"), _t("commercial_customers")
        row = self.db.execute(select(samples.c.product_type, samples.c.requested_spec_json).join(customers, customers.c.id == samples.c.customer_id)
                              .where(samples.c.id == sample_id, customers.c.organization_id == self.org)).first()
        if row is None:
            raise QualityError("SAMPLE_NOT_FOUND", 404)
        return row.product_type, dict(row.requested_spec_json or {})

    def sample_codes(self, sample_ids) -> dict:
        samples, customers = _t("commercial_samples"), _t("commercial_customers")
        ids = [i for i in set(sample_ids) if i]
        return dict(self.db.execute(select(samples.c.id, samples.c.sample_code).join(customers, customers.c.id == samples.c.customer_id)
                                    .where(samples.c.id.in_(ids), customers.c.organization_id == self.org)).all()) if ids else {}

    def samples(self, search: str = "", limit: int = 50) -> list[dict]:
        samples, customers = _t("commercial_samples"), _t("commercial_customers")
        query = select(samples.c.id, samples.c.sample_code, samples.c.product_type, samples.c.unit, customers.c.name).join(
            customers, customers.c.id == samples.c.customer_id).where(customers.c.organization_id == self.org)
        if search:
            query = query.where(samples.c.sample_code.icontains(search, autoescape=True) | customers.c.name.icontains(search, autoescape=True))
        return [dict(id=r.id, code=r.sample_code, product_type=r.product_type, unit=r.unit, customer=r.name)
                for r in self.db.execute(query.order_by(samples.c.created_at.desc()).limit(limit)).all()]


class ShippingReads:
    """Returned goods as quality needs them (QUAL-RET-001), read through the shared tables: the shipping returns received
    for quality, their lines, and the shipments that carried the same production order (read only, ADR-004)."""
    LEFT_OR_LEAVING = ("ready", "dispatched", "delivered", "partially_delivered", "returned", "not_delivered")

    def __init__(self, db, organization_id):
        self.db, self.org = db, organization_id

    def _lines(self):
        returns, lines, notes, note_lines = (_t("shipping_returns"), _t("shipping_return_lines"), _t("shipping_shipments"),
                                             _t("shipping_shipment_lines"))
        query = (select(lines.c.id.label("line_id"), lines.c.line_no, lines.c.description, lines.c.width_mm, lines.c.thickness_mm, lines.c.unit,
                        lines.c.weight_unit, lines.c.production_order_no, lines.c.received_quantity, lines.c.received_weight,
                        returns.c.id.label("return_id"), returns.c.return_no, returns.c.kind, returns.c.reason, returns.c.responsibility,
                        returns.c.details, returns.c.customer_name, returns.c.received_at, returns.c.status, returns.c.quality_required,
                        notes.c.id.label("shipment_id"), notes.c.shipment_no, note_lines.c.production_order_id)
                 .join(returns, returns.c.id == lines.c.return_id).join(notes, notes.c.id == returns.c.shipment_id)
                 .join(note_lines, note_lines.c.id == lines.c.shipment_line_id).where(returns.c.organization_id == self.org))
        return returns, lines, query

    @staticmethod
    def _row(r) -> dict:
        row = dict(r._mapping)
        row["awaiting_quality"] = r.status == "received" and bool(r.quality_required) and (r.received_quantity or 0) > 0
        return row

    def line(self, line_id) -> dict | None:
        _returns, lines, query = self._lines()
        r = self.db.execute(query.where(lines.c.id == line_id)).first()
        return self._row(r) if r else None

    def refs(self, line_ids) -> dict:
        """return line id -> the line with its return and delivery note (for showing an inspection's source)."""
        ids = [i for i in set(line_ids) if i]
        if not ids:
            return {}
        _returns, lines, query = self._lines()
        return {r.line_id: self._row(r) for r in self.db.execute(query.where(lines.c.id.in_(ids))).all()}

    def return_numbers(self, return_ids) -> dict:
        ids = [i for i in set(return_ids) if i]
        returns = _t("shipping_returns")
        return dict(self.db.execute(select(returns.c.id, returns.c.return_no).where(returns.c.organization_id == self.org,
                                                                                     returns.c.id.in_(ids))).all()) if ids else {}

    def received_for_quality(self, search: str = "", limit: int = 300) -> list[dict]:
        returns, _lines, query = self._lines()
        query = query.where(returns.c.status == "received", returns.c.quality_required.is_(True))
        if search:
            query = query.where(returns.c.return_no.icontains(search, autoescape=True) | returns.c.customer_name.icontains(search, autoescape=True))
        rows = self.db.execute(query.order_by(returns.c.received_at.desc(), returns.c.return_no, _lines.c.line_no).limit(limit)).all()
        return [self._row(r) for r in rows]

    def batch(self, production_order_id) -> list[dict]:
        """Every note line that carried this production order, newest first, with where the goods are now."""
        if not production_order_id:
            return []
        notes, note_lines = _t("shipping_shipments"), _t("shipping_shipment_lines")
        rows = self.db.execute(select(notes.c.id.label("shipment_id"), notes.c.shipment_no, notes.c.status, notes.c.shipment_date,
                                      notes.c.customer_name, note_lines.c.quantity, note_lines.c.delivered_quantity, note_lines.c.unit)
                               .join(notes, notes.c.id == note_lines.c.shipment_id)
                               .where(notes.c.organization_id == self.org, note_lines.c.production_order_id == production_order_id,
                                      notes.c.status.in_(self.LEFT_OR_LEAVING))
                               .order_by(notes.c.shipment_date.desc(), notes.c.shipment_no.desc())).all()
        return [dict(r._mapping) for r in rows]


class ProcurementReads:
    """The organization's suppliers (PROC-001), read through the shared tables: a report names a registered supplier."""

    def __init__(self, db, organization_id):
        self.db, self.org = db, organization_id

    def supplier(self, supplier_id) -> dict | None:
        suppliers = _t("procurement_suppliers")
        row = self.db.execute(select(suppliers.c.id, suppliers.c.supplier_code, suppliers.c.name, suppliers.c.status).where(
            suppliers.c.organization_id == self.org, suppliers.c.id == supplier_id)).first()
        return dict(row._mapping) if row else None

    def search(self, text: str = "", limit: int = 30) -> list[dict]:
        suppliers = _t("procurement_suppliers")
        query = select(suppliers.c.id, suppliers.c.supplier_code, suppliers.c.name, suppliers.c.status).where(suppliers.c.organization_id == self.org)
        if text:
            query = query.where(suppliers.c.name.icontains(text, autoescape=True) | suppliers.c.supplier_code.icontains(text, autoescape=True))
        return [dict(r._mapping) for r in self.db.execute(query.order_by(suppliers.c.name).limit(limit)).all()]


def user_names(db, organization_id, user_ids) -> dict:
    users = _t("foundation_users")
    ids = [i for i in set(user_ids) if i]
    return dict(db.execute(select(users.c.id, users.c.full_name).where(users.c.organization_id == organization_id, users.c.id.in_(ids))).all()) if ids else {}


def next_code(db, organization_id, kind: str) -> str:
    """QI-YYYY-NNNN / QR-YYYY-NNNN from a locked per-organization counter: never repeated under concurrency."""
    year = utc_now().year
    counter = db.get(QualityCodeCounter, (organization_id, kind, year), with_for_update=True)
    if counter is None:
        counter = QualityCodeCounter(organization_id=organization_id, kind=kind, year=year, value=0)
        db.add(counter)
        db.flush()
        counter = db.get(QualityCodeCounter, (organization_id, kind, year), with_for_update=True)
    counter.value += 1
    return f"{kind}-{year}-{counter.value:04d}"


def record(db, organization_id, entity_type, entity_id, action, from_status, to_status, actor_id, reason=None, detail=None):
    db.add(QualityStatusHistory(organization_id=organization_id, entity_type=entity_type, entity_id=entity_id, action=action,
                                from_status=from_status, to_status=to_status, reason=reason, detail=detail, actor_user_id=actor_id))


def history(db, organization_id, entity_type, entity_id) -> list[dict]:
    rows = list(db.scalars(select(QualityStatusHistory).where(
        QualityStatusHistory.organization_id == organization_id, QualityStatusHistory.entity_type == entity_type,
        QualityStatusHistory.entity_id == entity_id).order_by(QualityStatusHistory.created_at, QualityStatusHistory.id)))
    names = user_names(db, organization_id, [r.actor_user_id for r in rows])
    return [dict(action=r.action, from_status=r.from_status, to_status=r.to_status, reason=r.reason, detail=r.detail,
                 actor_name=names.get(r.actor_user_id), at=r.created_at) for r in rows]


def log_activity(db, organization_id, actor_id, action, entity_type, entity_id, name):
    """The tenant activity log (best effort, after the business commit), like the other modules."""
    try:
        get_registered_activity_logger().log_activity(db, organization_id, action, entity_type, entity_id, name, actor_id)
        db.commit()
    except Exception:  # noqa: BLE001 - logging never fails the business action
        db.rollback()


def as_decimal(value) -> Decimal:
    return Decimal(str(value or 0))


__all__ = ["ProductionReads", "CommercialReads", "ShippingReads", "ProcurementReads", "user_names", "next_code", "record", "history", "log_activity", "as_decimal"]
