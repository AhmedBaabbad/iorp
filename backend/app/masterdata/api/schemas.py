"""Master data API (MD-001). Inputs never accept organization scope; errors answer {"code": ...}."""
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.types import ISODatetime
from app.core.units import UNITS
from app.masterdata.domain import rules

Kind = Literal["finished", "material"]
PropertyKind = Literal["number", "text", "choice"]
Currency = Literal["SAR", "USD"]
assert set(Kind.__args__) == set(rules.KINDS) and set(PropertyKind.__args__) == set(rules.PROPERTY_KINDS)
assert set(Currency.__args__) == set(rules.CURRENCIES)


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _known_unit(value):
    if value and value not in UNITS:
        raise ValueError("UNIT_UNKNOWN")
    return value or None


class OptionInput(_Input):
    value: str = Field(min_length=1, max_length=60)
    label_ar: str = Field(min_length=1, max_length=120)
    label_en: str = Field(min_length=1, max_length=120)


class PropertyInput(_Input):
    key: str = Field(min_length=2, max_length=60)
    name_ar: str = Field(min_length=1, max_length=120)
    name_en: str = Field(min_length=1, max_length=120)
    kind: PropertyKind = "text"
    unit: str | None = Field(default=None, max_length=32)
    required: bool = False
    options: list[OptionInput] | None = Field(default=None, max_length=rules.MAX_OPTIONS)

    @field_validator("unit")
    @classmethod
    def known_unit(cls, value):
        return _known_unit(value)


class ProductCreate(_Input):
    key: str | None = Field(default=None, max_length=60)  # from the English name when left empty
    name_ar: str = Field(min_length=1, max_length=255)
    name_en: str = Field(min_length=1, max_length=255)
    kind: Kind = "finished"
    default_unit: str | None = Field(default=None, max_length=32)
    active: bool = True
    notes: str | None = Field(default=None, max_length=2000)
    properties: list[PropertyInput] = Field(default_factory=list, max_length=rules.MAX_PROPERTIES)

    @field_validator("default_unit")
    @classmethod
    def known_unit(cls, value):
        """Units come from the shared catalogue, so every document prints them in its language."""
        return _known_unit(value)


class ProductUpdate(_Input):
    name_ar: str | None = Field(default=None, min_length=1, max_length=255)
    name_en: str | None = Field(default=None, min_length=1, max_length=255)
    kind: Kind | None = None
    default_unit: str | None = Field(default=None, max_length=32)
    active: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)
    properties: list[PropertyInput] | None = Field(default=None, max_length=rules.MAX_PROPERTIES)

    @field_validator("default_unit")
    @classmethod
    def known_unit(cls, value):
        """Units come from the shared catalogue, so every document prints them in its language."""
        return _known_unit(value)


class OptionRead(BaseModel):
    value: str
    label_ar: str
    label_en: str


class PropertyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: str
    name_ar: str
    name_en: str
    kind: str
    unit: str | None
    required: bool
    options: list[OptionRead] | None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    key: str
    name_ar: str
    name_en: str
    kind: str
    default_unit: str | None
    active: bool
    notes: str | None
    properties: list[PropertyRead] = []
    actions: list[str] = []
    created_at: ISODatetime
    updated_at: ISODatetime


class LegacyValue(BaseModel):
    value: str
    uses: dict[str, int]  # module -> records
    total: int
    suggested_key: str


class LegacyMapInput(BaseModel):
    # Not stripped: a legacy value is matched exactly as stored (it may end in a space).
    model_config = ConfigDict(extra="forbid")
    value: str = Field(min_length=1, max_length=255)
    product_id: UUID


class LegacyMapResult(BaseModel):
    value: str
    key: str
    changed: dict[str, int]


class SettingsInput(_Input):
    vat_rate: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    default_currency: Currency | None = None


class SettingsRead(BaseModel):
    vat_rate: Decimal
    default_currency: str
    currencies: list[str]



# ── reference lists (MD-002) ────────────────────────────────────────────────────────────────────
ListName = Literal["sector", "opportunity_source", "country", "city"]


class ListItemCreate(_Input):
    key: str | None = Field(default=None, max_length=60)  # from the English name when left empty
    name_ar: str = Field(min_length=1, max_length=200)
    name_en: str = Field(min_length=1, max_length=200)
    parent_key: str | None = Field(default=None, max_length=60)  # a city's country


class ListItemUpdate(_Input):
    name_ar: str | None = Field(default=None, min_length=1, max_length=200)
    name_en: str | None = Field(default=None, min_length=1, max_length=200)
    parent_key: str | None = Field(default=None, max_length=60)
    active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100000)


class ListItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    list: str
    key: str
    name_ar: str
    name_en: str
    parent_key: str | None
    active: bool
    sort_order: int


class ListLegacyMapInput(BaseModel):
    # Not stripped: a legacy value is matched exactly as stored.
    model_config = ConfigDict(extra="forbid")
    value: str = Field(min_length=1, max_length=255)
    item_id: UUID
