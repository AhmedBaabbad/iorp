"""Test parameters and product specifications API (QUAL-SPEC-001)."""
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.types import ISODatetime

Limit = Decimal  # in the parameter's unit, up to four decimals


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ParameterCreate(_Input):
    code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_\-]+$")
    name_ar: str = Field(min_length=1, max_length=120)
    name_en: str = Field(min_length=1, max_length=120)
    kind: Literal["numeric", "attribute"]
    unit: str | None = Field(default=None, max_length=16)
    method: str | None = Field(default=None, max_length=255)
    sort_order: int = Field(default=0, ge=0, le=10000)


class ParameterUpdate(_Input):
    name_ar: str | None = Field(default=None, min_length=1, max_length=120)
    name_en: str | None = Field(default=None, min_length=1, max_length=120)
    unit: str | None = Field(default=None, max_length=16)
    method: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)


class ParameterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    name_ar: str
    name_en: str
    kind: str
    unit: str | None
    method: str | None
    is_active: bool
    sort_order: int


class SpecificationLineInput(_Input):
    parameter_id: UUID
    target_source: Literal["fixed", "order_line", "none"] = "none"
    order_spec_key: str | None = Field(default=None, max_length=60)
    target_value: Limit | None = Field(default=None, max_digits=14, decimal_places=4)
    tolerance_minus: Limit | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    tolerance_plus: Limit | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    min_value: Limit | None = Field(default=None, max_digits=14, decimal_places=4)
    max_value: Limit | None = Field(default=None, max_digits=14, decimal_places=4)
    requirement: str | None = Field(default=None, max_length=255)
    acceptance: str | None = Field(default=None, max_length=255)
    method: str | None = Field(default=None, max_length=255)
    readings_required: int = Field(default=1, ge=1, le=50)


class SpecificationCreate(_Input):
    code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_\-]+$")
    title: str = Field(min_length=1, max_length=200)
    product_type: str = Field(min_length=1, max_length=120)
    grade: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=4000)
    lines: list[SpecificationLineInput] = Field(default_factory=list, max_length=60)


class SpecificationUpdate(_Input):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    product_type: str | None = Field(default=None, min_length=1, max_length=120)
    grade: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=4000)
    lines: list[SpecificationLineInput] | None = Field(default=None, max_length=60)


class SpecificationLineRead(BaseModel):
    id: UUID
    position: int
    parameter_id: UUID
    parameter_code: str
    name_ar: str
    name_en: str
    kind: str
    unit: str | None
    parameter_method: str | None
    target_source: str
    order_spec_key: str | None
    target_value: Decimal | None
    tolerance_minus: Decimal | None
    tolerance_plus: Decimal | None
    min_value: Decimal | None
    max_value: Decimal | None
    requirement: str | None
    acceptance: str | None
    method: str | None
    readings_required: int


class SpecificationListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    revision: int
    title: str
    product_type: str
    grade: str | None
    status: str
    activated_at: ISODatetime | None
    activated_by_name: str | None = None
    created_by_name: str | None = None
    actions: list[str] = []
    updated_at: ISODatetime


class SpecificationRead(SpecificationListItem):
    notes: str | None
    lines: list[SpecificationLineRead] = []
