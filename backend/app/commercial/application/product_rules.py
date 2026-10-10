"""Master data on sales records (MD-001), asked through core (never by importing master data): product types chosen from
the organization's products, and VAT at the organization's rate or none. A value a record already stores may stay on it."""
from decimal import Decimal

from app.core.interfaces.product_catalog import business_settings, unknown_product_types
from app.core.interfaces.reference_lists import unknown_list_values

# A customer's fields that name a reference list item (MD-002).
CUSTOMER_LISTS = {"sector": "sector", "opportunity_source": "opportunity_source", "country": "country", "city": "city"}
LIST_NAMES = {"sector": "القطاع / sector", "opportunity_source": "مصدر الفرصة / opportunity source", "country": "الدولة / country",
              "city": "المدينة / city"}


def assert_known_products(db, organization_id, values, keep=()) -> None:
    unknown = unknown_product_types(db, organization_id, values, keep)
    if unknown:
        raise ValueError("نوع المنتج ليس في قائمة المنتجات / The product type is not in the product list: " + ", ".join(unknown))


def assert_vat_rate(db, organization_id, rate, keep=None) -> None:
    if rate is None or Decimal(rate) == 0 or (keep is not None and Decimal(rate) == Decimal(keep)):
        return
    allowed = business_settings(db, organization_id).vat_rate
    if Decimal(rate) != Decimal(allowed):
        raise ValueError(f"نسبة الضريبة إما {Decimal(allowed).normalize()}% أو بدون / VAT is {Decimal(allowed).normalize()}% or none")


def assert_list_values(db, organization_id, values: dict, record=None) -> None:
    """Each field naming a reference list holds one of its active items; the value the record already stores may stay."""
    for field, list_name in CUSTOMER_LISTS.items():
        value = values.get(field)
        if value and unknown_list_values(db, organization_id, list_name, [value], [getattr(record, field)] if record is not None else ()):
            raise ValueError(f"{LIST_NAMES[list_name]}: ليس في القائمة / not in the list: {value}")
