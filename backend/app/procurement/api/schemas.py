"""Procurement API (PROC-001). Create/Update schemas never accept organization scope; errors answer {"code": ...}."""
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.types import ISODatetime, NormalizedEmail
from app.core.units import UNITS, WEIGHT_UNITS
from app.procurement.domain import purchase_orders as PO
from app.procurement.domain import rules

SupplierCategory = Literal["raw_material", "packaging", "consumables", "services", "other"]
MaterialCategory = Literal["resin", "masterbatch", "additive", "core", "carton", "film", "accessory", "other"]
SupplierStatus = Literal["approved", "conditional", "blocked"]
WeightUnit = Literal["g", "kg", "ton", "lb", "oz"]
assert set(SupplierCategory.__args__) == set(rules.SUPPLIER_CATEGORIES) and set(MaterialCategory.__args__) == set(rules.MATERIAL_CATEGORIES)
assert set(WeightUnit.__args__) == set(WEIGHT_UNITS)
Currency = Literal["SAR", "USD"]
Incoterm = Literal["EXW", "FCA", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP"]
PaymentTerms = Literal["advance", "on_delivery", "net_15", "net_30", "net_45", "net_60", "net_90", "letter_of_credit", "other"]
assert set(Currency.__args__) == set(PO.CURRENCIES) and set(Incoterm.__args__) == set(PO.INCOTERMS)
assert set(PaymentTerms.__args__) == set(PO.PAYMENT_TERMS)


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _known_unit(value):
    if value is not None and value not in UNITS:
        raise ValueError("UNIT_UNKNOWN")
    return value


# ── suppliers ────────────────────────────────────────────────────────────────────────────────────
class SupplierCreate(_Input):
    name: str = Field(min_length=1, max_length=255)
    category: SupplierCategory = "raw_material"
    supplies: str | None = Field(default=None, max_length=500)
    contact_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    email: NormalizedEmail | None = None
    address: str | None = Field(default=None, max_length=1000)
    city: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=80)
    vat_number: str | None = Field(default=None, max_length=40)
    cr_number: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=4000)


class SupplierUpdate(SupplierCreate):
    name: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore[assignment]
    category: SupplierCategory | None = None  # type: ignore[assignment]


class SupplierStatusInput(_Input):
    status: SupplierStatus
    reason: str | None = Field(default=None, max_length=2000)


class SupplierOption(BaseModel):
    id: UUID
    supplier_code: str
    name: str
    status: str


class HistoryEntry(BaseModel):
    action: str
    from_status: str | None
    to_status: str | None
    reason: str | None
    actor_name: str | None
    at: ISODatetime


class ReceiptRef(BaseModel):
    id: UUID
    receipt_no: str
    receipt_date: date
    status: str


class NonConformanceRef(BaseModel):
    id: UUID
    report_number: str
    report_date: date
    title: str
    status: str
    severity: str
    reference_code: str | None


class Evaluation(BaseModel):
    """The supplier's score over a period (PROC-002): see rules.evaluate."""
    months: int
    since: date
    lots_inspected: int
    lots_released: int
    lots_rejected: int
    acceptance_pct: Decimal | None
    ncr_count: int
    ncr_penalty: int
    ncr_cost: Decimal
    cost_penalty: int
    score: Decimal | None
    grade: str | None
    suggested_status: str | None


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    supplier_code: str
    name: str
    category: str
    status: str
    status_reason: str | None
    status_changed_at: ISODatetime | None
    status_changed_by_name: str | None = None
    supplies: str | None
    contact_name: str | None
    phone: str | None
    email: str | None
    address: str | None
    city: str | None
    country: str | None
    vat_number: str | None
    cr_number: str | None
    notes: str | None
    receipts_count: int = 0
    last_receipt_date: date | None = None
    ncr_count: int = 0
    open_ncr_count: int = 0
    actions: list[str] = []
    history: list[HistoryEntry] = []
    non_conformances: list[NonConformanceRef] = []
    evaluation: Evaluation | None = None
    recent_receipts: list[ReceiptRef] = []
    created_at: ISODatetime


# ── materials ────────────────────────────────────────────────────────────────────────────────────
class MaterialCreate(_Input):
    name: str = Field(min_length=1, max_length=255)
    category: MaterialCategory = "resin"
    unit: str = Field(default="kg", max_length=32)
    inspection_required: bool = True
    spec_product_type: str | None = Field(default=None, max_length=120)
    active: bool = True
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("unit")
    @classmethod
    def known_unit(cls, value):
        """Units come from the shared catalogue, so every document prints them in its language."""
        return _known_unit(value)


class MaterialUpdate(_Input):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: MaterialCategory | None = None
    unit: str | None = Field(default=None, max_length=32)
    inspection_required: bool | None = None
    spec_product_type: str | None = Field(default=None, max_length=120)
    active: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("unit")
    @classmethod
    def known_unit(cls, value):
        """Units come from the shared catalogue, so every document prints them in its language."""
        return _known_unit(value)


class MaterialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    material_code: str
    name: str
    category: str
    unit: str
    inspection_required: bool
    spec_product_type: str | None
    active: bool
    notes: str | None


# ── receipts ─────────────────────────────────────────────────────────────────────────────────────
class LineInput(_Input):
    material_id: UUID | None = None
    description: str | None = Field(default=None, max_length=255)  # the material's name when left empty
    supplier_lot: str | None = Field(default=None, max_length=80)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit: str = Field(min_length=1, max_length=32)
    package_count: int | None = Field(default=None, ge=0, le=100000)
    weight: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    weight_unit: WeightUnit = "kg"
    notes: str | None = Field(default=None, max_length=500)
    po_line_id: UUID | None = None  # the purchase order line it delivers (the receipt's order)

    @field_validator("unit")
    @classmethod
    def known_unit(cls, value):
        """Units come from the shared catalogue, so every document prints them in its language."""
        return _known_unit(value)


class _ReceiptHeader(_Input):
    supplier_delivery_no: str | None = Field(default=None, max_length=80)
    supplier_invoice_no: str | None = Field(default=None, max_length=80)
    purchase_reference: str | None = Field(default=None, max_length=80)
    vehicle_plate: str | None = Field(default=None, max_length=40)
    driver_name: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=4000)


class ReceiptCreate(_ReceiptHeader):
    supplier_id: UUID
    receipt_date: date
    purchase_order_id: UUID | None = None
    lines: list[LineInput] = Field(default_factory=list, max_length=100)


class ReceiptUpdate(_ReceiptHeader):
    supplier_id: UUID | None = None
    purchase_order_id: UUID | None = None
    receipt_date: date | None = None
    lines: list[LineInput] | None = Field(default=None, max_length=100)


class ReasonInput(_Input):
    reason: str = Field(min_length=1, max_length=2000)


PREFIX = r"^[A-Za-z0-9_\-/]+$"


class SettingsInput(_Input):
    receipt_prefix: str | None = Field(default=None, min_length=1, max_length=20, pattern=PREFIX)
    po_prefix: str | None = Field(default=None, min_length=1, max_length=20, pattern=PREFIX)
    # The general terms printed on every purchase order: one term per line.
    po_terms_ar: str | None = Field(default=None, max_length=8000)
    po_terms_en: str | None = Field(default=None, max_length=8000)


class SettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    receipt_prefix: str
    po_prefix: str = "PO-"
    po_terms_ar: str | None = None
    po_terms_en: str | None = None


class LineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    line_no: int
    material_id: UUID | None
    description: str
    supplier_lot: str | None
    quantity: Decimal
    unit: str
    package_count: int | None
    weight: Decimal | None
    weight_unit: str
    inspection_required: bool
    notes: str | None
    po_line_id: UUID | None = None


class UnitQuantity(BaseModel):
    unit: str
    quantity: Decimal


class ReceiptListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    receipt_no: str
    status: str
    receipt_date: date
    supplier_id: UUID
    supplier_name: str
    supplier_status: str | None = None
    supplier_delivery_no: str | None
    supplier_invoice_no: str | None
    purchase_reference: str | None
    purchase_order_id: UUID | None = None
    po_number: str | None = None
    quantities: list[UnitQuantity] = []
    weight_kg: Decimal | None = None
    inspection_lines: int = 0
    lots_pending: int = 0
    actions: list[str] = []
    created_at: ISODatetime


class LotInspection(BaseModel):
    id: UUID
    inspection_code: str
    status: str
    result: str | None
    qty_inspected: Decimal
    qty_accepted: Decimal
    closed_at: ISODatetime | None


class LotQuality(BaseModel):
    status: str  # not_required · awaiting · inspecting · released · partly_released · rejected
    inspection: LotInspection | None = None


class ReceiptRead(ReceiptListItem):
    vehicle_plate: str | None
    driver_name: str | None
    notes: str | None
    received_at: ISODatetime | None
    received_by_name: str | None = None
    created_by_name: str | None = None
    cancel_reason: str | None
    lines: list[LineRead] = []
    line_quality: dict[str, LotQuality] = {}
    history: list[HistoryEntry] = []
    updated_at: ISODatetime


# ── purchase orders (PROC-003) ─────────────────────────────────────────────────────────────────
class OrderLineInput(_Input):
    material_id: UUID | None = None
    description: str | None = Field(default=None, max_length=500)  # the material's name when left empty
    notes: str | None = Field(default=None, max_length=500)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit: str = Field(min_length=1, max_length=32)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=4)

    @field_validator("unit")
    @classmethod
    def known_unit(cls, value):
        return _known_unit(value)


class _OrderHeader(_Input):
    required_date: date | None = None
    attention: str | None = Field(default=None, max_length=200)
    supplier_quote_ref: str | None = Field(default=None, max_length=80)
    subject: str | None = Field(default=None, max_length=255)
    # The organization's VAT rate (a local supplier) or 0 (an import from abroad); another rate is refused (TAX_RATE_UNKNOWN).
    tax_rate: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    discount_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    payment_terms: PaymentTerms | None = None
    payment_terms_note: str | None = Field(default=None, max_length=255)
    incoterm: Incoterm | None = None
    delivery_place: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=4000)


class OrderCreate(_OrderHeader):
    supplier_id: UUID
    order_date: date
    currency: Currency | None = None  # the organization's default currency when left out
    lines: list[OrderLineInput] = Field(default_factory=list, max_length=200)


class OrderUpdate(_OrderHeader):
    supplier_id: UUID | None = None
    order_date: date | None = None
    currency: Currency | None = None
    lines: list[OrderLineInput] | None = Field(default=None, max_length=200)


class OrderLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    line_no: int
    material_id: UUID | None
    description: str
    notes: str | None
    quantity: Decimal
    unit: str
    unit_price: Decimal
    line_total: Decimal


class LineReceived(BaseModel):
    received: Decimal
    remaining: Decimal


class OrderReceiptRef(BaseModel):
    id: UUID
    receipt_no: str
    receipt_date: date
    status: str


class OrderListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    po_number: str
    status: str
    order_date: date
    required_date: date | None
    supplier_id: UUID
    supplier_name: str
    supplier_status: str | None = None
    supplier_quote_ref: str | None
    subject: str | None
    currency: str
    tax_rate: Decimal
    total_amount: Decimal
    line_count: int = 0
    received_pct: Decimal = Decimal(0)
    actions: list[str] = []
    created_at: ISODatetime


class OrderRead(OrderListItem):
    attention: str | None
    subtotal_amount: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    payment_terms: str | None
    payment_terms_note: str | None
    incoterm: str | None
    delivery_place: str | None
    notes: str | None
    approved_at: ISODatetime | None
    approved_by_name: str | None = None
    sent_at: ISODatetime | None
    sent_by_name: str | None = None
    closed_at: ISODatetime | None
    close_reason: str | None
    cancel_reason: str | None
    created_by_name: str | None = None
    lines: list[OrderLineRead] = []
    line_received: dict[str, LineReceived] = {}
    receipts: list[OrderReceiptRef] = []
    history: list[HistoryEntry] = []
    updated_at: ISODatetime


class OpenOrderLine(BaseModel):
    id: UUID
    line_no: int
    material_id: UUID | None
    description: str
    unit: str
    quantity: Decimal
    remaining: Decimal


class OpenOrder(BaseModel):
    id: UUID
    po_number: str
    order_date: date
    status: str
    lines: list[OpenOrderLine]
