"""Reads shipping needs from other modules, numbering and the event log (SHIP-001, SHIP-004).

Customers, production orders and user names are read through the shared tables (Base.metadata), never by importing
another module's models (ADR-004). What a document prints is copied onto it, so it keeps what it printed.
"""
from sqlalchemy import select

from app.core.db import Base
from app.core.interfaces.activity_log import get_registered_activity_logger
from app.core.utils import utc_now
from app.shipping.domain import returns as R
from app.shipping.domain import rules
from app.shipping.infrastructure.models import (ShipmentEvent, ShippingAttachment, ShippingCodeCounter, ShippingReturnCounter,
                                                ShippingSettings)


def _t(name):
    return Base.metadata.tables[name]


class CustomerReads:
    """The organization's registered customers, as a shipment needs them (name and contacts)."""

    def __init__(self, db, organization_id):
        self.db, self.org = db, organization_id

    def _query(self):
        customers = _t("commercial_customers")
        return customers, select(customers.c.id, customers.c.customer_code, customers.c.name, customers.c.phone, customers.c.email,
                                 customers.c.city).where(customers.c.organization_id == self.org)

    def get(self, customer_id) -> dict:
        customers, query = self._query()
        row = self.db.execute(query.where(customers.c.id == customer_id)).first()
        if row is None:
            raise rules.ShippingError("CUSTOMER_NOT_FOUND", 404)
        return dict(row._mapping)

    def search(self, text: str = "", limit: int = 30) -> list[dict]:
        customers, query = self._query()
        if text:
            query = query.where(customers.c.name.icontains(text, autoescape=True) | customers.c.customer_code.icontains(text, autoescape=True))
        return [dict(r._mapping) for r in self.db.execute(query.order_by(customers.c.name).limit(limit)).all()]


class ProductionOrderReads:
    """The production orders goods are shipped from (their number is the batch a complaint is traced back to)."""
    HIDDEN = ("draft", "cancelled")

    def __init__(self, db, organization_id):
        self.db, self.org = db, organization_id

    def _query(self):
        orders = _t("production_orders")
        return orders, select(orders.c.id, orders.c.production_order_number.label("number"), orders.c.product_type, orders.c.status,
                              orders.c.planned_quantity, orders.c.unit).where(orders.c.organization_id == self.org)

    def numbers(self, ids) -> dict:
        orders, query = self._query()
        ids = [i for i in set(ids) if i]
        return {r.id: r.number for r in self.db.execute(query.where(orders.c.id.in_(ids))).all()} if ids else {}

    def search(self, text: str = "", limit: int = 30) -> list[dict]:
        orders, query = self._query()
        query = query.where(orders.c.status.notin_(self.HIDDEN))
        if text:
            query = query.where(orders.c.production_order_number.icontains(text, autoescape=True) | orders.c.product_type.icontains(text, autoescape=True))
        rows = self.db.execute(query.order_by(orders.c.planned_start_date.desc(), orders.c.production_order_number.desc()).limit(limit)).all()
        return [dict(r._mapping, status=getattr(r.status, "value", r.status)) for r in rows]


class QualityReads:
    """What quality did with returned goods: its inspections and decided parts for a return (read only)."""

    def __init__(self, db, organization_id):
        self.db, self.org = db, organization_id

    def of(self, return_ids) -> dict:
        """return id -> {"inspections": [...], "decisions": [...]}."""
        ids = [i for i in set(return_ids) if i]
        out = {i: dict(inspections=[], decisions=[]) for i in ids}
        if not ids:
            return out
        checks, rejections = _t("quality_checks"), _t("quality_rejections")
        for r in self.db.execute(select(checks.c.id, checks.c.inspection_code, checks.c.status, checks.c.result, checks.c.return_id,
                                        checks.c.return_line_id, checks.c.qty_inspected, checks.c.qty_accepted)
                                 .where(checks.c.organization_id == self.org, checks.c.return_id.in_(ids)).order_by(checks.c.created_at)).all():
            out[r.return_id]["inspections"].append(dict(id=r.id, inspection_code=r.inspection_code, status=_value(r.status), result=_value(r.result),
                                                        return_line_id=r.return_line_id, qty_inspected=r.qty_inspected, qty_accepted=r.qty_accepted))
        for r in self.db.execute(select(rejections.c.id, rejections.c.rejection_code, rejections.c.disposition, rejections.c.disposition_status,
                                        rejections.c.quantity_rejected, rejections.c.unit, rejections.c.return_id, rejections.c.return_line_id)
                                 .where(rejections.c.organization_id == self.org, rejections.c.return_id.in_(ids)).order_by(rejections.c.created_at)).all():
            out[r.return_id]["decisions"].append(dict(id=r.id, rejection_code=r.rejection_code, disposition=_value(r.disposition),
                                                      disposition_status=_value(r.disposition_status), quantity=r.quantity_rejected, unit=r.unit,
                                                      return_line_id=r.return_line_id))
        return out


def _value(v):
    return getattr(v, "value", v)


def user_names(db, organization_id, user_ids) -> dict:
    users = _t("foundation_users")
    ids = [i for i in set(user_ids) if i]
    return dict(db.execute(select(users.c.id, users.c.full_name).where(users.c.organization_id == organization_id, users.c.id.in_(ids))).all()) if ids else {}


def settings(db, organization_id) -> ShippingSettings:
    current = db.get(ShippingSettings, organization_id)
    if current is None:
        current = ShippingSettings(organization_id=organization_id, note_prefix=rules.DEFAULT_PREFIX, return_prefix=R.DEFAULT_PREFIX,
                                   return_window_days=R.DEFAULT_WINDOW_DAYS, weight_tolerance_pct=R.DEFAULT_TOLERANCE_PCT)
        db.add(current)
        db.flush()
    return current


def _next(db, model, organization_id, prefix) -> str:
    """PREFIX-YYYY-NNNN from a locked per-organization, per-year counter: never repeated under concurrency."""
    year = utc_now().year
    counter = db.get(model, (organization_id, year), with_for_update=True)
    if counter is None:
        counter = model(organization_id=organization_id, year=year, value=0)
        db.add(counter)
    counter.value += 1
    db.flush()
    return rules.number(prefix, year, counter.value)


def next_number(db, organization_id) -> str:
    return _next(db, ShippingCodeCounter, organization_id, settings(db, organization_id).note_prefix)


def next_return_number(db, organization_id) -> str:
    return _next(db, ShippingReturnCounter, organization_id, settings(db, organization_id).return_prefix)


def record(db, shipment, event_type, from_status, to_status, actor_id, reason=None, shipment_return=None):
    """History and outbox in one row: what happened, and what a notification would need (nothing is sent here)."""
    payload = dict(shipment_no=shipment.shipment_no, status=shipment.status, attempt=shipment.attempt, delivery_method=shipment.delivery_method,
                   customer_name=shipment.customer_name, consignee_name=shipment.consignee_name, consignee_phone=shipment.consignee_phone,
                   consignee_email=shipment.consignee_email, notify=shipment.notify_consignee)
    if shipment_return is not None:
        payload.update(return_no=shipment_return.return_no, return_kind=shipment_return.kind, return_status=to_status,
                       return_reason=shipment_return.reason, responsibility=shipment_return.responsibility)
    db.add(ShipmentEvent(organization_id=shipment.organization_id, shipment_id=shipment.id, return_id=getattr(shipment_return, "id", None),
                         event_type=event_type, from_status=from_status, to_status=to_status, reason=reason, actor_user_id=actor_id,
                         payload=payload))


def history(db, organization_id, shipment_id=None, return_id=None) -> list[dict]:
    """A shipment's history includes its returns'; a return's history is its own."""
    query = select(ShipmentEvent).where(ShipmentEvent.organization_id == organization_id)
    query = query.where(ShipmentEvent.return_id == return_id) if return_id else query.where(ShipmentEvent.shipment_id == shipment_id)
    rows = list(db.scalars(query.order_by(ShipmentEvent.occurred_at, ShipmentEvent.id)))
    names = user_names(db, organization_id, [r.actor_user_id for r in rows])
    out = []
    for r in rows:
        group, step = r.event_type.split(".", 1)
        out.append(dict(action=step if group == "shipment" else f"{group}_{step}", from_status=r.from_status, to_status=r.to_status,
                        reason=r.reason, actor_name=names.get(r.actor_user_id), at=r.occurred_at,
                        return_no=(r.payload or {}).get("return_no") if r.return_id else None))
    return out


def attachments(db, organization_id, shipment_id=None, return_id=None) -> list[dict]:
    query = select(ShippingAttachment).where(ShippingAttachment.organization_id == organization_id)
    query = query.where(ShippingAttachment.return_id == return_id) if return_id else query.where(
        ShippingAttachment.shipment_id == shipment_id, ShippingAttachment.return_id.is_(None))
    rows = list(db.scalars(query.order_by(ShippingAttachment.uploaded_at)))
    names = user_names(db, organization_id, [r.uploaded_by_user_id for r in rows])
    return [dict(id=r.id, kind=r.kind, file_name=r.file_name, content_type=r.content_type, size_bytes=r.size_bytes,
                 uploaded_by_name=names.get(r.uploaded_by_user_id), uploaded_at=r.uploaded_at) for r in rows]


def log_activity(db, organization_id, actor_id, action, entity_id, name, entity="shipment"):
    """The tenant activity log (best effort, after the business commit), like the other modules."""
    try:
        get_registered_activity_logger().log_activity(db, organization_id, action, entity, entity_id, name, actor_id)
        db.commit()
    except Exception:  # noqa: BLE001 - logging never fails the business action
        db.rollback()
