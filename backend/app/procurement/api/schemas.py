"""Procurement API (PROC-001). Create/Update schemas never accept organization scope; errors answer {"code": ...}."""
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.types import ISODatetime, NormalizedEmail
from app.core.units import UNITS, WEIGHT_UNITS
from app.procurement.domain import rules

SupplierCategory = Literal["raw_material", "packaging", "consumables", "services", "other"]
MaterialCategory = Literal["resin", "masterbatch", "additive", "core", "carton", "film", "accessory", "other"]
SupplierStatus = Literal["approved", "conditional", "blocked"]
WeightUnit = Literal["g", "kg", "ton", "lb", "oz"]
assert set(SupplierCategory.__args__) == set(rules.SUPPLIER_CATEGORIES) and set(MaterialCategory.__args__) == set(rules.MATERIAL_CATEGORIES)
assert set(WeightUnit.__args__) == set(WEIGHT_UNITS)


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
    lines: list[LineInput] = Field(default_factory=list, max_length=100)


class ReceiptUpdate(_ReceiptHeader):
    supplier_id: UUID | None = None
    receipt_date: date | None = None
    lines: list[LineInput] | None = Field(default=None, max_length=100)


class ReasonInput(_Input):
    reason: str = Field(min_length=1, max_length=2000)


class SettingsInput(_Input):
    receipt_prefix: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_\-/]+$")


class SettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    receipt_prefix: str


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
    quantities: list[UnitQuantity] = []
    weight_kg: Decimal | None = None
    inspection_lines: int = 0
    actions: list[str] = []
    created_at: ISODatetime


class ReceiptRead(ReceiptListItem):
    vehicle_plate: str | None
    driver_name: str | None
    notes: str | None
    received_at: ISODatetime | None
    received_by_name: str | None = None
    created_by_name: str | None = None
    cancel_reason: str | None
    lines: list[LineRead] = []
    history: list[HistoryEntry] = []
    updated_at: ISODatetime
