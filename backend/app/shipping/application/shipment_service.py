"""Shipments (SHIP-001, SHIP-004): the single writer of a delivery note, its lines and its lifecycle.

draft ─ready→ ready ─dispatch→ dispatched ─deliver→ delivered | partially_delivered; ─fail→ returned ─reschedule→ ready
(attempt 2 …) or ─close→ not_delivered; a pickup is delivered from ready; draft and ready (first attempt) can be
cancelled with a reason. What does not reach the customer opens a delivery return (ReturnService). Every step writes
a shipment event (history and notification outbox) and the activity log.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.units import to_kilograms
from app.core.utils import utc_now
from app.shipping.domain import permissions as P
from app.shipping.domain import returns as R
from app.shipping.domain import rules
from app.shipping.domain.rules import ShippingError
from app.shipping.infrastructure.models import Shipment, ShipmentLine, ShipmentReturn
from .return_service import ReturnService, available, taken_back
from .support import (CustomerReads, ProductionOrderReads, attachments, history, log_activity, next_number, record, settings,
                      user_names)

HEADER = ("delivery_method", "shipment_date", "customer_reference", "consignee_name", "consignee_email", "notify_consignee",
          "delivery_address", "delivery_city", "location_url", "driver_name", "driver_id_no", "vehicle_plate", "vehicle_type",
          "carrier_name", "tracking_no", "notes")
PHONES = ("consignee_phone", "driver_phone")
# What a rescheduled note may change: who carries it, and when (never its customer or its lines).
TRANSPORT = ("delivery_method", "shipment_date", "driver_name", "driver_phone", "driver_id_no", "vehicle_plate", "vehicle_type",
             "carrier_name", "tracking_no")
LINE_FIELDS = ("description", "width_mm", "thickness_mm", "quantity", "unit", "weight", "weight_unit", "production_order_id")


def _kg(value, unit):
    return to_kilograms(value, unit).quantize(Decimal("0.001")) if value is not None else None


class ShipmentService:
    def __init__(self, db, tenant):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id
        self.customers = CustomerReads(db, self.org)
        self.orders = ProductionOrderReads(db, self.org)
        self.returns = ReturnService(db, tenant)

    # ── reads ───────────────────────────────────────────────────────────────────────────────────
    def _get(self, shipment_id, lock=False) -> Shipment:
        query = select(Shipment).options(selectinload(Shipment.lines)).where(Shipment.id == shipment_id, Shipment.organization_id == self.org)
        shipment = self.db.scalar(query.with_for_update() if lock else query)
        if shipment is None:
            raise ShippingError("SHIPMENT_NOT_FOUND", 404)
        return shipment

    def get(self, shipment_id) -> Shipment:
        return self._get(shipment_id)

    def list(self, status=None, method=None, customer_id=None, date_from=None, date_to=None, search=None, limit=500):
        query = select(Shipment).options(selectinload(Shipment.lines)).where(Shipment.organization_id == self.org)
        for column, value in ((Shipment.status, status), (Shipment.delivery_method, method), (Shipment.customer_id, customer_id)):
            if value:
                query = query.where(column == value)
        if date_from:
            query = query.where(Shipment.shipment_date >= date_from)
        if date_to:
            query = query.where(Shipment.shipment_date <= date_to)
        if search:
            query = query.where(Shipment.shipment_no.icontains(search, autoescape=True) | Shipment.customer_name.icontains(search, autoescape=True)
                                | Shipment.customer_reference.icontains(search, autoescape=True) | Shipment.vehicle_plate.icontains(search, autoescape=True))
        return list(self.db.scalars(query.order_by(Shipment.shipment_date.desc(), Shipment.created_at.desc()).limit(limit)))

    def _returns_of(self, shipments) -> dict:
        ids = [s.id for s in shipments]
        found = list(self.db.scalars(select(ShipmentReturn).options(selectinload(ShipmentReturn.lines))
                                     .where(ShipmentReturn.organization_id == self.org, ShipmentReturn.shipment_id.in_(ids))
                                     .order_by(ShipmentReturn.created_at))) if ids else []
        out: dict = {i: [] for i in ids}
        for r in found:
            out[r.shipment_id].append(r)
        return out

    @staticmethod
    def _back_at_factory(returns) -> bool:
        """No delivery return still on its way back."""
        return not any(r.kind == R.DELIVERY and r.status == R.APPROVED for r in returns)

    def views(self, shipments, can, detail=False) -> list[dict]:
        names = user_names(self.db, self.org, [u for s in shipments for u in (s.created_by_user_id, s.dispatched_by_user_id, s.delivered_recorded_by_user_id)])
        returns_by = self._returns_of(shipments)
        tolerance = settings(self.db, self.org).weight_tolerance_pct if detail else None
        out = []
        for s in shipments:
            totals, returns = rules.totals(s.lines), returns_by[s.id]
            left = available(s, returns)
            view = dict(created_by_name=names.get(s.created_by_user_id), dispatched_by_name=names.get(s.dispatched_by_user_id),
                        delivered_recorded_by_name=names.get(s.delivered_recorded_by_user_id),
                        quantities=[dict(unit=u, quantity=q) for u, q in totals["quantities"].items()], weight_total_kg=totals["weight_kg"],
                        missing_details=rules.method_gaps(s) if s.status == rules.DRAFT else [],
                        open_returns=sum(1 for r in returns if r.status in R.OPEN),
                        actions=rules.actions(s.status, s.delivery_method, lambda a: can(P.SHIPMENT_ACTIONS[a]), s.attempt,
                                              self._back_at_factory(returns), any(q > 0 for q in left.values())))
            if detail:
                back = taken_back(returns)
                view.update(history=history(self.db, self.org, shipment_id=s.id), attachments=attachments(self.db, self.org, shipment_id=s.id),
                            returns=[dict(id=r.id, return_no=r.return_no, kind=r.kind, status=r.status, reason=r.reason, attempt=r.attempt,
                                          requested_at=r.requested_at) for r in returns],
                            line_returns={str(line.id): dict(returned=back.get(line.id, Decimal("0")), returnable=left.get(line.id, Decimal("0")))
                                          for line in s.lines},
                            weight_check=rules.weight_check(totals["weight_kg"], s.gate_weight_kg, s.received_weight_kg, tolerance))
            out.append(view)
        return out

    def customer_options(self, text=""):
        return self.customers.search(text)

    def production_order_options(self, text=""):
        return self.orders.search(text)

    # ── writes ──────────────────────────────────────────────────────────────────────────────────
    def _apply(self, shipment, values: dict, fields=HEADER):
        values = dict(values)
        if "customer_id" in values:
            shipment.customer_id = None
            if values["customer_id"]:
                customer = self.customers.get(values["customer_id"])
                shipment.customer_id = customer["id"]
                if not (values.get("customer_name") or "").strip():
                    values["customer_name"] = customer["name"]
                # A registered customer's contacts fill the recipient's when those are left empty.
                for field, source in (("consignee_phone", "phone"), ("consignee_email", "email"), ("delivery_city", "city")):
                    if not values.get(field) and not getattr(shipment, field) and customer[source]:
                        values[field] = customer[source]
                        if field == "consignee_phone":
                            try:  # a stored phone in another format is simply not copied (a typed one is still validated)
                                rules.normalize_phone(customer[source])
                            except ShippingError:
                                values[field] = None
        if values.get("customer_name") is not None:
            shipment.customer_name = values["customer_name"].strip()
        for field in fields:
            if field in values and field not in PHONES and not (field in ("notify_consignee", "delivery_method", "shipment_date") and values[field] is None):
                setattr(shipment, field, values[field])
        for field in PHONES:
            if field in values:
                setattr(shipment, field, rules.normalize_phone(values[field]))
        if shipment.delivery_method == rules.CARRIER:
            shipment.driver_name = shipment.driver_phone = shipment.driver_id_no = None
        else:
            shipment.carrier_name = shipment.tracking_no = None

    def _write_lines(self, shipment, lines):
        numbers = self.orders.numbers([data.production_order_id for data in lines])
        shipment.lines.clear()
        self.db.flush()
        for number, data in enumerate(lines, 1):
            line = ShipmentLine(line_no=number, **{f: getattr(data, f) for f in LINE_FIELDS})
            if line.production_order_id is not None:
                if line.production_order_id not in numbers:
                    raise ShippingError("PRODUCTION_ORDER_NOT_FOUND", 404, line=number)
                line.production_order_no = numbers[line.production_order_id]
            rules.assert_line(line)
            shipment.lines.append(line)

    def create(self, data) -> Shipment:
        values = data.model_dump(exclude={"lines"})
        if not values.get("customer_id") and not (values.get("customer_name") or "").strip():
            raise ShippingError("CUSTOMER_REQUIRED", 400)
        shipment = Shipment(organization_id=self.org, shipment_no=next_number(self.db, self.org), status=rules.DRAFT, attempt=1,
                            delivery_method=data.delivery_method, shipment_date=data.shipment_date, customer_name="",
                            created_by_user_id=self.tenant.user_id)
        self._apply(shipment, values)
        self.db.add(shipment)
        self.db.flush()
        self._write_lines(shipment, data.lines)
        record(self.db, shipment, "shipment.created", None, rules.DRAFT, self.tenant.user_id)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "shipment.created", shipment.id, shipment.shipment_no)
        return self._get(shipment.id)

    def update(self, shipment_id, data) -> Shipment:
        shipment = self._get(shipment_id, lock=True)
        rules.assert_editable(shipment.status)
        values = data.model_dump(exclude_unset=True, exclude={"lines"})
        if "customer_name" in values and not (values["customer_name"] or "").strip() and not (values.get("customer_id") or shipment.customer_id):
            raise ShippingError("CUSTOMER_REQUIRED", 400)
        self._apply(shipment, values)
        if data.lines is not None:
            self._write_lines(shipment, data.lines)
        self.db.commit()
        return self._get(shipment.id)

    def _move(self, shipment, to_status, event, reason=None, before=None):
        before = before or shipment.status
        shipment.status = to_status
        record(self.db, shipment, event, before, to_status, self.tenant.user_id, reason)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, event, shipment.id, shipment.shipment_no)
        return self._get(shipment.id)

    def ready(self, shipment_id) -> Shipment:
        shipment = self._get(shipment_id, lock=True)
        rules.assert_ready(shipment, len(shipment.lines))
        shipment.ready_at = utc_now()
        return self._move(shipment, rules.READY, "shipment.ready")

    def reopen(self, shipment_id) -> Shipment:
        shipment = self._get(shipment_id, lock=True)
        rules.assert_can_reopen(shipment.status, shipment.attempt)
        shipment.ready_at = None
        return self._move(shipment, rules.DRAFT, "shipment.reopened")

    def dispatch(self, shipment_id, data=None) -> Shipment:
        shipment = self._get(shipment_id, lock=True)
        rules.assert_can_dispatch(shipment.status, shipment.delivery_method)
        shipment.dispatched_at, shipment.dispatched_by_user_id = utc_now(), self.tenant.user_id
        shipment.gate_weight_kg = _kg(data.gate_weight, data.gate_weight_unit) if data is not None else None
        return self._move(shipment, rules.DISPATCHED, "shipment.dispatched")

    def deliver(self, shipment_id, data) -> Shipment:
        """Received in full, or in part: the refused part rides back with the driver as a delivery return."""
        shipment = self._get(shipment_id, lock=True)
        rules.assert_can_deliver(shipment.status, shipment.delivery_method, data.received_by_name)
        refused = rules.split_delivery(shipment.lines, {item.line_id: item.delivered_quantity for item in data.lines}, shipment.delivery_method)
        if refused:
            if not data.refusal_reason:
                raise ShippingError("REFUSAL_REASON_REQUIRED", 400)
            self.returns.open_delivery_return(shipment, data.refusal_reason or "", data.refusal_details, refused)
        short = dict((line.id, quantity) for line, quantity in refused)
        for line in shipment.lines:
            line.delivered_quantity = line.quantity - short.get(line.id, Decimal("0"))
        shipment.delivered_at = data.received_at or utc_now()
        shipment.received_by_name, shipment.delivery_notes = data.received_by_name.strip(), data.delivery_notes
        shipment.received_weight_kg = _kg(data.received_weight, data.received_weight_unit)
        shipment.delivered_recorded_by_user_id = self.tenant.user_id
        if shipment.delivery_method == rules.PICKUP:
            shipment.dispatched_at = shipment.delivered_at  # collected at the gate: it left when it was received
        return self._move(shipment, rules.PARTIALLY_DELIVERED if refused else rules.DELIVERED,
                          "shipment.partially_delivered" if refused else "shipment.delivered")

    def fail(self, shipment_id, data) -> Shipment:
        """Not received: the whole load comes back to the factory under a delivery return."""
        shipment = self._get(shipment_id, lock=True)
        rules.assert_can_fail(shipment.status, data.reason)
        R.assert_reason(R.DELIVERY, data.reason, data.details)
        self.returns.open_delivery_return(shipment, data.reason, data.details, [(line, line.quantity) for line in shipment.lines])
        shipment.failed_at = utc_now()
        return self._move(shipment, rules.RETURNED, "shipment.returned", (data.details or "").strip() or data.reason)

    def reschedule(self, shipment_id, data) -> Shipment:
        """The same note sets out again (attempt n + 1), possibly with another driver, vehicle, carrier or date."""
        shipment = self._get(shipment_id, lock=True)
        rules.assert_can_reschedule(shipment.status, self._back_at_factory(self.returns.for_shipment(shipment.id)))
        self._apply(shipment, data.model_dump(exclude_unset=True), TRANSPORT)
        missing = rules.method_gaps(shipment)
        if missing:
            raise ShippingError("METHOD_DETAILS_REQUIRED", 400, fields=",".join(missing))
        shipment.attempt += 1
        shipment.ready_at, shipment.dispatched_at, shipment.dispatched_by_user_id, shipment.gate_weight_kg = utc_now(), None, None, None
        return self._move(shipment, rules.READY, "shipment.rescheduled")

    def close(self, shipment_id, reason) -> Shipment:
        """Not delivered after all: the goods stay at the factory, the note is closed."""
        shipment = self._get(shipment_id, lock=True)
        rules.assert_can_close(shipment.status, shipment.attempt, self._back_at_factory(self.returns.for_shipment(shipment.id)), reason)
        shipment.close_reason = reason.strip()
        return self._move(shipment, rules.NOT_DELIVERED, "shipment.closed", shipment.close_reason)

    def cancel(self, shipment_id, reason) -> Shipment:
        shipment = self._get(shipment_id, lock=True)
        rules.assert_can_cancel(shipment.status, reason, shipment.attempt)
        shipment.cancel_reason = reason.strip()
        return self._move(shipment, rules.CANCELLED, "shipment.cancelled", reason.strip())

    # ── settings ────────────────────────────────────────────────────────────────────────────────
    def settings(self):
        current = settings(self.db, self.org)
        self.db.commit()
        return current

    def update_settings(self, data):
        current = settings(self.db, self.org)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(current, field, value)
        self.db.commit()
        return current
