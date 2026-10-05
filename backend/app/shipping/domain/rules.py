"""Shipments and delivery notes (SHIP-001, SHIP-004). Pure: no database, no HTTP.

A shipment is one delivery note: who it is for, how it leaves, and what is in it.
  draft ─ready→ ready ─dispatch→ dispatched ─deliver→ delivered | partially_delivered
                ready ─reopen→ draft                    (a change before loading, first attempt only)
                ready ─deliver→ delivered               (pickup: the customer collects at the factory)
                       dispatched ─fail(reason)→ returned  (not received: the goods come back to the factory)
                       returned ─reschedule→ ready      (the same note, attempt 2, 3 …: its lines never change)
                       returned ─close(reason)→ not_delivered
  draft / ready ─cancel(reason)→ cancelled              (only before the goods ever left)
Only a draft is edited. Once dispatched the goods have left: the note's lines are frozen. What comes back is a
return (see returns.py): the refused part of a partial delivery, a failed delivery, or a customer's later return.
Delivered, partially delivered, not delivered and cancelled shipments are final.
The customer is always named, whether a registered customer or not. Delivery methods:
  pickup            the customer's driver collects: name, ID, phone and vehicle plate
  factory_delivery  the factory's driver delivers: name, phone and vehicle plate
  carrier           a carrier company delivers: its name and tracking number
"""
import re
from decimal import Decimal

from app.core.units import to_kilograms


class ShippingError(ValueError):
    def __init__(self, code: str, status: int = 409, **detail):
        super().__init__(code)
        self.code, self.status, self.detail = code, status, detail


DRAFT, READY, DISPATCHED, DELIVERED, CANCELLED = "draft", "ready", "dispatched", "delivered", "cancelled"
PARTIALLY_DELIVERED, RETURNED, NOT_DELIVERED = "partially_delivered", "returned", "not_delivered"
STATUSES = (DRAFT, READY, DISPATCHED, DELIVERED, PARTIALLY_DELIVERED, RETURNED, NOT_DELIVERED, CANCELLED)
FINAL = frozenset({DELIVERED, PARTIALLY_DELIVERED, NOT_DELIVERED, CANCELLED})
RECEIVED = frozenset({DELIVERED, PARTIALLY_DELIVERED})  # the customer holds (some of) the goods
PICKUP, FACTORY_DELIVERY, CARRIER = "pickup", "factory_delivery", "carrier"
METHODS = (PICKUP, FACTORY_DELIVERY, CARRIER)
DEFAULT_PREFIX = "DN-"
ZERO = Decimal("0")


# ── contacts ────────────────────────────────────────────────────────────────────────────────────

def normalize_phone(value: str | None) -> str | None:
    """A phone in international form: "+9665…"; a Saudi local number ("05…", "011…") gets +966. Digits may be Arabic."""
    if value is None or not str(value).strip():
        return None
    text = str(value).strip().translate({**{0x0660 + i: str(i) for i in range(10)}, **{0x06F0 + i: str(i) for i in range(10)}})
    text = re.sub(r"[\s\-().]", "", text)
    if text.startswith("00"):
        text = "+" + text[2:]
    if re.fullmatch(r"0\d{8,9}", text):  # a Saudi local number: mobile 05…, landline 01…
        text = "+966" + text[1:]
    if not re.fullmatch(r"\+\d{8,15}", text):
        raise ShippingError("PHONE_INVALID", 400, value=str(value))
    return text


# ── lifecycle ───────────────────────────────────────────────────────────────────────────────────

def assert_editable(status) -> None:
    if status != DRAFT:
        raise ShippingError("SHIPMENT_NOT_DRAFT", shipment_status=status)


def assert_ready(shipment, line_count: int) -> None:
    """What a delivery note needs before it is printed for loading."""
    assert_editable(shipment.status)
    if not (shipment.customer_name or "").strip():
        raise ShippingError("CUSTOMER_REQUIRED", 400)
    if line_count == 0:
        raise ShippingError("LINES_REQUIRED", 400)
    missing = method_gaps(shipment)
    if missing:
        raise ShippingError("METHOD_DETAILS_REQUIRED", 400, fields=",".join(missing))


def method_gaps(shipment) -> list[str]:
    """The method's own details still empty (who carries the goods, and how)."""
    needed = {PICKUP: ("driver_name", "vehicle_plate"), FACTORY_DELIVERY: ("driver_name", "vehicle_plate"),
              CARRIER: ("carrier_name",)}[shipment.delivery_method]
    return [field for field in needed if not (getattr(shipment, field) or "").strip()]


def assert_can_reopen(status, attempt=1) -> None:
    if status != READY:
        raise ShippingError("SHIPMENT_NOT_READY", shipment_status=status)
    if attempt > 1:
        raise ShippingError("SHIPMENT_LEFT_BEFORE")  # its goods went out once: the lines stay as dispatched


def assert_can_dispatch(status, method) -> None:
    if status != READY:
        raise ShippingError("SHIPMENT_NOT_READY", shipment_status=status)
    if method == PICKUP:
        raise ShippingError("PICKUP_IS_DELIVERED_AT_FACTORY")


def assert_can_deliver(status, method, received_by) -> None:
    allowed = (READY,) if method == PICKUP else (DISPATCHED,)
    if status not in allowed:
        raise ShippingError("SHIPMENT_NOT_DISPATCHED" if method != PICKUP else "SHIPMENT_NOT_READY", shipment_status=status)
    if not (received_by or "").strip():
        raise ShippingError("RECEIVER_REQUIRED", 400)


def assert_can_cancel(status, reason, attempt=1) -> None:
    if status not in (DRAFT, READY):
        raise ShippingError("SHIPMENT_ALREADY_LEFT" if status in (DISPATCHED, RETURNED) else "SHIPMENT_IS_FINAL", shipment_status=status)
    if attempt > 1:
        raise ShippingError("SHIPMENT_LEFT_BEFORE")  # close it as not delivered instead
    _reason(reason)


def _reason(reason) -> None:
    if not (reason or "").strip():
        raise ShippingError("REASON_REQUIRED", 400)


def split_delivery(lines, accepted: dict, method) -> list[tuple[object, Decimal]]:
    """What the customer accepted of each line (all of it unless said otherwise), and what was refused at the door:
    [(line, refused quantity)] for the lines with a refused part."""
    unknown = set(accepted) - {line.id for line in lines}
    if unknown:
        raise ShippingError("LINE_NOT_FOUND", 400)
    refused, taken_total = [], ZERO
    for line in lines:
        taken = accepted.get(line.id, line.quantity)
        if taken < ZERO or taken > line.quantity:
            raise ShippingError("DELIVERED_QUANTITY_INVALID", 400, line=line.line_no)
        taken_total += taken
        if taken < line.quantity:
            refused.append((line, line.quantity - taken))
    if refused and method == PICKUP:
        raise ShippingError("PARTIAL_NOT_FOR_PICKUP", 400)  # what is not collected never left: edit the note
    if taken_total == ZERO:
        raise ShippingError("NOTHING_DELIVERED", 400)  # record a failed delivery instead
    return refused


def assert_can_fail(status, reason) -> None:
    if status != DISPATCHED:
        raise ShippingError("SHIPMENT_NOT_DISPATCHED", shipment_status=status)
    _reason(reason)


def assert_can_reschedule(status, back_at_factory) -> None:
    if status != RETURNED:
        raise ShippingError("SHIPMENT_NOT_RETURNED", shipment_status=status)
    if not back_at_factory:
        raise ShippingError("RETURN_NOT_RECEIVED")  # the goods must be back before they leave again


def assert_can_close(status, attempt, back_at_factory, reason) -> None:
    if not (status == RETURNED or (status == READY and attempt > 1)):
        raise ShippingError("SHIPMENT_NOT_RETURNED", shipment_status=status)
    if status == RETURNED and not back_at_factory:
        raise ShippingError("RETURN_NOT_RECEIVED")
    _reason(reason)


def actions(status, method, can, attempt=1, back_at_factory=True, returnable=False) -> list[str]:
    go = "deliver" if method == PICKUP else "dispatch"
    offered = {
        DRAFT: ["edit", "ready", "cancel"],
        READY: ["reopen", go, "cancel"] if attempt == 1 else [go, "close"],
        DISPATCHED: ["deliver", "fail"],
        RETURNED: ["reschedule", "close"] if back_at_factory else [],
        DELIVERED: ["return"] if returnable else [],
        PARTIALLY_DELIVERED: ["return"] if returnable else [],
    }.get(status, [])
    return [a for a in offered if can(a)]


# ── weights ─────────────────────────────────────────────────────────────────────────────────────

def weight_check(planned_kg, gate_kg, received_kg, tolerance_pct) -> dict | None:
    """The weight received against the weight that left (the gate weighbridge, else the lines' weights)."""
    reference = gate_kg if gate_kg is not None else planned_kg
    if received_kg is None or not reference:
        return None
    difference = (received_kg - reference).quantize(Decimal("0.001"))
    percent = (difference / reference * 100).quantize(Decimal("0.01"))
    return dict(reference_kg=reference, received_kg=received_kg, difference_kg=difference, difference_pct=percent,
                tolerance_pct=tolerance_pct, within_tolerance=abs(percent) <= tolerance_pct)


# ── lines ───────────────────────────────────────────────────────────────────────────────────────

def assert_line(line) -> None:
    if line.quantity is None or line.quantity <= ZERO:
        raise ShippingError("QUANTITY_REQUIRED", 400, line=line.line_no)


def totals(lines) -> dict:
    """The whole note: quantities per unit (rolls and kilograms are never added together), and the lines' weights,
    whatever unit each uses, in kilograms."""
    per_unit: dict[str, Decimal] = {}
    for line in lines:
        per_unit[line.unit] = per_unit.get(line.unit, ZERO) + line.quantity
    weights = [to_kilograms(line.weight, line.weight_unit) for line in lines if line.weight is not None]
    return dict(quantities=per_unit, weight_kg=sum(weights, ZERO).quantize(Decimal("0.001")) if weights else None)


def number(prefix: str, year: int, value: int) -> str:
    return f"{prefix}{year}-{value:04d}"
