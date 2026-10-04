"""Certificates of Analysis API (QUAL-COA-001)."""
from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.types import ISODatetime
from app.quality.api.inspection_schemas import HistoryEntry


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CertificateCreate(_Input):
    quality_check_id: UUID
    customer_id: UUID | None = None
    customer_po: str | None = Field(default=None, max_length=80)


class CertificateUpdate(_Input):
    customer_id: UUID | None = None
    customer_name: str | None = Field(default=None, max_length=255)
    customer_po: str | None = Field(default=None, max_length=80)
    delivery_ref: str | None = Field(default=None, max_length=80)
    batch_no: str | None = Field(default=None, min_length=1, max_length=80)
    product_description: str | None = Field(default=None, min_length=1, max_length=255)
    grade: str | None = Field(default=None, max_length=80)
    production_date: date | None = None
    inspection_date: date | None = None
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=3)
    unit_label: str | None = Field(default=None, max_length=32)
    package_count: int | None = Field(default=None, ge=0, le=1_000_000)
    sample_size: str | None = Field(default=None, max_length=120)
    sampling_reference: str | None = Field(default=None, max_length=120)
    retained_sample: bool | None = None
    retention_ref: str | None = Field(default=None, max_length=80)
    deviation_note: str | None = Field(default=None, max_length=2000)
    remarks: str | None = Field(default=None, max_length=2000)


class RevokeInput(_Input):
    reason: str = Field(min_length=1, max_length=1000)


class SettingsUpdate(_Input):
    coa_prefix: str | None = Field(default=None, min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_\-/]+$")
    coa_last_number: int | None = Field(default=None, ge=0, le=99_999_999)


class SettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    coa_prefix: str
    coa_last_number: int


class CustomerOption(BaseModel):
    id: UUID
    name: str


class CertificateSources(BaseModel):
    certifiable: bool
    blocker: str | None
    customers: list[CustomerOption]


class FrozenMeasurement(BaseModel):
    code: str
    name_ar: str
    name_en: str
    kind: str
    unit: str | None
    method: str | None
    requirement: str | None
    acceptance: str | None
    target: str | None
    lower: str | None
    upper: str | None
    count: int
    minimum: str | None
    maximum: str | None
    mean: str | None
    attribute_result: str | None
    observation: str | None
    status: str


class CertificateListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    certificate_no: str | None
    status: str
    quality_check_id: UUID
    production_order_id: UUID | None
    customer_name: str
    batch_no: str
    product_description: str
    quantity: Decimal
    unit_label: str
    inspection_code: str
    issued_at: ISODatetime | None
    issued_by_name: str | None = None
    supersedes_no: str | None = None
    superseded_by_no: str | None = None
    actions: list[str] = []
    created_at: ISODatetime


class CertificateRead(CertificateListItem):
    production_order_item_id: UUID | None
    customer_id: UUID | None
    customer_po: str | None
    delivery_ref: str | None
    grade: str | None
    production_date: date | None
    inspection_date: date | None
    package_count: int | None
    sample_size: str | None
    sampling_reference: str | None
    retained_sample: bool
    retention_ref: str | None
    deviation_note: str | None
    remarks: str | None
    inspection_result: str
    specification_code: str | None
    specification_revision: int | None
    measurements: list[FrozenMeasurement]
    inspector_name: str | None
    supersedes_id: UUID | None
    prepared_by_name: str | None = None
    revoked_at: ISODatetime | None
    revoked_by_name: str | None = None
    revoke_reason: str | None
    history: list[HistoryEntry] = []
