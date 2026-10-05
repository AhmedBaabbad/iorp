"""Returns (SHIP-004): the single writer of a return, its lines and its lifecycle.

A delivery return is opened by the shipment's delivery outcome (ShipmentService.deliver / fail), already approved;
a customer return is registered here against a delivered note. Each step writes an event on the note (history and
notification outbox) and the activity log. The delivery note itself is never changed by a return.
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
from app.shipping.infrastructure.models import Shipment, ShipmentReturn, ShipmentReturnLine
from .support import QualityReads, attachments, history, log_activity, next_return_number, record, settings, user_names

ZERO = Decimal("0")


def taken_back(returns) -> dict:
    """shipment line id -> what the customer's returns (not rejected or cancelled) take back: the received quantity
    once received, the requested one before."""
    out: dict = {}
    for ret in returns:
        if ret.kind != R.CUSTOMER or ret.status in R.VOID:
            continue
        for line in ret.lines:
            quantity = line.received_quantity if ret.status == R.RECEIVED else line.quantity
            out[line.shipment_line_id] = out.get(line.shipment_line_id, ZERO) + (quantity or ZERO)
    return out


def available(shipment, returns) -> dict:
    """shipment line id -> what the customer may still return (nothing unless the goods were received)."""
    if shipment.status not in rules.RECEIVED:
        return {}
    back = taken_back(returns)
    return {line.id: R.returnable(line.delivered_quantity, back.get(line.id, ZERO)) for line in shipment.lines}


class ReturnService:
    def __init__(self, db, tenant):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id

    # ── reads ───────────────────────────────────────────────────────────────────────────────────
    def _query(self):
        return select(ShipmentReturn).options(selectinload(ShipmentReturn.lines)).where(ShipmentReturn.organization_id == self.org)

    def _get(self, return_id, lock=False) -> ShipmentReturn:
        query = self._query().where(ShipmentReturn.id == return_id)
        found = self.db.scalar(query.with_for_update() if lock else query)
        if found is None:
            raise ShippingError("RETURN_NOT_FOUND", 404)
        return found

    def get(self, return_id) -> ShipmentReturn:
        return self._get(return_id)

    def _shipment(self, shipment_id, lock=False) -> Shipment:
        query = select(Shipment).options(selectinload(Shipment.lines)).where(Shipment.id == shipment_id, Shipment.organization_id == self.org)
        shipment = self.db.scalar(query.with_for_update() if lock else query)
        if shipment is None:
            raise ShippingError("SHIPMENT_NOT_FOUND", 404)
        return shipment

    def for_shipment(self, shipment_id) -> list[ShipmentReturn]:
        return list(self.db.scalars(self._query().where(ShipmentReturn.shipment_id == shipment_id).order_by(ShipmentReturn.created_at)))

    def list(self, status=None, kind=None, shipment_id=None, customer_id=None, date_from=None, date_to=None, search=None, limit=500):
        query = self._query()
        for column, value in ((ShipmentReturn.status, status), (ShipmentReturn.kind, kind), (ShipmentReturn.shipment_id, shipment_id),
                              (ShipmentReturn.customer_id, customer_id)):
            if value:
                query = query.where(column == value)
        if date_from:
            query = query.where(ShipmentReturn.requested_at >= date_from)
        if date_to:
            query = query.where(ShipmentReturn.requested_at < date_to)
        if search:
            notes = select(Shipment.id).where(Shipment.organization_id == self.org, Shipment.shipment_no.icontains(search, autoescape=True))
            query = query.where(ShipmentReturn.return_no.icontains(search, autoescape=True) | ShipmentReturn.customer_name.icontains(search, autoescape=True)
                                | ShipmentReturn.customer_reference.icontains(search, autoescape=True) | ShipmentReturn.shipment_id.in_(notes))
        return list(self.db.scalars(query.order_by(ShipmentReturn.created_at.desc()).limit(limit)))

    def views(self, found, can, detail=False) -> list[dict]:
        shipments = {s.id: s for s in self.db.scalars(select(Shipment).where(Shipment.id.in_({r.shipment_id for r in found})))} if found else {}
        names = user_names(self.db, self.org, [u for r in found for u in (r.created_by_user_id, r.decided_by_user_id, r.received_by_user_id)])
        quality = QualityReads(self.db, self.org).of([r.id for r in found if r.status == R.RECEIVED and r.quality_required])
        out = []
        for r in found:
            shipment = shipments[r.shipment_id]
            expected = [to_kilograms(line.weight, line.weight_unit) for line in r.lines if line.weight is not None]
            received = [to_kilograms(line.received_weight, line.weight_unit) for line in r.lines if line.received_weight is not None]
            quantities: dict = {}
            for line in r.lines:
                quantities[line.unit] = quantities.get(line.unit, ZERO) + line.quantity
            view = dict(shipment_no=shipment.shipment_no, delivery_method=shipment.delivery_method, delivered_at=shipment.delivered_at,
                        created_by_name=names.get(r.created_by_user_id), decided_by_name=names.get(r.decided_by_user_id),
                        received_by_name=names.get(r.received_by_user_id),
                        quantities=[dict(unit=u, quantity=q) for u, q in quantities.items()],
                        weight_kg=sum(expected, ZERO).quantize(Decimal("0.001")) if expected else None,
                        received_weight_kg=sum(received, ZERO).quantize(Decimal("0.001")) if received else None,
                        quality_status=R.quality_status(r.status == R.RECEIVED, r.quality_required,
                                                        sum(1 for line in r.lines if (line.received_quantity or ZERO) > ZERO),
                                                        quality.get(r.id, {}).get("inspections", []), quality.get(r.id, {}).get("decisions", [])),
                        actions=R.actions(r.kind, r.status, lambda a: can(P.RETURN_ACTIONS[a])))
            if detail:
                view["history"] = history(self.db, self.org, return_id=r.id)
                view["attachments"] = attachments(self.db, self.org, return_id=r.id)
                view["quality"] = dict(expected=R.needs_quality(r.reason), **quality.get(r.id, dict(inspections=[], decisions=[])))
            out.append(view)
        return out

    # ── writes ──────────────────────────────────────────────────────────────────────────────────
    def _new(self, shipment, kind, status, reason, details, quantities, weights=None, **extra) -> ShipmentReturn:
        """quantities: [(shipment line, quantity)]; weights: shipment line id -> weight (else in proportion)."""
        R.assert_reason(kind, reason, details)
        now = utc_now()
        late = kind == R.CUSTOMER and R.is_late(shipment.delivered_at, now, settings(self.db, self.org).return_window_days)
        ret = ShipmentReturn(organization_id=self.org, return_no=next_return_number(self.db, self.org), kind=kind, status=status,
                             shipment_id=shipment.id, attempt=shipment.attempt, customer_id=shipment.customer_id,
                             customer_name=shipment.customer_name, reason=reason,
                             responsibility=R.responsibility(kind, reason, shipment.delivery_method), details=(details or "").strip() or None,
                             requested_at=now, is_late=late, created_by_user_id=self.tenant.user_id, **extra)
        for number, (line, quantity) in enumerate(quantities, 1):
            weight = (weights or {}).get(line.id)
            ret.lines.append(ShipmentReturnLine(
                shipment_line_id=line.id, line_no=number, description=line.description, width_mm=line.width_mm, thickness_mm=line.thickness_mm,
                unit=line.unit, weight_unit=line.weight_unit, production_order_no=line.production_order_no, quantity=quantity,
                weight=weight if weight is not None else R.share(line.weight, quantity, line.quantity)))
        self.db.add(ret)
        self.db.flush()
        record(self.db, shipment, f"return.{'opened' if kind == R.DELIVERY else 'requested'}", None, status, self.tenant.user_id,
               ret.details, ret)
        return ret

    def open_delivery_return(self, shipment, reason, details, quantities) -> ShipmentReturn:
        """Not received at the door: nothing to approve, the goods are coming back. The caller commits."""
        return self._new(shipment, R.DELIVERY, R.APPROVED, reason, details, quantities)

    def create(self, data) -> ShipmentReturn:
        shipment = self._shipment(data.shipment_id, lock=True)
        if shipment.status not in rules.RECEIVED:
            raise ShippingError("SHIPMENT_NOT_DELIVERED", shipment_status=shipment.status)
        lines = {line.id: line for line in shipment.lines}
        wanted = {}
        for item in data.lines:
            wanted[item.shipment_line_id] = wanted.get(item.shipment_line_id, ZERO) + item.quantity
        R.assert_quantities(wanted, available(shipment, self.for_shipment(shipment.id)), {i: l.line_no for i, l in lines.items()})
        weights = {item.shipment_line_id: item.weight for item in data.lines if item.weight is not None}
        ret = self._new(shipment, R.CUSTOMER, R.REQUESTED, data.reason, data.details,
                        [(lines[i], q) for i, q in sorted(wanted.items(), key=lambda kv: lines[kv[0]].line_no)], weights,
                        customer_reference=data.customer_reference, carrier_claim_ref=data.carrier_claim_ref)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "return.requested", ret.id, ret.return_no, "shipment_return")
        return self._get(ret.id)

    def _move(self, ret, to_status, event, reason=None):
        before = ret.status
        ret.status = to_status
        record(self.db, self._shipment(ret.shipment_id), event, before, to_status, self.tenant.user_id, reason, ret)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, event, ret.id, ret.return_no, "shipment_return")
        return self._get(ret.id)

    def approve(self, return_id, note) -> ShipmentReturn:
        ret = self._get(return_id, lock=True)
        R.assert_can_approve(ret.status, ret.is_late, note)
        ret.decided_at, ret.decided_by_user_id, ret.decision_note = utc_now(), self.tenant.user_id, (note or "").strip() or None
        return self._move(ret, R.APPROVED, "return.approved", ret.decision_note)

    def reject(self, return_id, reason) -> ShipmentReturn:
        ret = self._get(return_id, lock=True)
        R.assert_can_reject(ret.status, reason)
        ret.decided_at, ret.decided_by_user_id, ret.decision_note = utc_now(), self.tenant.user_id, reason.strip()
        return self._move(ret, R.REJECTED, "return.rejected", ret.decision_note)

    def receive(self, return_id, data) -> ShipmentReturn:
        """The goods are back at the factory: what actually arrived (all that was expected unless said otherwise)."""
        ret = self._get(return_id, lock=True)
        given = {item.return_line_id: item for item in data.lines}
        R.assert_can_receive(ret.status, {i: item.received_quantity for i, item in given.items()}, {line.id: line.quantity for line in ret.lines})
        for line in ret.lines:
            item = given.get(line.id)
            line.received_quantity = item.received_quantity if item else line.quantity
            line.received_weight = item.received_weight if item and item.received_weight is not None else (
                line.weight if line.received_quantity == line.quantity else R.share(line.weight, line.received_quantity, line.quantity))
        ret.received_at, ret.received_by_user_id = data.received_at or utc_now(), self.tenant.user_id
        ret.receipt_notes = (data.notes or "").strip() or None
        # Quality inspects what came back when the reason requires it or the warehouse sends it; else it is back in stock.
        ret.quality_required = R.needs_quality(ret.reason) or bool(data.send_to_quality)
        if not any((line.received_quantity or ZERO) > ZERO for line in ret.lines):
            ret.quality_required = False  # nothing arrived: nothing to inspect
        return self._move(ret, R.RECEIVED, "return.received", ret.receipt_notes)

    def cancel(self, return_id, reason) -> ShipmentReturn:
        ret = self._get(return_id, lock=True)
        R.assert_can_cancel(ret.kind, ret.status, reason)
        ret.cancel_reason = reason.strip()
        return self._move(ret, R.CANCELLED, "return.cancelled", ret.cancel_reason)
