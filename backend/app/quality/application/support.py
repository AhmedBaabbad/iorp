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

    def order(self, order_id, *, lock=False, inspectable=False) -> OrderRef:
        orders = _t("production_orders")
        query = select(orders.c.id, orders.c.production_order_number, orders.c.product_type, orders.c.status, orders.c.unit).where(
            orders.c.id == order_id, orders.c.organization_id == self.org)
        row = self.db.execute(query.with_for_update() if lock else query).first()
        if row is None:
            raise QualityError("PRODUCTION_ORDER_NOT_FOUND", 404)
        ref = OrderRef(row.id, row.production_order_number, row.product_type, getattr(row.status, "value", row.status), row.unit)
        if inspectable and ref.status not in ORDER_STATUSES:
            raise QualityError("ORDER_NOT_INSPECTABLE", order_status=ref.status)
        return ref

    def item(self, order_id, item_id) -> ItemRef:
        items = _t("production_order_items")
        row = self.db.execute(select(items.c.id, items.c.line_no, items.c.unit).where(
            items.c.id == item_id, items.c.production_order_id == order_id)).first()
        if row is None:
            raise QualityError("ORDER_ITEM_NOT_FOUND", 404)
        return ItemRef(row.id, row.line_no, row.unit)

    def numbers(self, order_ids) -> dict:
        orders = _t("production_orders")
        ids = [i for i in set(order_ids) if i]
        return dict(self.db.execute(select(orders.c.id, orders.c.production_order_number).where(
            orders.c.organization_id == self.org, orders.c.id.in_(ids))).all()) if ids else {}

    def line_numbers(self, item_ids) -> dict:
        items = _t("production_order_items")
        ids = [i for i in set(item_ids) if i]
        return dict(self.db.execute(select(items.c.id, items.c.line_no).where(items.c.id.in_(ids))).all()) if ids else {}

    def inspectable_orders(self, search: str = "", limit: int = 50) -> list[dict]:
        """Orders a check can be opened on (running, held, completed), with their lines, newest first."""
        orders, items = _t("production_orders"), _t("production_order_items")
        query = select(orders.c.id, orders.c.production_order_number, orders.c.product_type, orders.c.status, orders.c.unit).where(
            orders.c.organization_id == self.org, orders.c.status.in_(sorted(ORDER_STATUSES)))
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


__all__ = ["ProductionReads", "CommercialReads", "user_names", "next_code", "record", "history", "log_activity", "as_decimal"]
