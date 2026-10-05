"""Shipping API (SHIP-001, SHIP-004). Create/Update schemas never accept organization scope; errors answer {"code": ...}."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.types import ISODatetime, NormalizedEmail
from app.core.units import UNITS, WEIGHT_UNITS
from app.shipping.domain import returns as R

WeightUnit = Literal["g", "kg", "ton", "lb", "oz"]
assert set(WeightUnit.__args__) == set(WEIGHT_UNITS), "keep in step with app.core.units.WEIGHT_UNITS"

Method = Literal["pickup", "factory_delivery", "carrier"]
DeliveryReason = Literal["customer_refused", "site_closed", "no_receiver", "wrong_address", "transit_damage", "quality_issue", "other"]
CustomerReason = Literal["quality_defect", "spec_mismatch", "wrong_item", "transit_damage", "excess_quantity", "customer_cancelled", "other"]
assert set(DeliveryReason.__args__) == set(R.DELIVERY_REASONS) and set(CustomerReason.__args__) == set(R.CUSTOMER_REASONS)
Quantity = Decimal
URL = Field(default=None, max_length=500, pattern=r"^https?://\S+$")


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LineInput(_Input):
    description: str = Field(min_length=1, max_length=255)
    width_mm: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=3)
    thickness_mm: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=3)
    quantity: Quantity = Field(gt=0, max_digits=14, decimal_places=3)
    unit: str = Field(min_length=1, max_length=32)
    # The full weight of the line's units (one weight: no net / gross split).
    weight: Quantity | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    weight_unit: WeightUnit = "kg"
    production_order_id: UUID | None = None  # the batch the goods come from

    @field_validator("unit")
    @classmethod
    def known_unit(cls, value):
        """Units come from the shared catalogue, so every document prints them in its language."""
        if value not in UNITS:
            raise ValueError("UNIT_UNKNOWN")
        return value


class _Header(_Input):
    customer_id: UUID | None = None
    customer_name: str | None = Field(default=None, max_length=255)
    customer_reference: str | None = Field(default=None, max_length=80)
    consignee_name: str | None = Field(default=None, max_length=255)
    consignee_phone: str | None = Field(default=None, max_length=30)
    consignee_email: NormalizedEmail | None = None
    notify_consignee: bool = False
    delivery_address: str | None = Field(default=None, max_length=1000)
    delivery_city: str | None = Field(default=None, max_length=120)
    location_url: str | None = URL
    driver_name: str | None = Field(default=None, max_length=200)
    driver_phone: str | None = Field(default=None, max_length=30)
    driver_id_no: str | None = Field(default=None, max_length=40)
    vehicle_plate: str | None = Field(default=None, max_length=40)
    vehicle_type: str | None = Field(default=None, max_length=80)
    carrier_name: str | None = Field(default=None, max_length=200)
    tracking_no: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=4000)


class ShipmentCreate(_Header):
    delivery_method: Method
    shipment_date: date
    lines: list[LineInput] = Field(default_factory=list, max_length=100)


class ShipmentUpdate(_Header):
    delivery_method: Method | None = None
    shipment_date: date | None = None
    notify_consignee: bool | None = None  # type: ignore[assignment]
    lines: list[LineInput] | None = Field(default=None, max_length=100)


Weight = Field(default=None, ge=0, max_digits=14, decimal_places=3)
Prefix = Field(default=None, min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_\-/]+$")


class DispatchInput(_Input):
    gate_weight: Decimal | None = Weight  # the factory weighbridge
    gate_weight_unit: WeightUnit = "kg"


class DeliveredLine(_Input):
    line_id: UUID
    delivered_quantity: Decimal = Field(ge=0, max_digits=14, decimal_places=3)


class DeliverInput(_Input):
    received_by_name: str = Field(min_length=1, max_length=200)
    received_at: datetime | None = None
    delivery_notes: str | None = Field(default=None, max_length=2000)
    # Only the lines accepted in part (or not at all); the others were accepted in full.
    lines: list[DeliveredLine] = Field(default_factory=list, max_length=100)
    refusal_reason: DeliveryReason | None = None  # needed when something was refused
    refusal_details: str | None = Field(default=None, max_length=2000)
    received_weight: Decimal | None = Weight  # the customer's weighbridge
    received_weight_unit: WeightUnit = "kg"


class FailInput(_Input):
    reason: DeliveryReason
    details: str | None = Field(default=None, max_length=2000)


class RescheduleInput(_Input):
    delivery_method: Method | None = None
    shipment_date: date | None = None
    driver_name: str | None = Field(default=None, max_length=200)
    driver_phone: str | None = Field(default=None, max_length=30)
    driver_id_no: str | None = Field(default=None, max_length=40)
    vehicle_plate: str | None = Field(default=None, max_length=40)
    vehicle_type: str | None = Field(default=None, max_length=80)
    carrier_name: str | None = Field(default=None, max_length=200)
    tracking_no: str | None = Field(default=None, max_length=80)


class ReasonInput(_Input):
    reason: str = Field(min_length=1, max_length=1000)


class NoteInput(_Input):
    note: str | None = Field(default=None, max_length=2000)


class SettingsUpdate(_Input):
    note_prefix: str | None = Prefix
    return_prefix: str | None = Prefix
    return_window_days: int | None = Field(default=None, ge=0, le=365)
    weight_tolerance_pct: Decimal | None = Field(default=None, ge=0, le=50, max_digits=5, decimal_places=2)


class SettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    note_prefix: str
    return_prefix: str
    return_window_days: int
    weight_tolerance_pct: Decimal


class ProductionOrderOption(BaseModel):
    id: UUID
    number: str
    product_type: str
    status: str
    planned_quantity: Decimal
    unit: str


class CustomerOption(BaseModel):
    id: UUID
    customer_code: str
    name: str
    phone: str | None
    email: str | None
    city: str | None


class LineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    line_no: int
    description: str
    width_mm: Decimal | None
    thickness_mm: Decimal | None
    quantity: Decimal
    unit: str
    weight: Decimal | None
    weight_unit: str
    production_order_id: UUID | None = None
    production_order_no: str | None = None
    delivered_quantity: Decimal | None = None


class UnitQuantity(BaseModel):
    unit: str
    quantity: Decimal


class HistoryEntry(BaseModel):
    action: str
    from_status: str | None
    to_status: str
    reason: str | None
    actor_name: str | None
    at: ISODatetime
    return_no: str | None = None


class AttachmentRead(BaseModel):
    id: UUID
    kind: str
    file_name: str
    content_type: str
    size_bytes: int
    uploaded_by_name: str | None
    uploaded_at: ISODatetime


class ReturnSummary(BaseModel):
    id: UUID
    return_no: str
    kind: str
    status: str
    reason: str
    attempt: int
    requested_at: ISODatetime


class LineReturns(BaseModel):
    returned: Decimal
    returnable: Decimal


class WeightCheck(BaseModel):
    reference_kg: Decimal
    received_kg: Decimal
    difference_kg: Decimal
    difference_pct: Decimal
    tolerance_pct: Decimal
    within_tolerance: bool


class ShipmentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    shipment_no: str
    status: str
    delivery_method: str
    shipment_date: date
    customer_id: UUID | None
    customer_name: str
    customer_reference: str | None
    consignee_name: str | None
    delivery_city: str | None
    driver_name: str | None
    vehicle_plate: str | None
    carrier_name: str | None
    dispatched_at: ISODatetime | None
    delivered_at: ISODatetime | None
    quantities: list[UnitQuantity] = []
    weight_total_kg: Decimal | None = None
    attempt: int = 1
    open_returns: int = 0
    actions: list[str] = []
    created_at: ISODatetime


class ShipmentRead(ShipmentListItem):
    consignee_phone: str | None
    consignee_email: str | None
    notify_consignee: bool
    delivery_address: str | None
    location_url: str | None
    driver_phone: str | None
    driver_id_no: str | None
    vehicle_type: str | None
    tracking_no: str | None
    notes: str | None
    ready_at: ISODatetime | None
    received_by_name: str | None
    delivery_notes: str | None
    cancel_reason: str | None
    close_reason: str | None = None
    failed_at: ISODatetime | None = None
    gate_weight_kg: Decimal | None = None
    received_weight_kg: Decimal | None = None
    weight_check: WeightCheck | None = None
    returns: list[ReturnSummary] = []
    line_returns: dict[str, LineReturns] = {}
    attachments: list[AttachmentRead] = []
    lines: list[LineRead] = []
    missing_details: list[str] = []
    created_by_name: str | None = None
    dispatched_by_name: str | None = None
    delivered_recorded_by_name: str | None = None
    history: list[HistoryEntry] = []
    updated_at: ISODatetime


# ── returns ─────────────────────────────────────────────────────────────────────────────────────

class ReturnLineInput(_Input):
    shipment_line_id: UUID
    quantity: Quantity = Field(gt=0, max_digits=14, decimal_places=3)
    weight: Decimal | None = Weight  # in the line's weight unit; in proportion when left out


class ReturnCreate(_Input):
    """A customer's return of delivered goods, against its delivery note."""
    shipment_id: UUID
    reason: CustomerReason
    details: str | None = Field(default=None, max_length=4000)
    customer_reference: str | None = Field(default=None, max_length=80)
    carrier_claim_ref: str | None = Field(default=None, max_length=80)
    lines: list[ReturnLineInput] = Field(min_length=1, max_length=100)


class ReceivedLine(_Input):
    return_line_id: UUID
    received_quantity: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    received_weight: Decimal | None = Weight


class ReceiveInput(_Input):
    """What actually arrived back; lines left out arrived as expected. send_to_quality: the warehouse sends goods to
    quality although the reason does not require it (e.g. damage seen on arrival)."""
    received_at: datetime | None = None
    send_to_quality: bool = False
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[ReceivedLine] = Field(default_factory=list, max_length=100)


class QualityInspection(BaseModel):
    id: UUID
    inspection_code: str
    status: str
    result: str | None
    return_line_id: UUID | None
    qty_inspected: Decimal
    qty_accepted: Decimal


class QualityDecision(BaseModel):
    id: UUID
    rejection_code: str
    disposition: str | None
    disposition_status: str
    quantity: Decimal
    unit: str
    return_line_id: UUID | None


class ReturnQuality(BaseModel):
    """What quality did with the returned goods (read from quality's tables)."""
    expected: bool  # the reason sends them to quality
    inspections: list[QualityInspection] = []
    decisions: list[QualityDecision] = []


class ReturnLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    shipment_line_id: UUID
    line_no: int
    description: str
    width_mm: Decimal | None
    thickness_mm: Decimal | None
    unit: str
    weight_unit: str
    production_order_no: str | None
    quantity: Decimal
    weight: Decimal | None
    received_quantity: Decimal | None
    received_weight: Decimal | None


class ReturnListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    return_no: str
    kind: str
    status: str
    shipment_id: UUID
    shipment_no: str = ""
    attempt: int
    customer_id: UUID | None
    customer_name: str
    reason: str
    responsibility: str
    customer_reference: str | None
    requested_at: ISODatetime
    is_late: bool
    received_at: ISODatetime | None
    quality_required: bool = False
    quality_status: str | None = None
    quantities: list[UnitQuantity] = []
    weight_kg: Decimal | None = None
    actions: list[str] = []


class ReturnRead(ReturnListItem):
    details: str | None
    carrier_claim_ref: str | None
    delivery_method: str = ""
    delivered_at: ISODatetime | None = None
    decided_at: ISODatetime | None
    decision_note: str | None
    receipt_notes: str | None
    cancel_reason: str | None
    received_weight_kg: Decimal | None = None
    created_by_name: str | None = None
    decided_by_name: str | None = None
    received_by_name: str | None = None
    lines: list[ReturnLineRead] = []
    history: list[HistoryEntry] = []
    attachments: list[AttachmentRead] = []
    quality: ReturnQuality | None = None
    updated_at: ISODatetime
