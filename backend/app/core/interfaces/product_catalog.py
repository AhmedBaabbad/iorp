"""The organization's product catalogue and general business settings, as other modules see them (MD-001).

Master data owns products (their keys, names and specification templates) and the VAT rate and default currency. Sales,
production, quality and procurement must not import it nor read its tables: master data registers a provider at the
composition root, and they ask here. Read-only.

Choosing from the list: once an organization has defined products, a product type written on a record must be the key
of an active product. A value a record already stores (a legacy text, or a product since deactivated) may stay on it.
Until the first product exists nothing is enforced, so an organization is never blocked before it sets its catalogue.
Samples use the stricter validate_sample_properties contract: new samples always require a catalog product.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable, Protocol
from uuid import UUID

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class PropertyInfo:
    key: str
    name_ar: str
    name_en: str
    kind: str  # number | text | choice
    unit: str | None = None
    options: tuple[tuple[str, str, str], ...] = ()  # (value, label_ar, label_en)
    required: bool = False
    allows_range: bool = False


@dataclass(frozen=True)
class ProductInfo:
    key: str
    name_ar: str
    name_en: str
    active: bool
    properties: tuple[PropertyInfo, ...] = field(default_factory=tuple)
    default_unit: str | None = None

    def name(self, lang: str) -> str:
        return self.name_ar if lang == "ar" else self.name_en


@dataclass(frozen=True)
class BusinessSettings:
    vat_rate: Decimal = Decimal("15")
    default_currency: str = "SAR"


class ProductCatalog(Protocol):
    def defined(self, db: Session, organization_id: UUID) -> bool: ...
    def products(self, db: Session, organization_id: UUID, keys: Iterable[str]) -> dict[str, ProductInfo]: ...
    def settings(self, db: Session, organization_id: UUID) -> BusinessSettings: ...
    def sample_products(self, db: Session, organization_id: UUID) -> list[ProductInfo]: ...
    def validate_sample_properties(self, db: Session, organization_id: UUID, key: str, values: dict,
                                   *, existing_key: str | None = None, existing_values: dict | None = None) -> dict: ...


class ProductSpecificationError(ValueError):
    def __init__(self, code: str, property_key: str | None = None):
        super().__init__(code)
        self.code, self.property_key = code, property_key


_provider: ProductCatalog | None = None


def register_product_catalog(provider: ProductCatalog) -> None:
    global _provider
    _provider = provider


def products(db: Session, organization_id: UUID, keys: Iterable[str]) -> dict[str, ProductInfo]:
    """{key: product} for the keys that are products (active or not); legacy texts are simply absent."""
    keys = {k for k in keys if k}
    return _provider.products(db, organization_id, keys) if _provider and keys else {}


def business_settings(db: Session, organization_id: UUID) -> BusinessSettings:
    return _provider.settings(db, organization_id) if _provider else BusinessSettings()


def validate_specification_values(db, organization_id, items, spec_attr='requested_spec_json', *, ranges_only=False):
    """Validate numeric fields/ranges on document writes, retaining free-text legacy specs.

    The product catalogue is read once for the document. Only the owning module
    validates all required/text/choice rules; this shared boundary protects ranges.
    Existing owners can retain their scalar validation and error contract with ranges_only.
    """
    from app.core.specifications import normalize_numeric, SpecificationValueError
    get = lambda item, key: item.get(key) if isinstance(item, dict) else getattr(item, key, None)
    items = list(items)
    known = products(db, organization_id, [get(item, 'product_type') for item in items])
    for item in items:
        product = known.get(get(item, 'product_type'))
        props = {p.key: p for p in product.properties} if product else {}
        for key, value in (get(item, spec_attr) or {}).items():
            prop = props.get(key)
            is_range = isinstance(value, dict) and ('min' in value or 'max' in value)
            if value in (None, '') or not (is_range or (not ranges_only and prop and prop.kind == 'number')):
                continue
            try:
                get(item, spec_attr)[key] = normalize_numeric(value, bool(prop and prop.kind == 'number' and prop.allows_range))
            except SpecificationValueError as exc:
                raise ProductSpecificationError(exc.code, key) from None


def sample_products(db: Session, organization_id: UUID) -> list[ProductInfo]:
    return _provider.sample_products(db, organization_id) if _provider else []


def validate_sample_properties(db, organization_id, key, values, *, existing_key=None, existing_values=None):
    if _provider is None:
        raise ProductSpecificationError('SAMPLE_PRODUCT_NOT_FOUND')
    return _provider.validate_sample_properties(db, organization_id, key, values,
        existing_key=existing_key, existing_values=existing_values)


def unknown_product_types(db: Session, organization_id: UUID, values: Iterable[str], keep: Iterable[str] = ()) -> list[str]:
    """The values that may not be written: not the key of an active product, and not already stored on the record (keep)."""
    if _provider is None or not _provider.defined(db, organization_id):
        return []
    kept = set(keep)
    wanted = {v for v in values if v and v not in kept}
    found = products(db, organization_id, wanted)
    return sorted(v for v in wanted if not (v in found and found[v].active))
